"""Data quality gate.

Every Canadian analyst posting in the finance sector asks for some version of
"monitor data quality, identify anomalies, investigate discrepancies" and
"perform reconciliation to ensure completeness and accuracy between source and
target". This module is that, made executable: a suite of declarative rules run
against the warehouse, with results persisted so quality is itself a time
series you can chart.

Severity ``error`` fails the run (non-zero exit). Severity ``warn`` is recorded
and surfaced on the dashboard but does not block.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import duckdb
import pandas as pd

from ccra.logging_setup import get_logger, stage
from ccra.warehouse.load import connect

log = get_logger("ccra.quality")

Severity = Literal["error", "warn"]


@dataclass
class Rule:
    """A single quality assertion.

    ``sql`` must return exactly one row with a numeric column ``metric``. The
    rule passes when ``metric <= threshold`` (or ``>=`` when ``direction`` is
    ``"min"``).
    """

    name: str
    dimension: str                # completeness | uniqueness | validity | consistency | reconciliation
    sql: str
    threshold: float
    severity: Severity = "error"
    direction: Literal["max", "min"] = "max"
    description: str = ""

    def evaluate(self, con: duckdb.DuckDBPyConnection) -> dict:
        metric = con.execute(self.sql).fetchone()[0]
        metric = float(metric if metric is not None else 0.0)
        passed = metric <= self.threshold if self.direction == "max" else metric >= self.threshold
        return {
            "rule_name": self.name,
            "dimension": self.dimension,
            "severity": self.severity,
            "metric_value": round(metric, 6),
            "threshold": self.threshold,
            "direction": self.direction,
            "passed": bool(passed),
            "description": self.description,
        }


def build_rules(cfg) -> list[Rule]:
    """Construct the rule suite from configured thresholds."""
    q = cfg.quality
    tol = float(q["reconciliation_tolerance"])

    return [
        # -- completeness ------------------------------------------------
        Rule(
            name="account_month_no_null_keys",
            dimension="completeness",
            sql="""SELECT coalesce(sum(CASE WHEN account_id IS NULL
                                             OR snapshot_month IS NULL THEN 1 ELSE 0 END)
                                   / nullif(count(*), 0), 0)
                   FROM landing.raw_account_month""",
            threshold=float(q["max_null_rate"]),
            description="Fact grain keys must never be null.",
        ),
        Rule(
            name="account_month_min_row_count",
            dimension="completeness",
            sql="SELECT count(*) FROM landing.raw_account_month",
            threshold=float(q["min_row_count"]),
            direction="min",
            description="Guards against a silently truncated simulation run.",
        ),
        Rule(
            name="borrower_no_null_province",
            dimension="completeness",
            sql="""SELECT coalesce(sum(CASE WHEN province_code IS NULL THEN 1 ELSE 0 END)
                                   / nullif(count(*), 0), 0)
                   FROM landing.raw_borrowers""",
            threshold=float(q["max_null_rate"]),
            description="Every borrower must carry a province for regional reporting.",
        ),

        # -- uniqueness --------------------------------------------------
        Rule(
            name="account_month_grain_unique",
            dimension="uniqueness",
            sql="""SELECT coalesce((count(*) - count(DISTINCT (account_id, snapshot_month)))
                                   / nullif(count(*), 0), 0)
                   FROM landing.raw_account_month""",
            threshold=float(q["max_duplicate_rate"]),
            description="One row per account per month. A duplicate double-counts exposure.",
        ),
        Rule(
            name="account_id_unique",
            dimension="uniqueness",
            sql="""SELECT coalesce((count(*) - count(DISTINCT account_id))
                                   / nullif(count(*), 0), 0)
                   FROM landing.raw_accounts""",
            threshold=float(q["max_duplicate_rate"]),
            description="Account dimension primary key.",
        ),

        # -- validity ----------------------------------------------------
        Rule(
            name="no_negative_balances",
            dimension="validity",
            sql="""SELECT coalesce(sum(CASE WHEN balance_cad < 0 THEN 1 ELSE 0 END)
                                   / nullif(count(*), 0), 0)
                   FROM landing.raw_account_month""",
            threshold=0.0,
            description="A negative outstanding balance is never valid.",
        ),
        Rule(
            name="interest_rate_in_plausible_range",
            dimension="validity",
            sql="""SELECT coalesce(sum(CASE WHEN interest_rate_pct < 0
                                             OR interest_rate_pct > 35 THEN 1 ELSE 0 END)
                                   / nullif(count(*), 0), 0)
                   FROM landing.raw_account_month""",
            threshold=0.0,
            description="Rates outside 0-35% indicate a repricing defect.",
        ),
        Rule(
            name="credit_score_in_range",
            dimension="validity",
            sql="""SELECT coalesce(sum(CASE WHEN credit_score_at_origination NOT BETWEEN 300 AND 900
                                       THEN 1 ELSE 0 END) / nullif(count(*), 0), 0)
                   FROM landing.raw_borrowers""",
            threshold=0.0,
            description="Credit scores must sit inside the Canadian 300-900 range.",
        ),

        # -- consistency (referential integrity) -------------------------
        Rule(
            name="account_month_orphan_rate",
            dimension="consistency",
            sql="""SELECT coalesce(sum(CASE WHEN a.account_id IS NULL THEN 1 ELSE 0 END)
                                   / nullif(count(*), 0), 0)
                   FROM landing.raw_account_month m
                   LEFT JOIN landing.raw_accounts a USING (account_id)""",
            threshold=0.0,
            description="Every fact row must resolve to an account.",
        ),
        Rule(
            name="account_orphan_borrower_rate",
            dimension="consistency",
            sql="""SELECT coalesce(sum(CASE WHEN b.borrower_id IS NULL THEN 1 ELSE 0 END)
                                   / nullif(count(*), 0), 0)
                   FROM landing.raw_accounts a
                   LEFT JOIN landing.raw_borrowers b USING (borrower_id)""",
            threshold=0.0,
            description="Every account must resolve to a borrower.",
        ),

        # -- reconciliation ----------------------------------------------
        Rule(
            name="opening_balance_reconciles_to_origination",
            dimension="reconciliation",
            sql="""
                WITH first_obs AS (
                    SELECT m.account_id, m.balance_cad,
                           row_number() OVER (PARTITION BY m.account_id
                                              ORDER BY m.snapshot_month) AS rn
                    FROM landing.raw_account_month m
                    JOIN landing.raw_accounts a USING (account_id)
                    WHERE date_trunc('month', a.origination_date)
                          = date_trunc('month', m.snapshot_month)
                )
                SELECT coalesce(abs(sum(f.balance_cad) - sum(a.original_balance_cad))
                                / nullif(sum(a.original_balance_cad), 0), 0)
                FROM first_obs f
                JOIN landing.raw_accounts a USING (account_id)
                WHERE f.rn = 1
            """,
            threshold=tol,
            description=(
                "Accounts observed in their origination month should still carry "
                "close to their original balance. Detects a break between the "
                "account dimension and the monthly fact."
            ),
        ),
        Rule(
            name="exposure_continuity_month_over_month",
            dimension="reconciliation",
            sql="""
                WITH monthly AS (
                    SELECT snapshot_month, sum(balance_cad) AS exposure
                    FROM landing.raw_account_month GROUP BY 1
                ),
                delta AS (
                    SELECT snapshot_month, exposure,
                           lag(exposure) OVER (ORDER BY snapshot_month) AS prior
                    FROM monthly
                )
                SELECT coalesce(max(abs(exposure - prior) / nullif(prior, 0)), 0)
                FROM delta WHERE prior IS NOT NULL
            """,
            threshold=0.35,
            severity="warn",
            description=(
                "Total exposure should not jump more than 35% month over month. "
                "A spike usually means a load ran twice or a vintage was dropped."
            ),
        ),
        Rule(
            name="macro_coverage_complete",
            dimension="completeness",
            sql="""
                WITH need AS (SELECT DISTINCT snapshot_month FROM landing.raw_account_month),
                     have AS (SELECT DISTINCT observation_date FROM landing.raw_macro
                              WHERE metric = 'conventional_5y')
                SELECT coalesce(sum(CASE WHEN h.observation_date IS NULL THEN 1 ELSE 0 END)
                                / nullif(count(*), 0), 0)
                FROM need n LEFT JOIN have h ON n.snapshot_month = h.observation_date
            """,
            threshold=0.0,
            description="Every reporting month needs a market rate to reprice against.",
        ),
    ]


def run(cfg) -> pd.DataFrame:
    """Execute the suite, persist results, and fail the run on an error breach."""
    with stage(log, "data_quality") as st:
        con = connect(cfg)
        run_ts = datetime.now(timezone.utc)
        try:
            results = [rule.evaluate(con) for rule in build_rules(cfg)]
            df = pd.DataFrame(results)
            df.insert(0, "run_timestamp_utc", run_ts)

            con.execute("CREATE SCHEMA IF NOT EXISTS quality")
            con.register("dq_results", df)
            con.execute(
                "CREATE TABLE IF NOT EXISTS quality.dq_results AS "
                "SELECT * FROM dq_results WHERE 1=0"
            )
            con.execute("INSERT INTO quality.dq_results SELECT * FROM dq_results")
        finally:
            con.close()

        exports = Path(cfg.path("exports"))
        exports.mkdir(parents=True, exist_ok=True)
        df.to_csv(exports / "data_quality_results.csv", index=False)

        failures = df[~df["passed"]]
        errors = failures[failures["severity"] == "error"]
        warns = failures[failures["severity"] == "warn"]

        for _, row in failures.iterrows():
            log.log(
                40 if row["severity"] == "error" else 30,
                "DQ %s | %s | metric=%s threshold=%s",
                row["severity"].upper(), row["rule_name"],
                row["metric_value"], row["threshold"],
            )

        st["rules"] = len(df)
        st["passed"] = int(df["passed"].sum())
        st["warnings"] = len(warns)
        st["errors"] = len(errors)

        if not errors.empty:
            raise SystemExit(
                f"Data quality gate failed: {len(errors)} error-severity rule(s) breached "
                f"({', '.join(errors['rule_name'])})."
            )
    return df
