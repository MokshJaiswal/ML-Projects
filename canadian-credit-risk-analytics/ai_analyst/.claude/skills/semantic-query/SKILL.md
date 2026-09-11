---
name: semantic-query
description: >
  Answer a question about the CCRA credit portfolio by composing SQL from the
  declared metric catalogue in ai_analyst/metrics.yml. Use whenever someone asks
  for a portfolio figure — exposure, delinquency, expected loss, renewal shock —
  or asks to break one down by product, province, risk band, vintage or month.
---

# Semantic query

You answer portfolio questions by composing SQL **from the metric catalogue
only**. You do not write free-form SQL against the warehouse tables.

## Procedure

1. **Check quality first.** Run the `quality-check` skill. If an error-severity
   rule failed on the latest run, stop and report that instead of returning
   figures.

2. **Read the contract.** Load `ai_analyst/metrics.yml`. It declares every
   available metric, its exact SQL expression, and its grain.

3. **Map the question onto the catalogue.**
   - Identify which metric(s) are being asked for.
   - Identify which dimensions to group by or filter on.
   - If the question needs a metric that is not declared, **do not invent one**.
     Say it is not in the semantic layer, list the nearest available metrics,
     and offer to add a definition.

4. **Respect the grain.** Metrics carry a `grain` of either
   `fact_account_month` or `agg_renewal_exposure`. Never combine metrics from
   different grains in a single SELECT — `total_exposure` and
   `severe_shock_exposure` come from different tables and summing across them
   double-counts. Run separate queries and present them side by side.

5. **Default to the current reporting month** unless the question asks for a
   trend or names a period. Join `dim_date` and filter `is_current_month`.

6. **Compose and run.** Build the query as:

   ```sql
   SELECT <dimension columns>,
          <metric sql expressions>
   FROM main_marts.fact_account_month f
   JOIN main_marts.dim_account a  ON a.account_key = f.account_key
   JOIN main_marts.dim_product p  ON p.product_key = f.product_key
   JOIN main_marts.dim_date d     ON d.date_key    = f.date_key
   WHERE <filters>
   GROUP BY <dimension columns>
   ORDER BY <the primary metric> DESC
   ```

   For `agg_renewal_exposure` metrics, alias that table as `r` and join
   `dim_account a ON a.account_key = r.account_key`.

   Open the connection **read-only**.

## Answering

Always report, in this order:

1. **The answer**, in one sentence, with the number formatted per the metric's
   `format` (currency to the nearest million above $1M; percentages to two
   decimals).
2. **The breakdown table**, if the question implied one.
3. **What it means** — one or two sentences of interpretation, not a restatement
   of the number.
4. **Provenance** — a short block naming:
   - the metric definitions used,
   - the dbt models they read from,
   - the reporting month,
   - the macro data source mode (`live` or `synthetic_fallback`, from
     `data/raw/macro_manifest.json`).

Never return a figure without the provenance block. An uncited number is a bug,
not a shortcut.

## Refusals

- If asked for a single identifiable borrower's details, decline and offer
  segment-level analysis instead.
- If asked to write SQL outside the catalogue, explain why the constraint exists
  and offer to extend `metrics.yml` instead.
