"""Load staged Parquet into the DuckDB warehouse.

DuckDB is the warehouse for a reason worth saying out loud in an interview: it
is a real columnar analytical engine with full ANSI SQL and window functions,
it needs no server, and the same dbt models run unchanged against Snowflake,
BigQuery or Databricks by swapping the adapter. The modelling is portable; only
the connection string is not.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from ccra.logging_setup import get_logger, stage

log = get_logger("ccra.warehouse")

# Landing tables, loaded verbatim from the staged Parquet files. dbt owns
# everything downstream of these.
SOURCE_TABLES = {
    "raw_macro":         "data/raw/macro.parquet",
    "raw_borrowers":     "data/staged/borrowers.parquet",
    "raw_accounts":      "data/staged/accounts.parquet",
    "raw_account_month": "data/staged/account_month.parquet",
}


def connect(cfg) -> duckdb.DuckDBPyConnection:
    """Open the warehouse, creating the file and its directory if needed."""
    db_path = cfg.path("warehouse")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def run(cfg) -> dict[str, int]:
    """Stage entry point: (re)create the landing schema from staged Parquet."""
    from ccra.config import REPO_ROOT

    counts: dict[str, int] = {}
    with stage(log, "load_warehouse") as st:
        con = connect(cfg)
        try:
            con.execute("CREATE SCHEMA IF NOT EXISTS landing")
            for table, rel_path in SOURCE_TABLES.items():
                path = REPO_ROOT / rel_path
                if not path.exists():
                    raise FileNotFoundError(
                        f"staged file missing for {table}: {path}. Run the ingest "
                        f"and simulate stages first."
                    )
                con.execute(f"CREATE OR REPLACE TABLE landing.{table} AS "
                            f"SELECT * FROM read_parquet('{path.as_posix()}')")
                n = con.execute(f"SELECT count(*) FROM landing.{table}").fetchone()[0]
                counts[table] = n
                log.info("loaded landing.%-20s %10d rows", table, n)
        finally:
            con.close()

        st["tables"] = len(counts)
        st["rows"] = sum(counts.values())
    return counts
