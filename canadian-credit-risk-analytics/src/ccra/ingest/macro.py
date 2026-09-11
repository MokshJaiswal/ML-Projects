"""Macro layer: fetch real Canadian macro data, or fall back to a labelled scenario.

Provenance is tracked explicitly. Every row carries a ``source`` column and the
run writes a manifest recording which mode produced the data, so no downstream
consumer can mistake a simulated scenario for published statistics.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ccra.ingest.boc_valet import ValetError, fetch_rates
from ccra.ingest.statcan_wds import WDSError, fetch_indicators
from ccra.logging_setup import get_logger, stage

log = get_logger("ccra.ingest.macro")

# Province -> StatCan GEO label, so the two sources join on a common key.
PROVINCE_GEO = {
    "ON": "Ontario",
    "BC": "British Columbia",
    "AB": "Alberta",
    "QC": "Quebec",
    "MB": "Manitoba",
    "SK": "Saskatchewan",
    "NS": "Nova Scotia",
    "NB": "New Brunswick",
}


def _month_index(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(start=start, end=end, freq="MS")


def synthetic_scenario(cfg, provinces: list[str]) -> pd.DataFrame:
    """Generate a labelled synthetic macro scenario.

    This is NOT Canadian macro data. It is a deterministic stress scenario used
    when the live APIs are unreachable (offline CI, restricted network) so the
    rest of the pipeline stays runnable and testable. Its shape mirrors a
    tightening-then-easing cycle: rates climb, plateau, then drift down while
    unemployment rises with a lag.

    Every row is stamped ``source='synthetic_scenario'``.
    """
    window = cfg.window
    months = _month_index(window["observation_start"], window["forecast_end"])
    rng = np.random.default_rng(cfg.portfolio["seed"])
    n = len(months)
    t = np.arange(n)

    # Tightening cycle: rise to a plateau around month 18, then ease.
    peak = max(int(n * 0.45), 1)
    policy = np.where(
        t <= peak,
        0.25 + 4.75 * (t / peak),
        5.00 - 2.00 * ((t - peak) / max(n - peak, 1)),
    )
    policy = np.clip(policy, 0.25, 5.25)

    rows: list[pd.DataFrame] = []

    # National rate series carry geo='Canada'.
    for metric, offset in (
        ("policy_rate", 0.0),
        ("prime_rate", 2.20),
        ("gov_5y_yield", -0.55),
        ("conventional_5y", 1.35),
    ):
        noise = rng.normal(0, 0.04, n).cumsum() * 0.15
        rows.append(
            pd.DataFrame(
                {
                    "observation_date": months,
                    "geo": "Canada",
                    "metric": metric,
                    "value": np.round(np.clip(policy + offset + noise, 0.05, None), 3),
                    "source": "synthetic_scenario",
                }
            )
        )

    # Provincial unemployment: base level + lagged response to the rate cycle.
    base_unemployment = {
        "ON": 6.2, "BC": 5.6, "AB": 7.1, "QC": 5.1,
        "MB": 5.4, "SK": 5.3, "NS": 6.5, "NB": 7.0,
    }
    lag = 9
    rate_impulse = np.concatenate([np.zeros(lag), policy[:-lag]]) if n > lag else np.zeros(n)

    for prov in provinces:
        base = base_unemployment.get(prov, 6.0)
        series = base + 0.28 * (rate_impulse - rate_impulse.mean()) + rng.normal(0, 0.12, n)
        rows.append(
            pd.DataFrame(
                {
                    "observation_date": months,
                    "geo": PROVINCE_GEO.get(prov, prov),
                    "metric": "unemployment_rate",
                    "value": np.round(np.clip(series, 2.5, 14.0), 2),
                    "source": "synthetic_scenario",
                }
            )
        )

        # House price index, 2019=100, cooling as rates bite.
        hpi = 145 - 12 * (rate_impulse / 5.0) + rng.normal(0, 0.9, n).cumsum() * 0.25
        rows.append(
            pd.DataFrame(
                {
                    "observation_date": months,
                    "geo": PROVINCE_GEO.get(prov, prov),
                    "metric": "new_housing_price_index",
                    "value": np.round(np.clip(hpi, 80, 220), 2),
                    "source": "synthetic_scenario",
                }
            )
        )

    return pd.concat(rows, ignore_index=True)


def build_macro(cfg) -> tuple[pd.DataFrame, dict]:
    """Assemble the macro table, preferring live sources.

    Returns ``(frame, manifest)``. The manifest records, per source, whether the
    live fetch succeeded and why it did not.
    """
    provinces = list(cfg.portfolio["regions"])
    window = cfg.window
    start, end = window["observation_start"], window["forecast_end"]
    macro_cfg = cfg.macro

    manifest: dict = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "window": {"start": start, "end": end},
        "sources": {},
    }

    frames: list[pd.DataFrame] = []
    live_ok = True

    if macro_cfg.get("use_live_sources", True):
        # -- Bank of Canada -------------------------------------------------
        try:
            boc = fetch_rates(macro_cfg, start, end)
            boc["geo"] = "Canada"
            frames.append(boc[["observation_date", "geo", "metric", "value", "source"]])
            manifest["sources"]["bank_of_canada"] = {"status": "live", "rows": len(boc)}
        except (ValetError, Exception) as exc:   # noqa: BLE001 - we record and degrade
            live_ok = False
            manifest["sources"]["bank_of_canada"] = {"status": "failed", "error": str(exc)[:400]}
            log.warning("Bank of Canada fetch failed: %s", exc)

        # -- Statistics Canada ---------------------------------------------
        try:
            sc = fetch_indicators(macro_cfg, start, end)
            geos = set(PROVINCE_GEO[p] for p in provinces if p in PROVINCE_GEO)
            sc = sc[sc["geo"].isin(geos | {"Canada"})]
            frames.append(sc)
            manifest["sources"]["statcan"] = {"status": "live", "rows": len(sc)}
        except (WDSError, Exception) as exc:     # noqa: BLE001
            live_ok = False
            manifest["sources"]["statcan"] = {"status": "failed", "error": str(exc)[:400]}
            log.warning("Statistics Canada fetch failed: %s", exc)
    else:
        manifest["sources"]["live"] = {"status": "disabled_by_config"}
        live_ok = False

    if not live_ok or not frames:
        if not macro_cfg.get("fallback_to_synthetic", True):
            raise RuntimeError(
                "Live macro sources unavailable and macro.fallback_to_synthetic is false."
            )
        log.warning(
            "Using the SYNTHETIC macro scenario. Rows are stamped "
            "source='synthetic_scenario' - they are not published statistics."
        )
        frames.append(synthetic_scenario(cfg, provinces))
        manifest["sources"]["synthetic_scenario"] = {"status": "used_as_fallback"}

    macro = pd.concat(frames, ignore_index=True)
    macro = macro.drop_duplicates(subset=["observation_date", "geo", "metric"], keep="last")
    macro = macro.sort_values(["metric", "geo", "observation_date"]).reset_index(drop=True)

    manifest["row_count"] = len(macro)
    manifest["mode"] = "live" if live_ok else "synthetic_fallback"
    manifest["metrics"] = sorted(macro["metric"].unique().tolist())
    return macro, manifest


def run(cfg) -> pd.DataFrame:
    """Stage entry point: build the macro table and persist it with its manifest."""
    with stage(log, "ingest_macro") as st:
        macro, manifest = build_macro(cfg)

        raw_dir = Path(cfg.path("raw"))
        raw_dir.mkdir(parents=True, exist_ok=True)

        macro.to_parquet(raw_dir / "macro.parquet", index=False)
        (raw_dir / "macro_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        st["rows"] = len(macro)
        st["mode"] = manifest["mode"]
        st["metrics"] = len(manifest["metrics"])
    return macro
