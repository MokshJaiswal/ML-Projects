# Business Requirements Document — Retail Credit Renewal Risk Reporting

| | |
|---|---|
| **Document ID** | CCRA-BRD-001 |
| **Version** | 1.0 |
| **Status** | Approved for build |
| **Requesting function** | Retail Credit Risk |
| **Delivery team** | Credit Risk Analytics |
| **Related artefacts** | CCRA-DD-001 (data dictionary), CCRA-UAT-001 (below) |

> This document is written the way a bank writes one, because "gather, document,
> and translate data and reporting requirements into actionable solutions" is a
> line item in the job description this project targets. Producing the artefact
> is part of the deliverable, not paperwork around it.

---

## 1. Background

A material share of the retail mortgage book was originated between 2020 and
2022, when contract rates were at historic lows. Those facilities carry five-year
terms and reprice at prevailing market rates on renewal, concentrating a
significant repricing event across 2025–2027.

Credit Risk currently has no consolidated view of which accounts reprice when,
what payment increase each faces, or what the aggregate provision impact is.
Current reporting is monthly delinquency by product and region — backward-looking
and silent on accounts that have not yet repriced.

## 2. Problem statement

Existing reporting cannot answer:

1. What exposure reprices in each forward quarter?
2. What payment increase will each account face at prevailing rates?
3. Which segments — product, region, vintage, credit band, income band — carry
   disproportionate shock?
4. What incremental provision does the shock imply?
5. Which accounts should receive proactive retention or modification contact,
   and in what priority order?

## 3. Objectives

| # | Objective | Success measure |
|---|---|---|
| O1 | Forward view of repricing exposure by quarter | Renewal schedule visible 18+ months ahead |
| O2 | Per-account projected payment shock | Every un-repriced renewable facility carries a projected payment and shock % |
| O3 | Segment attribution | Shock decomposable by product, province, CMA, vintage, credit band, income band, LTV band |
| O4 | Provision impact | Incremental expected loss under a stated PD uplift |
| O5 | Prioritised outreach list | Exportable, ranked account list |
| O6 | Demonstrable data trust | Quality results visible on the report itself |

## 4. Scope

**In scope:** retail secured and unsecured lending — fixed and variable
mortgages, HELOC, auto, credit card. Eight provinces. Monthly grain. Historical
observation window plus forward renewal schedule.

**Out of scope:** commercial and business banking; wealth; insurance; deposits;
collections workflow and any system of record write-back; borrower-level
decisioning — this is a portfolio analytics deliverable, and individual credit
decisions remain with adjudication.

## 5. Stakeholders

| Role | Interest | Primary page |
|---|---|---|
| VP, Retail Credit Risk | Provision impact, aggregate exposure | Executive Summary |
| Director, Portfolio Management | Segment concentration, targeting | Renewal Cliff |
| Regional Credit Managers | Local exposure against local conditions | Regional & Segment Risk |
| Finance / Provisioning | Expected loss inputs | Executive Summary |
| Data Governance | Lineage, quality, provenance | Data Quality & Lineage |
| Internal Audit | Reproducibility, controls | Repository + this document |

## 6. Functional requirements

| ID | Requirement | Priority | Acceptance criterion |
|---|---|---|---|
| FR-01 | Report total exposure, delinquency rate and impaired rate by month | Must | Figures reconcile to `fact_account_month` within 0.5% |
| FR-02 | Break every measure down by product, province, CMA, credit band, income band, vintage and LTV band | Must | All seven dimensions filterable, cross-filtering correctly |
| FR-03 | Show renewing exposure by forward quarter | Must | Schedule extends to the last renewal date in the book |
| FR-04 | Compute projected payment and shock % per un-repriced facility | Must | Present for every renewable account with `has_renewed = false` |
| FR-05 | Band projected shock into five severity tiers | Must | Bands are mutually exclusive and exhaustive |
| FR-06 | Report incremental provision under a configurable PD uplift | Must | Uplift exposed as a DAX measure, not hard-coded in a visual |
| FR-07 | Rates must be balance-weighted, with account-weighted shown alongside | Must | Both measures present and labelled |
| FR-08 | Drill from any aggregate to individual account history | Should | Drill-through page filtered on `account_id` |
| FR-09 | Surface data quality status on the report | Must | Status card visible on the Executive Summary |
| FR-10 | Surface macro data provenance | Must | Live vs scenario mode stated on the report |
| FR-11 | Export the prioritised outreach list | Should | Table export to CSV from the Renewal Cliff page |
| FR-12 | Vintage performance curves by origination year | Should | Delinquency by months-on-book, one line per vintage |

## 7. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-01 | Report page render | Under 3 seconds on the executive page |
| NFR-02 | Full pipeline runtime | Under 10 minutes |
| NFR-03 | Reproducibility | Identical output from identical config and seed |
| NFR-04 | Refresh cadence | Monthly, automated, no manual step |
| NFR-05 | Failure behaviour | Error-severity quality breach stops the build before the marts |
| NFR-06 | Accessibility | No meaning encoded in colour alone; alt text on every visual |
| NFR-07 | Auditability | Every run leaves a timestamped quality record and a source manifest |

## 8. Business rules

| ID | Rule |
|---|---|
| BR-01 | **Impaired** = 90+ days past due or defaulted |
| BR-02 | **Delinquent** = any delinquency state other than `CURRENT` |
| BR-03 | Credit bands: super-prime 800+, prime 720–799, near-prime 660–719, subprime 600–659, deep subprime below 600 |
| BR-04 | Payment shock = projected payment ÷ current payment − 1 |
| BR-05 | Severe shock = projected shock above 40% |
| BR-06 | Fiscal year runs 1 November to 31 October |
| BR-07 | Only facilities where term < amortisation reprice; fully-amortising facilities mature |
| BR-08 | Renewal repricing assumes the latest observed conventional 5-year rate |
| BR-09 | Portfolio rates are balance-weighted unless explicitly labelled otherwise |

## 9. Assumptions and dependencies

**Assumptions**
- The latest observed market rate is a reasonable proxy for the renewal rate.
- Borrowers renew with the same lender at the same remaining amortisation.
- No structural change to product mix within the forecast window.

**Dependencies**
- Bank of Canada Valet API availability.
- Statistics Canada WDS availability.
- Power BI Desktop (report build) / Power BI Service (distribution).

## 10. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Source API unavailable at refresh | Stale or missing macro | Retry with backoff; labelled scenario fallback; mode surfaced on the report |
| Rate path diverges from assumption | Shock estimates drift | Repricing rate is a single configurable input; re-run under alternatives |
| Renewal behaviour differs (borrowers switch lender, extend amortisation) | Overstated shock | Documented as a limitation; extension scenario is the first enhancement |
| Users read balance-weighted as account-weighted | Wrong conclusion | Both published, explicitly labelled |
| Users treat simulated figures as actuals | Serious credibility failure | Provenance stated in the repo, on the report, and in the AI layer |

---

# UAT — CCRA-UAT-001

Run before each release. Record actual against expected; any failure blocks.

## Data integrity

| # | Test | Expected |
|---|---|---|
| T-01 | Sum of `balance_cad` in Power BI for the current month equals the warehouse total | Match within 0.01% |
| T-02 | Account count matches `SELECT count(*) FROM dim_account` filtered to open accounts | Exact match |
| T-03 | No account appears twice in a single month | Zero duplicates |
| T-04 | Every fact row resolves to a dimension row | Zero orphans |
| T-05 | Renewal schedule totals equal `agg_renewal_exposure` total | Exact match |

## Calculation

| # | Test | Expected |
|---|---|---|
| T-06 | Delinquency rate = delinquent balance ÷ total balance, checked by hand for one province | Match to 4 dp |
| T-07 | Shock bands are mutually exclusive and sum to the total | No account in two bands |
| T-08 | Projected payment recomputed by hand for three sampled accounts | Match within $1 |
| T-09 | Prior-month measures return the actual prior month, not a blank | Correct values |
| T-10 | Provision uplift measure responds to a changed multiplier | Recalculates |

## Filter behaviour

| # | Test | Expected |
|---|---|---|
| T-11 | Province slicer filters every visual on the page | All respond |
| T-12 | Slicers stay in sync across pages | State preserved |
| T-13 | Clearing all filters restores portfolio totals | Matches unfiltered warehouse |
| T-14 | Drill-through from an aggregate lands on the right account | Correct account, correct history |
| T-15 | Cross-filtering by delinquency state gives the same answer as an equivalent SQL query | Match |

## Presentation and accessibility

| # | Test | Expected |
|---|---|---|
| T-16 | All currency in CAD, consistently formatted | Consistent |
| T-17 | Rates to two decimals, basis-point deltas signed | Consistent |
| T-18 | Products sort in `display_order`, not alphabetically | Correct order |
| T-19 | Quality status card reflects the latest run | Matches `quality.dq_results` |
| T-20 | Provenance note states the correct macro mode | Matches `macro_manifest.json` |
| T-21 | Every visual has alt text | Present |
| T-22 | Conditional formatting passes WCAG AA contrast | Passes |
| T-23 | Executive page renders in under 3 seconds | Under target |

## Sign-off

| Role | Name | Date | Outcome |
|---|---|---|---|
| Business owner | | | |
| Data governance | | | |
| Report developer | | | |
