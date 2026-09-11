"""Bank of Canada Valet API client.

Valet is a public, keyless JSON API. Docs: https://www.bankofcanada.ca/valet/docs

We pull the policy rate, prime rate, 5-year GoC yield and the posted
conventional 5-year mortgage rate. Together these drive the renewal payment
shock that the whole analysis turns on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import requests

from ccra.logging_setup import get_logger

log = get_logger("ccra.ingest.boc")

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 4


class ValetError(RuntimeError):
    """Raised when Valet cannot be reached or returns an unusable payload."""


@dataclass
class ValetClient:
    base_url: str = "https://www.bankofcanada.ca/valet"
    timeout: int = DEFAULT_TIMEOUT
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()
            self.session.headers.update(
                {"Accept": "application/json", "User-Agent": "CCRA-pipeline/1.0"}
            )

    def _get(self, path: str, params: dict | None = None) -> dict:
        """GET with bounded exponential backoff on transient failures."""
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                # 4xx other than 429 is a request bug; retrying will not help.
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise ValetError(f"transient HTTP {resp.status_code} from {url}")
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValetError, ValueError) as exc:
                last_error = exc
                if attempt == MAX_RETRIES - 1:
                    break
                backoff = 2 ** (attempt + 1)
                log.warning(
                    "Valet request failed (attempt %d/%d): %s - retrying in %ds",
                    attempt + 1, MAX_RETRIES, exc, backoff,
                )
                import time
                time.sleep(backoff)

        raise ValetError(f"Valet request to {url} failed after {MAX_RETRIES} attempts: {last_error}")

    def observations(
        self,
        series: Iterable[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Fetch one or more series as a tidy frame.

        Returns columns: ``observation_date``, ``series_id``, ``value``.
        Valet caps a request at 10 series, so we chunk.
        """
        series = list(series)
        frames: list[pd.DataFrame] = []

        for i in range(0, len(series), 10):
            chunk = series[i : i + 10]
            payload = self._get(
                f"observations/{','.join(chunk)}/json",
                params={"start_date": start_date, "end_date": end_date},
            )
            frames.append(self._parse_observations(payload))

        if not frames:
            return pd.DataFrame(columns=["observation_date", "series_id", "value"])

        out = pd.concat(frames, ignore_index=True)
        log.info("Valet returned %d observations across %d series", len(out), len(series))
        return out

    @staticmethod
    def _parse_observations(payload: dict) -> pd.DataFrame:
        """Flatten Valet's ``{"observations": [{"d": ..., "SERIES": {"v": ...}}]}``."""
        observations = payload.get("observations")
        if observations is None:
            raise ValetError("Valet payload has no 'observations' key")

        records: list[dict] = []
        for row in observations:
            obs_date = row.get("d")
            for key, cell in row.items():
                if key == "d":
                    continue
                # A suppressed or not-yet-published value comes back as "" or null.
                value = cell.get("v") if isinstance(cell, dict) else cell
                if value in (None, ""):
                    continue
                records.append(
                    {"observation_date": obs_date, "series_id": key, "value": float(value)}
                )

        df = pd.DataFrame.from_records(
            records, columns=["observation_date", "series_id", "value"]
        )
        if not df.empty:
            df["observation_date"] = pd.to_datetime(df["observation_date"])
        return df


def fetch_rates(cfg_macro: dict, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch the configured Bank of Canada series and label them by role.

    Returns columns: ``observation_date``, ``metric``, ``series_id``, ``value``,
    ``source``.
    """
    boc_cfg = cfg_macro["bank_of_canada"]
    series_map = boc_cfg["series"]          # metric -> series_id
    inverse = {sid: metric for metric, sid in series_map.items()}

    client = ValetClient(base_url=boc_cfg["base_url"])
    df = client.observations(series_map.values(), start_date, end_date)

    if df.empty:
        return df.assign(metric=None, source="bank_of_canada")

    df["metric"] = df["series_id"].map(inverse)
    df["source"] = "bank_of_canada"
    return df[["observation_date", "metric", "series_id", "value", "source"]]
