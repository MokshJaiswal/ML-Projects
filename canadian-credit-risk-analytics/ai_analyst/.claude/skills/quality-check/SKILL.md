---
name: quality-check
description: >
  Check whether the CCRA warehouse is trustworthy before reporting from it.
  Reads the latest data quality run and reports pass/fail by rule. Use before
  answering any question that returns portfolio figures, and whenever someone
  asks whether the data is reliable, current, or what failed.
---

# Quality check

Before any figure leaves this warehouse, establish whether it can be trusted.

## Procedure

1. Open `data/warehouse/ccra.duckdb` **read-only**.
2. Read the latest run:

   ```sql
   SELECT rule_name, dimension, severity, metric_value, threshold, passed, description
   FROM quality.dq_results
   WHERE run_timestamp_utc = (SELECT max(run_timestamp_utc) FROM quality.dq_results)
   ORDER BY passed, severity DESC, dimension
   ```

3. Read `data/raw/macro_manifest.json` for the macro source mode and the run
   timestamp.

## Report

State the verdict first, in one line:

- **`ALL CHECKS PASSED`** — every rule passed. Figures may be reported.
- **`PASSED WITH WARNINGS`** — only `warn`-severity rules failed. Figures may be
  reported, but name the warnings alongside them.
- **`FAILED`** — one or more `error`-severity rules breached. **Do not report
  portfolio figures.** Name the failing rules, their measured value against
  threshold, and what each one means.

Then give the rule table, failures first.

Finally note two things that are easy to miss and matter:

- **Staleness.** If the latest run is more than 35 days old, say so — the
  pipeline is scheduled monthly, so a gap means a run failed.
- **Provenance.** If the macro mode is `synthetic_fallback`, state clearly that
  the macro series are a generated scenario rather than published Bank of Canada
  and Statistics Canada data, and that rate-dependent figures should be read as
  scenario output.

## Why this exists

A number from a pipeline nobody checked is worse than no number, because it gets
used. Reporting the quality state alongside the figure is what makes the figure
usable.
