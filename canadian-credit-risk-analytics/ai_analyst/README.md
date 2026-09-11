# AI Analyst — a governed natural-language layer over the CCRA warehouse

## An honest assessment of the idea first

The original idea was "an AI data analyst built with Claude that automates the
complete procedure, acting as a data analyst using agents and skills."

**The instinct is right and the timing is right. The framing needs to change.**

### Why the framing matters

Consider what an entry-level analyst hiring manager is screening for: can this
person write SQL against a schema they have never seen, build a dashboard a VP
will actually use, and explain a number to someone who does not trust it. A
project that *automates* those things does not evidence that you can *do* them.
Worse, presented as a standalone portfolio piece it invites the reading "he
built a tool to avoid the analysis" — which is the opposite of the intended
signal.

There is a second problem. "An AI that acts as a data analyst" is, in September
2026, a crowded claim. Every BI vendor ships one. A portfolio project that
competes with Microsoft Copilot on its own framing loses that comparison.

### What works instead

Build the AI layer as **a governed semantic interface to a warehouse you built
yourself**. The pitch becomes:

> "I built a credit risk warehouse with a dbt semantic layer and a data quality
> gate. Then I put a natural-language interface on top of it that can only query
> through the governed models, cites the lineage for every number it returns,
> and refuses to answer when the underlying quality checks have failed."

That version is strong because:

- It **requires** project 1 to exist, so it showcases the analytics fundamentals
  rather than hiding them.
- It answers the exact thing SureWerx put in a junior posting — *"assist in
  rollout of AI tools to accelerate reporting and analysis cycle"* — and what
  Fidelity asks for as *"genuine interest in ... artificial intelligence"*.
- It demonstrates the thing most NL-to-SQL demos get wrong: **governance**. An
  LLM pointed at raw tables invents joins and returns confidently wrong numbers.
  An LLM constrained to a tested semantic layer does not. Knowing the difference
  is the senior-sounding insight.
- It is genuinely hard to dismiss. "I made a chatbot" is dismissible. "I made
  the numbers verifiable" is not.

### The rule to hold onto

**The AI layer must never be the only thing that proves you can analyse data.**
Build it after the Power BI report is finished, not before.

---

## Design

```
                    ┌─────────────────────────────────┐
   "Which regions   │        Claude Agent             │
    face the worst  │                                 │
    renewal shock?" │   Skills:                       │
         ─────────► │    • semantic-query             │
                    │    • quality-check              │
                    │    • narrative-insight          │
                    └──────────────┬──────────────────┘
                                   │ constrained to
                                   ▼
                    ┌─────────────────────────────────┐
                    │   Semantic layer (contract)     │
                    │   metrics.yml — every metric    │
                    │   defined once, with its SQL    │
                    └──────────────┬──────────────────┘
                                   ▼
                    ┌─────────────────────────────────┐
                    │   dbt marts in DuckDB           │
                    │   (read-only connection)        │
                    └─────────────────────────────────┘
```

### The four design decisions that make it defensible

**1. The agent queries metrics, not tables.**
It cannot write arbitrary SQL against `fact_account_month`. It selects from a
declared metric catalogue (`metrics.yml`), and the SQL for each metric is
written once, by you, and tested by dbt. This is the difference between a demo
and something a bank would let near its data.

**2. Read-only, allow-listed connection.**
The DuckDB connection is opened read-only. Even a prompt-injected instruction to
`DROP TABLE` has nothing to act on.

**3. Every answer carries provenance.**
Each response states which metric definitions were used, which models they come
from, the row count, and the macro data source mode. An answer without a
citation is a bug.

**4. It refuses when quality has failed.**
Before answering, the agent reads `quality.dq_results`. If an error-severity
rule is breached on the latest run, it says so and declines to report figures.
This single behaviour is the most interview-valuable part of the whole project —
it is what separates someone who has thought about data trust from someone who
has not.

---

## Implementation sketch

```
ai_analyst/
├── README.md              ← this file
├── metrics.yml            ← the semantic contract
├── .claude/
│   └── skills/
│       ├── semantic-query/SKILL.md
│       ├── quality-check/SKILL.md
│       └── narrative-insight/SKILL.md
└── agent.py               ← optional: same logic via the Anthropic SDK
```

Two ways to run it, and they are worth understanding as alternatives:

- **As Claude Code skills.** Drop `.claude/skills/` into the repo and the agent
  is available in any Claude Code session opened here. Zero infrastructure. Best
  for demonstrating the idea.
- **As a standalone agent** via the Anthropic SDK with tool use, wrapped in a
  small Streamlit chat UI. More work, but it is a deployable artefact you can
  link to.

Start with the skills. Build the SDK version only if you want a hosted demo.

## What to measure

An AI project without an evaluation is a demo. Add a small eval set — 20
questions with known correct answers computed directly in SQL — and report
accuracy. That turns "I built an AI analyst" into "I built an AI analyst and
measured it at 18/20 on a held-out question set, with the two failures both
being ambiguous-phrasing cases." The second sentence is what gets you hired.
