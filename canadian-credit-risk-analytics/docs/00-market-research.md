# Canadian entry-level data analyst market — research findings

Research conducted September 2026. Primary evidence: live Indeed Canada postings
sampled across Toronto, Vancouver and Calgary, read in full rather than by title.
Secondary: Glassdoor volume counts and published salary aggregates.

---

## 1. The single most important finding: title is the wrong search term

Searching `"Data Analyst"` in Toronto surfaced roughly as many postings under
*other* titles as under that one. In a representative sample of 40 postings
returned by data-analyst-adjacent searches, the titles were:

| Title family | Example employers in the sample |
|---|---|
| Data Analyst | Scotiabank, Reach3 Insights, FOUR20, TD (co-op) |
| Business / Business Data Analyst | Moneris, First National Financial, EQ Bank, TP |
| Business Systems Analyst | TD, isgSearch |
| Business Intelligence Analyst / Developer | Atlantic Packaging, SRX Health, Raise |
| Reporting / Advanced Analytics Analyst | Fidelity Canada |
| Domain analyst (Pricing, Supply Chain, FP&A, Procurement, Logistics) | Sysco, SmartCentres, Atlantic Packaging, BCAA, CFR Chemicals |
| Data Warehouse Analyst | TransLink |

**Implication:** a job search restricted to "Data Analyst" sees perhaps half the
addressable market. The skill set is near-identical across these titles — SQL,
a BI tool, requirements gathering, stakeholder communication. Search on the
*work*, not the label.

## 2. Which sectors carry the entry-level volume

Ranked by observed posting density in the sample:

1. **Financial services** — banks (TD, RBC, Scotiabank, BMO, CIBC, EQ Bank,
   ICBC Canada), payments (Moneris), asset management (Fidelity Canada),
   mortgage finance (First National), fund services (IFDS). Concentrated in
   Toronto. This is the deepest pool by a wide margin.
2. **Healthcare / pharma / life sciences** — Sanofi, SRX Health, DoPriorAuth,
   Canadian Cancer Society.
3. **Retail, CPG and distribution** — Sysco, SureWerx, T&T Supermarket,
   Atlantic Packaging, Ecco Supply.
4. **Public sector and crown corporations** — City of Calgary, TransLink, BDC.
   Slower hiring cycles, but they publish salary bands and interview
   predictably.
5. **Consulting and staffing** — isgSearch, Raise, VIMY, McKinsey. Often the
   fastest route to a first title, at the cost of stability.

## 3. What the postings actually ask for

Read across the full descriptions, not the bullet summaries:

### Universal (appeared in essentially every posting)
- **SQL** — writing and *optimising* queries, creating views, complex extraction
  and transformation. Not just `SELECT ... WHERE`.
- **A BI tool** — **Power BI is dominant in Canada**, especially in finance and
  enterprise. Tableau appears as an alternative, usually as "Tableau or Power
  BI". Canadian enterprise is overwhelmingly a Microsoft shop.
- **Excel** — still explicitly listed, including by Fidelity ("advanced
  proficiency with Microsoft Excel, Access and PowerPoint").
- **Stakeholder communication** — every single posting. Usually phrased as
  translating between technical and non-technical audiences.

### Very common, and where most candidate portfolios are silent
- **Data quality, validation and reconciliation.** Scotiabank devotes three
  separate responsibility blocks to it: "monitor data quality, identify
  anomalies, investigate discrepancies"; "perform reconciliation activities to
  ensure completeness and accuracy between source and target systems". Moneris:
  "ensure data quality through data profiling, validation, and analysis of data
  from multiple sources".
- **Requirements gathering and documentation.** "Assist in documenting
  requirements from business stakeholders" (SureWerx); "gather, document, and
  translate data and reporting requirements into actionable solutions"
  (Moneris); "create and maintain process documentation, user guides, and
  operational procedures" (Scotiabank).
- **UAT and release process.** SureWerx: "develop test plans and conduct quality
  assurance testing prior to release"; "coordinate user acceptance testing".
  Scotiabank: "support User Acceptance Testing (UAT), parallel runs, production
  readiness, and go-live activities".
- **Process automation.** "Identify opportunities to streamline and automate
  operational processes" (Scotiabank).
- **Data modelling / warehousing.** "Build and support data models, reporting
  datasets, and data management solutions" (Moneris); "data modeling, and
  database design" (Scotiabank).

### The 2026 differentiators — new, and still rare in candidate portfolios
- **dbt and Snowflake.** Moneris lists "minimum 1 year of experience with dbt
  and Snowflake" as a *required* skill on a business data analyst posting. This
  is analytics-engineering tooling crossing into the analyst job description.
- **Microsoft Fabric and Copilot.** SureWerx requires "Power BI, SQL, Copilot,
  MS Fabric, Excel" and asks the junior analyst to "assist in rollout of AI
  tools to accelerate reporting and analysis cycle".
- **AI fluency generally.** Fidelity wants "genuine interest in ... future state
  of technology like artificial intelligence & machine learning". Both Moneris
  and Fidelity disclose AI-assisted candidate screening, which itself says
  something about how quickly these organisations are adopting.
- **Data governance and lineage.** Scotiabank lists "data lineage, metadata
  repositories, and governance frameworks" under exposure.

### Python's real position
Python is listed almost everywhere, but read where it sits. Scotiabank files it
under **Nice-to-Have** alongside SAS and VBA. RBC's co-op posting lists it in
must-haves next to SQL and R. Fidelity wants it for modelling. The honest
summary: **SQL and Power BI get you screened in; Python differentiates you once
you are in the room.** A portfolio that is Python-heavy and SQL-light is
optimised for the wrong filter.

## 4. Experience requirements, and how to read them

| Employer | Stated requirement | What it means in practice |
|---|---|---|
| SureWerx (Junior Data Analyst) | 0–2 years | Genuinely open to entry level |
| Scotiabank (Data Analyst) | 3 years, **but** explicitly accepts "work, internships, co-op placements, **or academic projects**" | A strong project portfolio is named as qualifying evidence |
| Moneris (Business Data Analyst) | 3–5 years + 1 year dbt/Snowflake | Stretch; apply anyway if the portfolio carries dbt |
| Fidelity (Analyst, Advanced Analytics) | 2–3 years | Stretch |
| TD / RBC / BMO co-ops | Must be an enrolled student returning to school | **Hard eligibility gate, not a preference** |

Two things follow. First, the big-bank co-op pipeline — the most visible
entry-level banking route — is closed to anyone not currently enrolled. Second,
Scotiabank's wording is the one to build toward: it names academic projects as
acceptable evidence of experience. A rigorous project is not a consolation
prize in that posting; it is a listed qualification.

## 5. Compensation observed

| Role | Band | Source |
|---|---|---|
| Business Data Analyst, Moneris (contract) | $71,000 – $100,000 | Posted in the job description |
| Analyst, Advanced Analytics, Fidelity | $75,000 – $95,000 + bonus + RRSP | Posted in the job description |
| Banking data analyst, Toronto (hourly, all levels) | $26.84 – $43.59/hr, median $37.62 | ZipRecruiter aggregate, Sept 2026 |

Ontario pay-transparency rules mean an increasing share of postings state the
band. Use posted bands rather than aggregator averages when negotiating.

## 6. What this implies for a portfolio project

The gap between what candidates build and what employers ask for is specific and
addressable:

| Employers repeatedly ask for | Typical portfolio project shows | Gap |
|---|---|---|
| Optimised SQL over a modelled warehouse | A Jupyter notebook over a Kaggle CSV | **Large** |
| Power BI dashboards for stakeholders | A matplotlib chart grid | **Large** |
| Data quality, validation, reconciliation | Nothing | **Total** |
| Requirements documentation, UAT | Nothing | **Total** |
| Scheduled, automated pipelines | A script run once by hand | **Large** |
| dbt / modern transformation tooling | Nothing | **Total** |
| Dimensional modelling | A single flat table | **Large** |
| Domain knowledge in financial services | Generic e-commerce or Titanic data | **Large** |

The project specified in `01-project-plan.md` is built to close every row of that
table.

---

## Sources

- Live Indeed Canada postings, sampled 11 September 2026 (Toronto, Vancouver,
  Calgary; searches: "Data Analyst", "Entry Level Data Analyst", "Data Analyst
  bank", "Business Intelligence Analyst Power BI"). Full descriptions read for
  Moneris, SureWerx, Scotiabank, RBC and Fidelity postings.
- [Glassdoor — entry level data analyst jobs in Canada](https://www.glassdoor.ca/Job/canada-entry-level-data-analyst-jobs-SRCH_IL.0,6_IN3_KO7,31.htm)
- [Glassdoor — entry level data analyst jobs in Toronto](https://www.glassdoor.ca/Job/toronto-entry-level-data-analyst-jobs-SRCH_IL.0,7_IC2281069_KO8,32.htm)
- [Indeed Canada — big five bank postings, Toronto](https://ca.indeed.com/q-cibc,-rbc,-td-bank,-scotiabank,-bmo-l-toronto,-on-jobs.html)
- [ZipRecruiter — banking data analyst salaries, Toronto](https://www.ziprecruiter.com/Jobs/Banking-Data-Analyst/-in-Toronto,ON)

*Posting details reflect what was live in September 2026. Re-run the search
before relying on any individual figure.*
