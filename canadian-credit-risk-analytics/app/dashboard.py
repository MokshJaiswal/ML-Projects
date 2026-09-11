"""Streamlit view of the CCRA portfolio.

This exists so the analysis is viewable by someone without a Power BI licence.
The Power BI report is the primary deliverable; this mirrors its first two pages
and is deployable to Streamlit Community Cloud for free.

Run with:  make dashboard
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "warehouse" / "ccra.duckdb"
MANIFEST = REPO / "data" / "raw" / "macro_manifest.json"

st.set_page_config(page_title="CCRA — Canadian Credit Risk Analytics",
                   page_icon="📊", layout="wide")


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    if not DB.exists():
        st.error(f"Warehouse not found at {DB}. Run `make all` first.")
        st.stop()
    return duckdb.connect(str(DB), read_only=True)


@st.cache_data(ttl=300)
def query(sql: str) -> pd.DataFrame:
    return get_connection().execute(sql).df()


def money(x: float) -> str:
    """Format CAD at a sensible magnitude."""
    if abs(x) >= 1e9:
        return f"${x / 1e9:,.2f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.1f}M"
    return f"${x:,.0f}"


# --- trust banner: quality and provenance before any figure ----------------
def render_trust_banner() -> None:
    dq = query("""
        SELECT rule_name, dimension, severity, metric_value, threshold, passed
        FROM quality.dq_results
        WHERE run_timestamp_utc = (SELECT max(run_timestamp_utc) FROM quality.dq_results)
    """)
    failed_err = dq[(~dq.passed) & (dq.severity == "error")]
    failed_warn = dq[(~dq.passed) & (dq.severity == "warn")]

    mode = "unknown"
    if MANIFEST.exists():
        mode = json.loads(MANIFEST.read_text()).get("mode", "unknown")

    left, right = st.columns([3, 2])
    with left:
        if len(failed_err):
            st.error(f"Data quality FAILED — {len(failed_err)} error-severity rule(s) breached: "
                     f"{', '.join(failed_err.rule_name)}. Figures below should not be relied on.")
        elif len(failed_warn):
            st.warning(f"Data quality passed with {len(failed_warn)} warning(s): "
                       f"{', '.join(failed_warn.rule_name)}")
        else:
            st.success(f"Data quality: all {len(dq)} rules passed")
    with right:
        if mode == "live":
            st.info("Macro source: live (Bank of Canada + Statistics Canada)")
        else:
            st.warning("Macro source: **synthetic scenario** — generated stress path, "
                       "not published statistics. Loan-level data is simulated in all modes.")


st.title("Canadian Credit Risk Analytics")
st.caption("Retail mortgage renewal shock — exposure, segmentation and provision impact")
render_trust_banner()

page = st.sidebar.radio("Page", ["Executive summary", "The renewal cliff",
                                 "Regional & segment risk", "Data quality"])

# ---------------------------------------------------------------------------
if page == "Executive summary":
    kpi = query("""
        SELECT sum(f.balance_cad) AS exposure,
               sum(f.delinquent_balance_cad) / nullif(sum(f.balance_cad), 0) AS delinq_rate,
               sum(f.impaired_balance_cad)   / nullif(sum(f.balance_cad), 0) AS impaired_rate,
               sum(f.expected_loss_cad) AS expected_loss,
               count(*) AS accounts
        FROM main_marts.fact_account_month f
        JOIN main_marts.dim_date d ON d.date_key = f.date_key
        WHERE d.is_current_month
    """).iloc[0]

    c = st.columns(5)
    c[0].metric("Total exposure", money(kpi.exposure))
    c[1].metric("Accounts", f"{kpi.accounts:,.0f}")
    c[2].metric("Delinquency rate", f"{kpi.delinq_rate:.3%}")
    c[3].metric("Impaired rate", f"{kpi.impaired_rate:.3%}")
    c[4].metric("Expected loss", money(kpi.expected_loss))

    trend = query("""
        SELECT d.date_key AS month,
               sum(f.balance_cad) AS exposure,
               sum(f.delinquent_balance_cad) / nullif(sum(f.balance_cad), 0) AS delinq_rate
        FROM main_marts.fact_account_month f
        JOIN main_marts.dim_date d ON d.date_key = f.date_key
        GROUP BY 1 ORDER BY 1
    """)
    fig = go.Figure()
    fig.add_bar(x=trend.month, y=trend.exposure, name="Exposure", marker_color="#4C78A8")
    fig.add_scatter(x=trend.month, y=trend.delinq_rate, name="Delinquency rate",
                    yaxis="y2", line=dict(color="#E45756", width=3))
    fig.update_layout(
        title="Exposure and delinquency over time", height=420,
        yaxis=dict(title="Exposure (CAD)"),
        yaxis2=dict(title="Delinquency rate", overlaying="y", side="right", tickformat=".2%"),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)
    with left:
        by_product = query("""
            SELECT p.product_name, a.credit_risk_band, sum(f.balance_cad) AS exposure
            FROM main_marts.fact_account_month f
            JOIN main_marts.dim_date d ON d.date_key = f.date_key
            JOIN main_marts.dim_product p ON p.product_key = f.product_key
            JOIN main_marts.dim_account a ON a.account_key = f.account_key
            WHERE d.is_current_month GROUP BY 1, 2
        """)
        st.plotly_chart(
            px.bar(by_product, x="exposure", y="product_name", color="credit_risk_band",
                   orientation="h", title="Exposure by product and credit band",
                   labels={"exposure": "Exposure (CAD)", "product_name": ""}),
            use_container_width=True)
    with right:
        by_prov = query("""
            SELECT a.province_code,
                   sum(f.balance_cad) AS exposure,
                   sum(f.delinquent_balance_cad)/nullif(sum(f.balance_cad),0) AS delinq_rate
            FROM main_marts.fact_account_month f
            JOIN main_marts.dim_date d ON d.date_key = f.date_key
            JOIN main_marts.dim_account a ON a.account_key = f.account_key
            WHERE d.is_current_month GROUP BY 1 ORDER BY exposure DESC
        """)
        st.plotly_chart(
            px.bar(by_prov, x="province_code", y="exposure", color="delinq_rate",
                   color_continuous_scale="Reds", title="Exposure and delinquency by province",
                   labels={"exposure": "Exposure (CAD)", "delinq_rate": "Delinquency"}),
            use_container_width=True)

# ---------------------------------------------------------------------------
elif page == "The renewal cliff":
    kpi = query("""
        SELECT sum(balance_cad) AS renewing,
               sum(CASE WHEN projected_shock_band = 'SEVERE_OVER_40' THEN balance_cad ELSE 0 END) AS severe,
               sum(projected_payment_shock_pct * balance_cad)/nullif(sum(balance_cad),0) AS avg_shock,
               sum(CASE WHEN payment_increase_cad > 0 THEN payment_increase_cad ELSE 0 END)*12 AS annual_increase,
               count(*) FILTER (WHERE projected_shock_band = 'SEVERE_OVER_40') AS severe_n
        FROM main_marts.agg_renewal_exposure
    """).iloc[0]

    c = st.columns(4)
    c[0].metric("Exposure yet to reprice", money(kpi.renewing))
    c[1].metric("Severe shock (>40%)", money(kpi.severe), f"{kpi.severe_n:,.0f} accounts")
    c[2].metric("Avg payment shock", f"{kpi.avg_shock:.1%}", help="Exposure-weighted")
    c[3].metric("Added annual payments", money(kpi.annual_increase))

    sched = query("""
        SELECT renewal_quarter, sum(balance_cad) AS exposure,
               sum(projected_payment_shock_pct * balance_cad)/nullif(sum(balance_cad),0) AS avg_shock
        FROM main_marts.agg_renewal_exposure
        WHERE renewal_quarter IS NOT NULL GROUP BY 1 ORDER BY 1
    """)
    fig = go.Figure()
    fig.add_bar(x=sched.renewal_quarter, y=sched.exposure, name="Exposure repricing",
                marker_color="#4C78A8")
    fig.add_scatter(x=sched.renewal_quarter, y=sched.avg_shock, name="Avg payment shock",
                    yaxis="y2", line=dict(color="#E45756", width=3))
    fig.update_layout(title="Repricing schedule and payment shock by quarter", height=440,
                      yaxis=dict(title="Exposure (CAD)"),
                      yaxis2=dict(title="Avg shock", overlaying="y", side="right", tickformat=".0%"),
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Who carries the shock")
    st.caption(
        "The severe-shock cohort is almost entirely prime. The deepest shock belongs "
        "to whoever borrowed at the cheapest rate, and the cheapest rates went to the "
        "strongest credits — so credit-score-based early warning misses this population."
    )
    mix = query("""
        SELECT projected_shock_band, credit_risk_band,
               sum(balance_cad) AS exposure, count(*) AS accounts
        FROM main_marts.agg_renewal_exposure GROUP BY 1, 2
    """)
    order = ["NONE_OR_BENEFIT", "MILD_0_10", "MODERATE_10_25", "HIGH_25_40", "SEVERE_OVER_40"]
    st.plotly_chart(
        px.bar(mix, x="projected_shock_band", y="exposure", color="credit_risk_band",
               category_orders={"projected_shock_band": order},
               title="Exposure by shock band and credit band",
               labels={"exposure": "Exposure (CAD)", "projected_shock_band": ""}),
        use_container_width=True)

    st.subheader("Prioritised outreach list")
    outreach = query("""
        SELECT account_id, province_code, cma_name, credit_risk_band,
               renewal_date, round(balance_cad) AS balance_cad,
               round(current_payment_cad) AS current_payment,
               round(projected_payment_cad) AS projected_payment,
               round(payment_increase_cad) AS monthly_increase,
               round(projected_payment_shock_pct, 3) AS shock_pct
        FROM main_marts.agg_renewal_exposure
        WHERE projected_shock_band = 'SEVERE_OVER_40'
        ORDER BY payment_increase_cad DESC LIMIT 250
    """)
    st.dataframe(outreach, use_container_width=True, height=340)
    st.download_button("Download full severe-shock list (CSV)",
                       outreach.to_csv(index=False), "severe_shock_outreach.csv", "text/csv")

# ---------------------------------------------------------------------------
elif page == "Regional & segment risk":
    regional = query("""
        SELECT province_code,
               sum(balance_cad) AS renewing,
               sum(CASE WHEN projected_shock_band = 'SEVERE_OVER_40' THEN balance_cad ELSE 0 END) AS severe,
               sum(CASE WHEN projected_shock_band = 'SEVERE_OVER_40' THEN balance_cad ELSE 0 END)
                 / nullif(sum(balance_cad), 0) AS severe_share
        FROM main_marts.agg_renewal_exposure GROUP BY 1 ORDER BY severe DESC
    """)
    left, right = st.columns(2)
    left.plotly_chart(
        px.bar(regional, x="province_code", y="severe", title="Severe-shock exposure by province (absolute)",
               labels={"severe": "Exposure (CAD)", "province_code": ""}), use_container_width=True)
    right.plotly_chart(
        px.bar(regional.sort_values("severe_share", ascending=False),
               x="province_code", y="severe_share", title="Severe-shock share of renewing book (relative)",
               labels={"severe_share": "Share", "province_code": ""}), use_container_width=True)
    st.caption(
        "Absolute and relative disagree: Ontario carries the largest dollar exposure, "
        "but a smaller province can carry the higher proportion — a targeting question "
        "that absolute exposure alone answers wrongly."
    )

    st.subheader("Vintage performance curves")
    vintage = query("""
        SELECT f.months_on_book,
               extract(year from a.origination_vintage_year) AS vintage,
               sum(f.delinquent_balance_cad)/nullif(sum(f.balance_cad),0) AS delinq_rate
        FROM main_marts.fact_account_month f
        JOIN main_marts.dim_account a ON a.account_key = f.account_key
        WHERE f.months_on_book <= 60
        GROUP BY 1, 2 HAVING sum(f.balance_cad) > 0 ORDER BY 1
    """)
    vintage["vintage"] = vintage["vintage"].astype(int).astype(str)
    st.plotly_chart(
        px.line(vintage, x="months_on_book", y="delinq_rate", color="vintage",
                title="Delinquency rate by months on book, per origination vintage",
                labels={"delinq_rate": "Delinquency rate", "months_on_book": "Months on book"}),
        use_container_width=True)

# ---------------------------------------------------------------------------
else:
    st.subheader("Data quality — latest run")
    dq = query("""
        SELECT rule_name, dimension, severity, metric_value, threshold, direction,
               passed, description
        FROM quality.dq_results
        WHERE run_timestamp_utc = (SELECT max(run_timestamp_utc) FROM quality.dq_results)
        ORDER BY passed, severity DESC, dimension
    """)
    c = st.columns(3)
    c[0].metric("Rules", len(dq))
    c[1].metric("Passed", int(dq.passed.sum()))
    c[2].metric("Pass rate", f"{dq.passed.mean():.0%}")
    st.dataframe(dq, use_container_width=True)

    st.subheader("Quality over time")
    hist = query("""
        SELECT run_timestamp_utc, avg(CASE WHEN passed THEN 1.0 ELSE 0.0 END) AS pass_rate
        FROM quality.dq_results GROUP BY 1 ORDER BY 1
    """)
    if len(hist) > 1:
        st.plotly_chart(px.line(hist, x="run_timestamp_utc", y="pass_rate",
                                title="Quality pass rate by run"), use_container_width=True)
    else:
        st.info("Quality becomes a time series once the pipeline has run more than once.")

    if MANIFEST.exists():
        st.subheader("Source provenance")
        st.json(json.loads(MANIFEST.read_text()))
