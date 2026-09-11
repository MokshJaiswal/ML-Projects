# Portfolio strategy and project plan

## The thesis

`00-market-research.md` establishes a specific gap: Canadian employers ask
repeatedly for data quality, reconciliation, requirements documentation,
dimensional modelling, automation and modern transformation tooling — and
almost no candidate portfolio contains any of it. Meanwhile every candidate
portfolio contains the same three notebooks over the same public CSVs.

This plan builds two projects that close that gap, plus a repositioning of the
two SQL projects already published.

---

## The portfolio, as a whole

| # | Project | Role in the portfolio | Status |
|---|---|---|---|
| 1 | **CCRA — Canadian Credit Risk Analytics** (this repo) | The flagship. End-to-end pipeline, warehouse, star schema, quality gate, Power BI. Proves you can do the job. | Built |
| 2 | **AI Analyst** (`ai_analyst/`) | The differentiator. A governed natural-language analytics layer over project 1. Proves 2026 fluency. | Designed |
| 3 | Instagram User Analytics *(existing)* | Supporting. SQL depth. Needs rework — see below. | Published, needs work |
| 4 | Operations Analytics & Metric Spikes *(existing)* | Supporting. SQL depth. Needs rework — see below. | Published, needs work |

Three to four projects is the right number. Beyond that, reviewers stop reading.

---

## Project 1 — CCRA, the flagship

### Business problem

> Between 2025 and 2027 a large share of Canadian mortgages written during the
> low-rate era reach the end of their fixed term and reprice at prevailing
> rates. For our retail book: which segments, products and regions carry the
> greatest payment-shock and default risk, how much incremental provision does
> that imply, and where should proactive retention and modification outreach be
> targeted first?

This question is chosen deliberately. It is:

- **Real** — the mortgage renewal wave is the dominant retail credit topic in
  Canadian banking right now, and every bank on the target employer list is
  working on it.
- **Money-denominated** — the answer is a provision number and a target list,
  not "engagement went up".
- **Defensible in an interview** — you can explain the mechanism, the
  assumptions, and what would change the answer.
- **Domain-aligned** — financial services is the deepest entry-level pool in
  Canada.

### Architecture

```
Bank of Canada Valet API ─┐
Statistics Canada WDS ────┤
                          ├─► ingest ─► macro.parquet (provenance-stamped)
                          │                   │
Seeded portfolio simulator┘                   ▼
         │                            simulate (macro-driven hazard)
         ▼                                    │
   borrowers / accounts / account_month ──────┘
                          │
                          ▼
                   DuckDB landing schema
                          │
                          ▼
              ┌── data quality gate (13 rules, fails the build)
                          │
                          ▼
                  dbt: staging → marts
              (star schema, 45 tests, lineage docs)
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
      Parquet / CSV extracts    Streamlit dashboard
              │
              ▼
        Power BI report
```

Every stage is orchestrated by `make all` and runs monthly in GitHub Actions.

### Which employer requirement each component answers

| Component | Requirement it evidences | Named by |
|---|---|---|
| Valet / WDS API clients with retry and backoff | "data from multiple sources and platforms" | Moneris |
| Seeded simulator | Reproducibility; synthetic data for privacy | Standard bank practice |
| DuckDB warehouse + star schema | "data modeling, and database design" | Scotiabank |
| dbt models and tests | "minimum 1 year of experience with dbt" | Moneris |
| 13-rule quality gate | "data profiling, validation"; "reconciliation between source and target" | Moneris, Scotiabank |
| Power BI star model + DAX | "dashboards, scorecards, visualizations using Tableau or Power BI" | Moneris, SureWerx |
| Business requirements document | "gather, document, and translate requirements" | Moneris, SureWerx |
| UAT checklist | "coordinate user acceptance testing" | SureWerx, Scotiabank |
| GitHub Actions schedule | "identify opportunities to ... automate operational processes" | Scotiabank |
| dbt docs lineage graph | "data lineage, metadata repositories, governance" | Scotiabank |
| Data quality dashboard page | "monitor data quality, identify anomalies" | Scotiabank |

That table is the project's real specification. Each row is a sentence you can
say in an interview with something to show behind it.

### On the synthetic portfolio — the honest framing

No lender publishes account-level performance data, so the loan book is
simulated. Say this plainly, everywhere, and it becomes a strength rather than a
weakness:

- Banks themselves use synthetic data for model development and testing,
  precisely because privacy rules prevent using production data. Knowing that is
  itself domain knowledge.
- The macro layer *is* real (Bank of Canada, Statistics Canada), and the
  simulation is driven by it — so the portfolio responds to the actual rate
  path. That is the interesting part.
- Every generated row is stamped with its provenance, and the dashboard surfaces
  which mode produced the data.

**Never** present simulated figures as real portfolio outcomes. The moment an
interviewer suspects that, the whole portfolio is worthless.

---

## Project 2 — the AI Analyst

See `ai_analyst/README.md` for the full design and a candid assessment of the
idea. The short version:

**Build it second, not first, and build it *on top of* project 1.**

An AI agent that does analysis does not prove you can do analysis — and for an
entry-level analyst role, that is precisely what is being screened for. But an
AI layer that queries *your own governed warehouse*, is constrained by *your own
semantic definitions*, and validates its answers against *your own dbt tests* —
that demonstrates both the analytics fundamentals and the 2026 tooling fluency
that SureWerx and Fidelity are explicitly asking for.

The framing that works: **not "AI replaces the analyst" but "AI over a governed
semantic layer".** The second is what enterprises are actually building, and
it is the version that shows you understand why the governance matters.

---

## Projects 3 and 4 — repositioning the existing SQL work

An honest review of the two published SQL repos.

### What is good
The SQL itself is solid. `Solution Case Study 1.sql` shows window functions,
two distinct approaches to a rolling average (subquery and CTE), and two methods
for duplicate detection. That is genuinely above the level of most entry-level
portfolios.

### What will cost you
1. **Both are widely-replicated bootcamp case studies.** The Instagram and
   Operations Analytics assignments appear in thousands of near-identical public
   repos. A reviewer who has seen them before discounts them instantly.
2. **The README claims findings the queries do not produce.** The Operations
   Analytics README reports "emails with personalized subject lines boosted
   engagement by 15%" — there is no subject-line data in the schema and no query
   computes it. It also reports a "12% drop on weekends" and a "20% week-2
   retention drop" with no supporting output committed. If an interviewer asks
   you to walk through how you got 15%, there is no answer. **This is the single
   highest-priority fix in the entire portfolio** — an unsupported number is
   worse than no number.
3. **The README describes a folder structure that does not exist** (`sql_queries/`
   with five named files). The repo has two flat `.sql` files.
4. **No reproducibility.** No data, no schema load script for case study 1, no
   outputs.

### The fix (roughly a weekend)
1. Delete or substantiate every claimed metric. Run the queries, commit the
   actual result sets as CSVs, and quote only numbers that appear in them.
2. Make the README structure match the repo, or restructure the repo to match.
3. Add a `setup.sql` that creates and populates the tables so a reviewer can run
   your queries.
4. Reframe the summaries around the business decision, not the SQL feature.
5. Merge both into one repo, `sql-analytics-case-studies`, with a clear note
   that they are case studies from a structured curriculum. Labelling them
   honestly costs nothing and removes the "is he passing this off as original?"
   question.

Do this before adding anything new. A portfolio with one unverifiable number in
it is a portfolio an interviewer stops trusting.

---

## Sequencing

| Phase | Work | Rough effort |
|---|---|---|
| 1 | Fix the two existing SQL repos | 1 weekend |
| 2 | Run CCRA end to end, understand every stage well enough to explain it | 2–3 days |
| 3 | Build the Power BI report from `powerbi/dashboard-spec.md` | 3–4 days |
| 4 | Write the findings up as an executive summary; record a 5-minute walkthrough | 2 days |
| 5 | Build the AI Analyst layer | 1 week |
| 6 | Rewrite the résumé around the requirement table above | 1 day |

Phases 1–4 produce a portfolio that is already competitive. Phase 5 is the
differentiator. Do not start phase 5 before phase 4 is finished — a
half-finished AI project alongside a half-finished analytics project reads worse
than one complete analytics project.

## Job search strategy implied by the research

1. **Search on work, not titles.** Set alerts for Business Systems Analyst,
   Reporting Analyst, BI Developer, Pricing Analyst, FP&A Analyst, Data
   Warehouse Analyst — not just Data Analyst.
2. **If you are an enrolled student, apply to the bank co-op pipelines now.**
   TD, RBC, BMO and Scotiabank post Winter and Summer terms months ahead and the
   eligibility gate is strict. If you are not enrolled, skip them entirely and
   stop reading those postings.
3. **Target the mid-market first.** SureWerx-sized companies hire 0–2 years
   directly; the big banks mostly convert co-ops. A first title from a
   mid-market company makes the bank application viable a year later.
4. **Apply to the 3-year postings anyway** where the wording accepts academic
   projects — Scotiabank's does, explicitly.
5. **Lead with the requirement table.** In a cover letter, map their posting's
   bullets to your project's components. Almost nobody does this, and it is the
   most direct possible answer to "why should we interview you".
