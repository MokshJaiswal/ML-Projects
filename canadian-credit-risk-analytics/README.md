# CCRA — Canadian Credit Risk Analytics

An end-to-end retail credit analytics platform: public Canadian macro data and a
simulated loan book, through a tested warehouse and dimensional model, to a
Power BI report that answers one executive question.

> **The question:** *Between 2025 and 2027 a large share of Canadian mortgages
> written during the low-rate era reach the end of their fixed term and reprice.
> Which segments, products and regions carry the greatest payment-shock and
> default risk, how much incremental provision does that imply, and where should
> retention outreach be targeted first?*

---

## What this repository demonstrates

| Capability | Where to look |
|---|---|
| API ingestion with retry, backoff and graceful degradation | `src/ccra/ingest/` |
| Dimensional modelling (star schema, conformed date dimension) | `dbt/ccra/models/marts/` |
| SQL transformation with dbt — 45 tests, lineage, docs | `dbt/ccra/` |
| Data quality gate — 13 rules across 5 dimensions, fails the build | `src/ccra/quality/checks.py` |
| Reconciliation between source and target | `opening_balance_reconciles_to_origination` |
| Power BI semantic model + DAX measure library | `powerbi/` |
| Scheduled automation | `.github/workflows/pipeline.yml` |
| Requirements documentation and UAT | `docs/02-business-requirements.md` |
| Governed AI analytics layer | `ai_analyst/` |

The mapping from each of these to specific Canadian job postings is in
[`docs/01-project-plan.md`](docs/01-project-plan.md); the underlying market
research is in [`docs/00-market-research.md`](docs/00-market-research.md).

---

## Quick start

```bash
pip install -r requirements.txt
make all
```

That runs ingest → simulate → load → quality gate → dbt build → export, and takes
about two minutes. Then:

```bash
make docs        # dbt lineage graph and model documentation
```

Power BI extracts land in `data/exports/` as both Parquet and CSV. Build the
report from [`powerbi/dashboard-spec.md`](powerbi/dashboard-spec.md).

---

## Architecture

```
Bank of Canada Valet API ─┐
Statistics Canada WDS ────┤──► ingest ──► macro.parquet  (provenance-stamped)
                          │                     │
                          │                     ▼
   seeded simulator ──────┴──────────► macro-driven hazard model
                                              │
                              borrowers / accounts / account_month
                                              │
                                              ▼
                                   DuckDB — landing schema
                                              │
                                    ┌─────────┴─────────┐
                                    ▼                   │
                        data quality gate (13 rules)    │
                          fails the build on error      │
                                    │                   │
                                    ▼                   ▼
                            dbt: staging → marts (star schema, 45 tests)
                                              │
                                ┌─────────────┴─────────────┐
                                ▼                           ▼
                     Parquet / CSV extracts          AI analyst layer
                                │                   (governed semantic API)
                                ▼
                         Power BI report
```

### Why these tools

**DuckDB** is a real columnar analytical engine with full ANSI SQL and window
functions, and it needs no server — so a reviewer can clone and run this in one
command. The dbt models are adapter-portable: pointing the same project at
Snowflake or BigQuery is a profile change, not a rewrite.

**dbt** because Canadian analyst postings have started requiring it outright —
Moneris lists "minimum 1 year of experience with dbt and Snowflake" as a
*required* skill on a business data analyst role.

**Power BI** because it is dominant in Canadian financial services. A Streamlit
version exists so the work is viewable without a Power BI licence.

---

## The data

### Real: macro indicators

| Source | Series | Access |
|---|---|---|
| Bank of Canada Valet | Policy rate, prime, 5-year GoC yield, conventional 5-year mortgage | Public, keyless JSON |
| Statistics Canada WDS | Unemployment by province, CPI, New Housing Price Index, household debt-to-income | Public, keyless JSON |

### Simulated: the loan book

**No lender publishes account-level performance data, so the portfolio is
simulated.** This is stated plainly because the alternative — implying otherwise
— would make everything else here worthless.

What makes the simulation analytically meaningful rather than arbitrary is that
**every account's monthly default hazard is a function of the macro series
ingested upstream.** Payment shock at renewal is computed against the actual
market rate for that month. Change the rate path and the portfolio responds.

The generator is seeded (`portfolio.seed` in `config/pipeline.yml`), so a given
config produces a byte-identical portfolio on any machine.

Product-level calibration is checked against published Canadian norms:

| Product | 42-month cumulative default, simulated | Canadian norm |
|---|---|---|
| Mortgage (fixed) | 0.52% | ~0.5% |
| Mortgage (variable) | 0.53% | ~0.5% |
| HELOC | 0.55% | ~0.8% |
| Auto | 3.54% | ~3% |
| Credit card | 4.16% | ~5% |

### Provenance and graceful degradation

If the live APIs are unreachable, the pipeline falls back to a deterministic
**synthetic macro scenario** rather than failing — but every row is stamped
`source = 'synthetic_scenario'`, a manifest records the mode, and both the
dashboard and the AI analyst surface it. The fallback is a labelled stress
scenario, never presented as published statistics.

---

## Scale

| Table | Rows |
|---|---|
| `dim_borrower` | 60,000 |
| `dim_account` | 80,528 |
| `fact_account_month` | 3,008,785 |
| `agg_renewal_exposure` | 32,461 |

Portfolio exposure at the current reporting month: **$17.2B** across five
products and eight provinces.

---

## Findings

*Figures below come from the simulated portfolio under the synthetic macro
scenario. They illustrate the analysis; they are not statements about any real
lender's book.*

### 1. The repricing wave is concentrated and quantifiable

32,461 renewable facilities carrying **$11.3B** have not yet repriced. Of that,
**$2.78B across 7,356 accounts faces a payment increase above 25%**, and
**$908M across 2,013 accounts faces an increase above 40%** — an average of
**+$854 per month** for those households. Aggregate additional annual payment
obligation across the renewing book: **$81M**.

Exposure peaks in Q3 2026 at an average shock of 34.9%, then decays through 2027
as the assumed rate path eases.

### 2. The severe-shock cohort is almost entirely prime — which is the point

| Credit risk band | Share of the severe-shock cohort |
|---|---|
| Super-prime (800+) | 64.7% |
| Prime (720–799) | 34.8% |
| Near-prime (660–719) | 0.5% |
| Subprime and below | 0.0% |

The mechanism is straightforward once stated: the deepest payment shock belongs
to whoever borrowed at the *cheapest* rate, and the cheapest rates went to the
strongest credits. **Credit-score-based early warning systematically misses this
population**, because by every conventional measure they are the safest accounts
on the book.

### 3. The aggregate relationship inverts — a worked case of Simpson's paradox

Compare cumulative mortgage default across shock bands without controlling for
credit quality, and the result is backwards: accounts facing a >40% shock
default *less* (0.38%) than accounts facing none (0.50%).

Control for credit band and the relationship reappears:

| Credit band | Default, no shock | Default, >40% shock | Effect |
|---|---|---|---|
| Super-prime | 0.249% | 0.349% | **+40%** |
| Prime | 0.299% | 0.324% | **+8%** |
| Near-prime | 0.483% | 0.436% | −10% (n small) |
| Subprime | 0.818% | 0.540% | −34% (n small, selection) |

The aggregate inverts because the shock cohort is 63% prime-or-better against
53% for the no-shock cohort. The composition difference outweighs the effect.

**A caveat that belongs in the open:** the within-band shock→default relationship
is *built into* the simulation — there is a payment-shock coefficient in
`config/pipeline.yml`. It is not a discovery. What is genuinely emergent, and
what makes this worth showing, is the **aggregate inversion**: nobody specified
it, it falls out of the correlation between origination era and credit quality,
and it is exactly the trap a real analyst would fall into by running the
crosstab and stopping there.

### 4. Regional concentration

Ontario carries the largest absolute severe-shock exposure ($0.35B), but
Saskatchewan carries the highest *proportion* (10.3% of its renewing balance
versus 6.6% in Alberta) — a targeting question that absolute exposure alone
would answer wrongly.

### Recommendation

Prioritise proactive contact at the 2,013 accounts in the severe band ahead of
their renewal dates, weighted toward Ontario by absolute exposure and
Saskatchewan by rate. Because this population is overwhelmingly prime, it will
not surface in credit-score-triggered watchlists — it needs a renewal-date
trigger instead. Provision impact under a 2.5× PD uplift on the severe band is
modelled in the `Incremental Provision Required` measure.

---

## Data quality

13 rules across completeness, uniqueness, validity, consistency and
reconciliation. An `error`-severity breach exits non-zero and stops the build
before anything reaches the marts; results are persisted to
`quality.dq_results` so quality is itself a time series.

```
DONE   data_quality  rules=13 passed=13 warnings=0 errors=0
```

Plus 45 dbt tests — uniqueness, not-null, referential integrity, accepted
values, range checks, and a composite grain test on the fact table.

```
Done. PASS=45 WARN=0 ERROR=0 SKIP=0 TOTAL=45
```

---

## Repository layout

```
├── config/pipeline.yml        Every tunable. A run is described by this file + the git SHA.
├── src/ccra/
│   ├── ingest/                Bank of Canada + Statistics Canada clients
│   ├── simulate/              Macro-driven portfolio generator
│   ├── warehouse/             DuckDB loader
│   ├── quality/               Data quality gate
│   ├── export/                Power BI extracts
│   └── pipeline.py            CLI orchestrator
├── dbt/ccra/                  Star schema, tests, lineage
├── powerbi/                   DAX measure library + dashboard build spec
├── ai_analyst/                Governed semantic layer + Claude skills
├── docs/                      Market research, plan, requirements, data dictionary
└── .github/workflows/         Monthly scheduled rebuild
```

## Known limitations

Worth stating explicitly, because an analyst who cannot name their own
assumptions is not finished.

- **The loan book is simulated.** Distributions are calibrated to published
  aggregates, but no real account data is used.
- **Mortgage payments use monthly compounding.** Canadian fixed mortgages
  compound semi-annually; the difference is a few basis points on payment and
  does not change any conclusion, but it is a simplification.
- **One renewal per account.** The observation window is 42 months, so at most
  one 5-year renewal occurs; the model does not handle repeated renewals.
- **Repricing assumes the latest observed market rate** persists. It is not a
  forward rate curve.
- **The synthetic macro scenario is steeper than the actual tightening cycle**,
  so payment shock under fallback mode overstates what real 2026 renewals faced.
  Run with live sources for realistic magnitudes.
- **LGD is a fixed product-level constant.** A real model would condition it on
  LTV and regional house prices.

## Licence

MIT. The macro data is public and remains subject to the terms of the Bank of
Canada and Statistics Canada open licences.
