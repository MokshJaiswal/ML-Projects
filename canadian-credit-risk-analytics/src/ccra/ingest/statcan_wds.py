"""Statistics Canada Web Data Service (WDS) client.

WDS is public and keyless. Docs: https://www.statcan.gc.ca/en/developers/wds

Two access patterns are useful here:

* ``getFullTableDownloadCSV/{productId}/en`` returns a signed URL to a zipped
  CSV of the whole table. Best for the dimension-heavy tables (LFS by province,
  NHPI by CMA) where we want every coordinate.
* ``getDataFromVectorsAndLatestNPeriods`` fetches specific vectors. Cheaper when
  you already know the exact series, but vector IDs are brittle across table
  revisions, so the full-table path is the default.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

import pandas as pd
import requests

from ccra.logging_setup import get_logger

log = get_logger("ccra.ingest.statcan")

DEFAULT_TIMEOUT = 60
MAX_RETRIES = 4


class WDSError(RuntimeError):
    """Raised when WDS is unreachable or returns a failure status."""


@dataclass
class WDSClient:
    base_url: str = "https://www150.statcan.gc.ca/t1/wds/rest"
    timeout: int = DEFAULT_TIMEOUT
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()
            self.session.headers.update({"User-Agent": "CCRA-pipeline/1.0"})

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Issue a request with bounded exponential backoff."""
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.request(
                    method, url, timeout=self.timeout, **kwargs
                )
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise WDSError(f"transient HTTP {resp.status_code} from {url}")
                resp.raise_for_status()
                return resp
            except (requests.RequestException, WDSError) as exc:
                last_error = exc
                if attempt == MAX_RETRIES - 1:
                    break
                backoff = 2 ** (attempt + 1)
                log.warning(
                    "WDS request failed (attempt %d/%d): %s - retrying in %ds",
                    attempt + 1, MAX_RETRIES, exc, backoff,
                )
                import time
                time.sleep(backoff)
        raise WDSError(f"WDS request to {url} failed after {MAX_RETRIES} attempts: {last_error}")

    def full_table(self, product_id: str) -> pd.DataFrame:
        """Download an entire StatCan table as a DataFrame.

        WDS answers with ``{"status": "SUCCESS", "object": "<zip url>"}``; the
        zip holds ``{product_id}.csv`` plus a metadata CSV we discard.
        """
        meta = self._request(
            "GET", f"{self.base_url}/getFullTableDownloadCSV/{product_id}/en"
        ).json()

        if meta.get("status") != "SUCCESS":
            raise WDSError(f"WDS refused table {product_id}: {meta}")

        zip_url = meta["object"]
        log.info("Downloading StatCan table %s", product_id)
        blob = self._request("GET", zip_url).content

        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            # The data file is the one NOT ending in _MetaData.csv
            names = [
                n for n in zf.namelist()
                if n.lower().endswith(".csv") and "metadata" not in n.lower()
            ]
            if not names:
                raise WDSError(f"no data CSV inside archive for table {product_id}")
            with zf.open(names[0]) as fh:
                df = pd.read_csv(fh, low_memory=False)

        log.info("StatCan table %s -> %d rows, %d columns", product_id, len(df), df.shape[1])
        return df

    @staticmethod
    def tidy(df: pd.DataFrame, metric: str, geo_filter: list[str] | None = None) -> pd.DataFrame:
        """Reduce a raw StatCan table to ``observation_date, geo, metric, value``.

        StatCan tables share a common shape: a ``REF_DATE`` period, a ``GEO``
        label, one or more dimension columns, and a ``VALUE``. We keep only the
        columns every table has so one function serves all four sources.
        """
        required = {"REF_DATE", "GEO", "VALUE"}
        missing = required - set(df.columns)
        if missing:
            raise WDSError(f"StatCan table missing expected columns: {sorted(missing)}")

        out = df[["REF_DATE", "GEO", "VALUE"]].copy()
        out.columns = ["observation_date", "geo", "value"]

        # REF_DATE is YYYY-MM for monthly tables, YYYY-MM-DD for daily.
        out["observation_date"] = pd.to_datetime(
            out["observation_date"], format="mixed", errors="coerce"
        )
        out["value"] = pd.to_numeric(out["value"], errors="coerce")
        out = out.dropna(subset=["observation_date", "value"])

        if geo_filter:
            out = out[out["geo"].isin(geo_filter)]

        out["metric"] = metric
        out["source"] = "statcan"
        return out[["observation_date", "geo", "metric", "value", "source"]]


def fetch_indicators(cfg_macro: dict, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch every configured StatCan table and return one tidy frame."""
    sc_cfg = cfg_macro["statcan"]
    client = WDSClient(base_url=sc_cfg["base_url"])

    frames: list[pd.DataFrame] = []
    for metric, product_id in sc_cfg["tables"].items():
        raw = client.full_table(product_id)
        frames.append(WDSClient.tidy(raw, metric=metric))

    if not frames:
        return pd.DataFrame(columns=["observation_date", "geo", "metric", "value", "source"])

    out = pd.concat(frames, ignore_index=True)
    mask = (out["observation_date"] >= start_date) & (out["observation_date"] <= end_date)
    return out.loc[mask].reset_index(drop=True)
