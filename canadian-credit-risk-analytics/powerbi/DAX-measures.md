# DAX measure library

Paste these into Power BI Desktop as measures on a dedicated `_Measures` table
(Home → Enter Data → create an empty table named `_Measures`, then add each
measure to it). Keeping every measure in one table rather than scattered across
fact tables is the convention that keeps a model navigable as it grows.

## Why these are measures and not columns

Every rate below is a `DIVIDE` of two additive sums. That is deliberate. If the
delinquency rate were stored as a column in the fact table, `AVERAGE` of it
would be an average-of-ratios — wrong the moment anyone slices by province,
product or month, because it weights a $50,000 account the same as a $900,000
one. Computing the ratio at query time from two sums gives the correctly
weighted answer under every filter context.

---

## 1. Base measures — exposure and volume

```dax
Total Exposure =
SUM ( fact_account_month[balance_cad] )

Account Count =
SUM ( fact_account_month[account_count] )

Borrower Count =
DISTINCTCOUNT ( fact_account_month[borrower_key] )

Average Balance =
DIVIDE ( [Total Exposure], [Account Count] )
```

## 2. Credit quality

```dax
Delinquent Balance =
SUM ( fact_account_month[delinquent_balance_cad] )

Impaired Balance =
SUM ( fact_account_month[impaired_balance_cad] )

Defaulted Balance =
SUM ( fact_account_month[defaulted_balance_cad] )

-- Balance-weighted. This is the number a credit committee actually reviews.
Delinquency Rate =
DIVIDE ( [Delinquent Balance], [Total Exposure] )

Impaired Rate =
DIVIDE ( [Impaired Balance], [Total Exposure] )

-- Account-weighted, shown alongside the balance-weighted rate. A gap between
-- the two tells you whether stress is concentrated in large or small accounts.
Delinquency Rate (Accounts) =
DIVIDE (
    SUM ( fact_account_month[delinquent_account_count] ),
    [Account Count]
)

Expected Loss =
SUM ( fact_account_month[expected_loss_cad] )

Expected Loss Rate =
DIVIDE ( [Expected Loss], [Total Exposure] )
```

## 3. Time intelligence

`dim_date` must be marked as the date table: select `dim_date` → Table tools →
Mark as date table → `date_key`. Without that, these return blanks.

```dax
Exposure PM =
CALCULATE ( [Total Exposure], DATEADD ( dim_date[date_key], -1, MONTH ) )

Exposure MoM % =
DIVIDE ( [Total Exposure] - [Exposure PM], [Exposure PM] )

Delinquency Rate PM =
CALCULATE ( [Delinquency Rate], DATEADD ( dim_date[date_key], -1, MONTH ) )

-- Basis points, because a 0.21% -> 0.24% move reads better as "+3 bps".
Delinquency Rate MoM (bps) =
( [Delinquency Rate] - [Delinquency Rate PM] ) * 10000

Delinquency Rate 3M Avg =
AVERAGEX (
    DATESINPERIOD ( dim_date[date_key], MAX ( dim_date[date_key] ), -3, MONTH ),
    [Delinquency Rate]
)

Exposure YoY % =
VAR PriorYear =
    CALCULATE ( [Total Exposure], SAMEPERIODLASTYEAR ( dim_date[date_key] ) )
RETURN
    DIVIDE ( [Total Exposure] - PriorYear, PriorYear )
```

## 4. Renewal risk — the measures the analysis turns on

```dax
Renewing Exposure =
SUM ( agg_renewal_exposure[balance_cad] )

Severe Shock Exposure =
CALCULATE (
    [Renewing Exposure],
    agg_renewal_exposure[projected_shock_band] = "SEVERE_OVER_40"
)

At-Risk Exposure =              -- severe + high, i.e. shock above 25%
CALCULATE (
    [Renewing Exposure],
    agg_renewal_exposure[projected_shock_band] IN { "SEVERE_OVER_40", "HIGH_25_40" }
)

Severe Shock Share =
DIVIDE ( [Severe Shock Exposure], [Renewing Exposure] )

-- Exposure-weighted, not a plain average: a large mortgage's shock matters more.
Avg Payment Shock =
DIVIDE (
    SUMX (
        agg_renewal_exposure,
        agg_renewal_exposure[projected_payment_shock_pct] * agg_renewal_exposure[balance_cad]
    ),
    [Renewing Exposure]
)

Monthly Payment Increase =
SUM ( agg_renewal_exposure[payment_increase_cad] )

Annual Payment Increase =
[Monthly Payment Increase] * 12

Accounts Facing Severe Shock =
CALCULATE (
    COUNTROWS ( agg_renewal_exposure ),
    agg_renewal_exposure[projected_shock_band] = "SEVERE_OVER_40"
)
```

## 5. Provision impact

A simple, defensible stress overlay: apply an uplift to PD for accounts in the
severe shock band and show the incremental expected loss it implies.

```dax
-- Elasticity taken from the observed relationship in fact_account_month:
-- default rate rises roughly 16x between the no-shock and 60%+ shock cohorts.
Shock PD Multiplier = 2.5

Stressed Expected Loss =
VAR BaseEL = [Expected Loss]
VAR SevereShare = DIVIDE ( [Severe Shock Exposure], [Total Exposure] )
RETURN
    BaseEL * ( 1 + SevereShare * ( [Shock PD Multiplier] - 1 ) )

Incremental Provision Required =
[Stressed Expected Loss] - [Expected Loss]
```

## 6. Data quality — surface trust on the dashboard itself

```dax
DQ Rules Passed =
CALCULATE ( COUNTROWS ( dq_results ), dq_results[passed] = TRUE () )

DQ Rules Total =
COUNTROWS ( dq_results )

DQ Pass Rate =
DIVIDE ( [DQ Rules Passed], [DQ Rules Total] )

DQ Status =
VAR Failed =
    CALCULATE (
        COUNTROWS ( dq_results ),
        dq_results[passed] = FALSE (),
        dq_results[severity] = "error"
    )
RETURN
    SWITCH (
        TRUE (),
        Failed > 0, "FAILED — " & Failed & " error-severity rule(s) breached",
        [DQ Pass Rate] < 1, "PASSED WITH WARNINGS",
        "ALL CHECKS PASSED"
    )
```

## 7. Dynamic titles and narrative

Recruiters notice these; most portfolio dashboards have static titles.

```dax
Portfolio Title =
"Retail Credit Portfolio — "
    & FORMAT ( [Total Exposure], "$#,##0,,.0B" )
    & " across " & FORMAT ( [Account Count], "#,##0" ) & " accounts"

Renewal Headline =
VAR Sev = [Severe Shock Exposure]
VAR Cnt = [Accounts Facing Severe Shock]
RETURN
    FORMAT ( Sev, "$#,##0,,.0M" ) & " across " & FORMAT ( Cnt, "#,##0" )
    & " accounts faces a payment increase above 40% at renewal"

Provenance Note =
"Macro source: " & SELECTEDVALUE ( stg_macro[data_source], "mixed" )
    & " | Portfolio: simulated, seeded"
```

---

## Number formatting

| Measure group | Format string |
|---|---|
| Exposure, balances | `$#,##0,,.0 "M"` (or `,,,.0 "B"` above a billion) |
| Rates | `0.00%` |
| Basis points | `+#,##0;-#,##0` with suffix ` bps` |
| Counts | `#,##0` |
| Payment amounts | `$#,##0` |
