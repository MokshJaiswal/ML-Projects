# Power BI dashboard — build specification

A page-by-page build sheet. Work through it in order and the report will match
the one described in the project README.

> **Why a spec and not a .pbix in the repo?** A `.pbix` is an opaque binary —
> it cannot be diffed, reviewed, or rebuilt by CI. The extracts in
> `data/exports/` plus this spec plus `DAX-measures.md` reproduce the report
> deterministically. Commit your finished `.pbix` alongside them; the spec is
> what makes it reviewable.

---

## Step 1 — Load the data

1. **Get Data → Parquet** → `data/exports/` → load all eight files.
   (CSV equivalents are exported too if your Power BI build predates the
   Parquet connector.)
2. In **Model view**, delete every relationship Power BI auto-detected. Auto
   detection reliably guesses wrong on a star schema with multiple date-like
   columns.
3. Create these relationships by hand — all **one-to-many, single direction**,
   from dimension to fact:

| From (1 side) | Column | To (many side) | Column |
|---|---|---|---|
| `dim_date` | `date_key` | `fact_account_month` | `date_key` |
| `dim_account` | `account_key` | `fact_account_month` | `account_key` |
| `dim_borrower` | `borrower_key` | `fact_account_month` | `borrower_key` |
| `dim_product` | `product_key` | `fact_account_month` | `product_key` |
| `dim_geography` | `geography_key` | `fact_account_month` | `geography_key` |
| `dim_account` | `account_key` | `agg_renewal_exposure` | `account_key` |
| `dim_product` | `product_key` | `agg_renewal_exposure` | `product_key` |

4. Select `dim_date` → **Table tools → Mark as date table** → `date_key`.
   Time-intelligence measures return blank without this.
5. Hide every `*_key` column from report view (right-click → Hide in report
   view). Report users should never see a surrogate key.
6. Set `dim_product[display_order]` as the **Sort by column** for
   `product_name`, so products appear in a sensible order rather than
   alphabetically.

## Step 2 — Add the measures

Create an empty table named `_Measures` (Home → Enter Data → name it →
Load), then add every measure from `DAX-measures.md`. Delete the placeholder
`Column1` afterwards. Apply the number formats from the table at the end of
that file.

---

## Page 1 — Executive Summary

**Question it answers:** how big is the book, how is it performing, and what is
coming at us?

| Position | Visual | Fields |
|---|---|---|
| Top strip | 5 × KPI card | `Total Exposure`, `Delinquency Rate`, `Impaired Rate`, `Expected Loss`, `At-Risk Exposure` |
| Under each card | Trend sparkline | Add `dim_date[date_month]` to the card's sparkline slot |
| Left, mid | Line + clustered column | Axis `dim_date[month_label]`; column `Total Exposure`; line `Delinquency Rate` on the secondary axis |
| Right, mid | Stacked bar | Axis `dim_product[product_name]`; values `Total Exposure`; legend `dim_account[credit_risk_band]` |
| Bottom left | Filled map | Location `dim_geography[province_code]`; colour saturation `Delinquency Rate` |
| Bottom right | Card (large text) | `Renewal Headline` |
| Footer | Card | `DQ Status` — conditional formatting: green on "ALL CHECKS PASSED", amber on warnings, red on failure |
| Footer | Card | `Provenance Note` |

Slicers (sync across all pages): `dim_date[date_month]` (between),
`dim_product[product_name]`, `dim_geography[province_code]`,
`dim_account[credit_risk_band]`.

## Page 2 — The Renewal Cliff

**Question it answers:** when does the repricing wave hit, how hard, and who
does it hit?

| Position | Visual | Fields |
|---|---|---|
| Top | 4 × KPI card | `Renewing Exposure`, `Severe Shock Exposure`, `Avg Payment Shock`, `Annual Payment Increase` |
| Left, large | Clustered column + line | Axis `agg_renewal_exposure[renewal_quarter]`; column `Renewing Exposure`; line `Avg Payment Shock` on secondary axis |
| Right, top | 100% stacked bar | Axis `dim_account[origination_rate_era]`; legend `projected_shock_band`; values `Renewing Exposure` |
| Right, mid | Matrix | Rows `credit_risk_band`; columns `projected_shock_band`; values `Renewing Exposure` with a background colour scale |
| Bottom | Scatter | X `projected_payment_shock_pct`; Y `payment_increase_cad`; size `balance_cad`; legend `province_code`; details `account_id` |

Add a **drill-through page** filtered on `account_id` showing the account's
full monthly history from `fact_account_month`. Credit reviewers always ask to
see the individual file behind an aggregate.

## Page 3 — Regional & Segment Risk

| Position | Visual | Fields |
|---|---|---|
| Left | Filled map | Location `cma_name`; colour `Severe Shock Share`; tooltip `Renewing Exposure`, `latest_unemployment_rate_pct` |
| Right, top | Scatter | X `latest_unemployment_rate_pct`; Y `Delinquency Rate`; size `Total Exposure`; legend `region_name` |
| Right, bottom | Decomposition tree | Analyse `At-Risk Exposure`; explain by `province_code` → `product_name` → `credit_risk_band` → `income_band` |
| Bottom | Table | `cma_name`, `Renewing Exposure`, `Severe Shock Share`, `Avg Payment Shock`, `Delinquency Rate`, `Expected Loss Rate` — with data bars on the rate columns |

## Page 4 — Portfolio Performance Detail

| Position | Visual | Fields |
|---|---|---|
| Top | Ribbon chart | Axis `dim_date[month_label]`; legend `delinquency_state`; values `Total Exposure` |
| Mid left | Line | Axis `months_on_book`; legend `origination_vintage_year`; values `Delinquency Rate` — vintage curves, the standard credit view |
| Mid right | Line | Axis `dim_date[month_label]`; values `avg_interest_rate_pct` and the macro `conventional_5y_rate_pct` |
| Bottom | Matrix | Rows `origination_rate_era` → `product_name`; values `Account Count`, `Total Exposure`, `Delinquency Rate`, `Delinquency Rate MoM (bps)` |

## Page 5 — Data Quality & Lineage

Most portfolio dashboards skip this page. Including it is the single cheapest
way to signal that you think about data the way a bank does.

| Position | Visual | Fields |
|---|---|---|
| Top | KPI cards | `DQ Pass Rate`, `DQ Rules Total`, `DQ Status` |
| Left | Table | `rule_name`, `dimension`, `severity`, `metric_value`, `threshold`, `passed` — conditional icons on `passed` |
| Right | Line | Axis `run_timestamp_utc`; values `DQ Pass Rate` — quality as a time series |
| Bottom | Image | Screenshot of the dbt lineage graph (`make docs`) |
| Bottom | Text box | Source provenance: which macro series came from Bank of Canada / Statistics Canada, and that the loan-level portfolio is simulated |

---

## Performance notes

`fact_account_month` is roughly 3 million rows — comfortable for Power BI's
in-memory engine, but a few habits keep it fast:

- Build page-level visuals on `agg_portfolio_monthly` where the grain allows;
  reserve `fact_account_month` for drill-through and the vintage curves.
- Never put a high-cardinality column (`account_id`, `borrower_id`) on a visual
  axis. Use them in drill-through only.
- Prefer `DIVIDE()` over the `/` operator — it handles divide-by-zero without a
  wrapping `IF`.
- Avoid bidirectional filtering. It is the most common cause of both wrong
  numbers and slow reports in models like this one.

## Accessibility

- Do not encode meaning in colour alone. The delinquency state visuals should
  carry a label or pattern as well as a hue.
- Check contrast on the conditional formatting — the default Power BI red on a
  white card fails WCAG AA at small text sizes.
- Set alt text on every visual (Format → General → Alt text).
- Set a sensible tab order per page (View → Selection → Tab order).
