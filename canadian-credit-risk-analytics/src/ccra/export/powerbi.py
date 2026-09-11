"""Export warehouse marts to files Power BI can consume.

Power BI Desktop reads Parquet natively through the Folder / Parquet connector,
and CSV as a universal fallback. Exporting both means the .pbix can be rebuilt
on any machine without a live database connection, which is what makes the
dashboard reproducible for a reviewer who just clones the repo.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from ccra.logging_setup import get_logger, stage
from ccra.warehouse.load import connect

log = get_logger("ccra.export")

# dbt writes marts to <profile target schema>_<model schema>. With the default
# DuckDB profile that is `main_marts`.
MART_SCHEMA = "main_marts"

# Mart tables built by dbt. Exported in dependency order.
EXPORT_TABLES = [
    "dim_date",
    "dim_borrower",
    "dim_account",
    "dim_geography",
    "dim_product",
    "fact_account_month",
    "agg_portfolio_monthly",
    "agg_renewal_exposure",
]


def _table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    return bool(
        con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name = ? AND table_schema = ?",
            [name, MART_SCHEMA],
        ).fetchone()[0]
    )


def run(cfg) -> dict[str, int]:
    """Stage entry point: write each mart to Parquet and CSV."""
    exports = Path(cfg.path("exports"))
    exports.mkdir(parents=True, exist_ok=True)

    written: dict[str, int] = {}
    with stage(log, "export_powerbi") as st:
        con = connect(cfg)
        try:
            missing = [t for t in EXPORT_TABLES if not _table_exists(con, t)]
            if missing:
                log.warning(
                    "Mart tables not found: %s. Run `dbt build` before exporting.",
                    ", ".join(missing),
                )
            for table in EXPORT_TABLES:
                if table in missing:
                    continue
                pq = exports / f"{table}.parquet"
                csv = exports / f"{table}.csv"
                con.execute(f"COPY (SELECT * FROM {MART_SCHEMA}.{table}) TO '{pq.as_posix()}' (FORMAT PARQUET)")
                con.execute(f"COPY (SELECT * FROM {MART_SCHEMA}.{table}) TO '{csv.as_posix()}' (HEADER, DELIMITER ',')")
                n = con.execute(f"SELECT count(*) FROM {MART_SCHEMA}.{table}").fetchone()[0]
                written[table] = n
                log.info("exported %-26s %10d rows", table, n)
        finally:
            con.close()

        st["tables"] = len(written)
        st["rows"] = sum(written.values())
    return written
