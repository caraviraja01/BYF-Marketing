# Architecture

## Overview

A linear, auditable agent pipeline with a human-in-the-loop gate. Each agent has
one job, a typed input, and a typed output (see `app/schemas.py`), so the system is
easy to reason about, test, and extend.

```
PipelineRun
  ├─ research   (ResearchAgent)     → ResearchBrief        ─┐
  ├─ strategy   (StrategyAgent)     → ContentStrategy       │ persisted on the run
  └─ items[]                                                ─┘
       ├─ idea          (ContentIdea)
       ├─ script        (ScriptAgent)        → Script
       ├─ creative      (CreativeAgent+Canva)→ CreativeAsset
       ├─ verification  (VerificationAgent)  → VerificationResult
       │
       │   ── 🧑 HUMAN REVIEW GATE (dashboard / CLI) ──
       │
       ├─ publish       (SocialPublisher)    → PublishResult
       └─ analytics     (AnalyticsAgent)     → AnalyticsInsight → feeds next cycle
```

## Layers

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Config | `settings.py`, `brand.py`, `config/brand.yaml` | Env + the single brand source of truth every agent reads |
| LLM | `llm.py` | Claude wrapper; disabled → agents use their own `mock()` |
| Agents | `agents/*` | Six specialists, each a `BaseAgent` subclass |
| Integrations | `integrations/*` | Canva, web research, social publishers, analytics — all behind clean interfaces |
| Orchestration | `orchestrator.py` | Runs the chain, persists every stage, enforces the gate |
| Persistence | `db.py`, `models.py` | SQLAlchemy + SQLite (`PipelineRun`, `ContentItem`) |
| Interface | `main.py` (web), `cli.py` (CLI), `templates/` | Dashboard + review gate + analytics |

## Design decisions

- **Mock-first.** No API key? Every agent returns realistic structured output, so the
  whole flow is demonstrable before any credential exists. Add `ANTHROPIC_API_KEY`
  to switch on real Claude generation — no other change required.
- **Typed hand-offs.** Pydantic schemas are the contract between agents; the LLM is
  instructed to emit JSON matching each schema and the result is validated.
- **Compliance is deterministic, not vibes.** The Verify agent runs a hard,
  non-LLM scan for banned claims (`verify.py::_deterministic_compliance`) that can
  never be "reasoned away" by the model. See `docs/COMPLIANCE.md`.
- **Connectors are swappable.** Social publishing, Canva, web research and analytics
  each sit behind a one-method interface with a clearly-marked `TODO(real-api)` —
  wiring a live API is a single-file change that never touches agent code.
- **Honest stubs.** Unconfigured publishers report "not configured" rather than
  faking a post. For demos, the orchestrator can *simulate* publishing
  (`BYF_SIMULATE_PUBLISH=true`) with a clearly-labelled `simulated://` reference.

## Model choice

`BYF_MODEL` (default `claude-opus-4-8`) drives the reasoning-heavy agents
(strategy, script, creative). `BYF_FAST_MODEL` (default
`claude-haiku-4-5-20251001`) drives the high-volume / low-creativity agents
(research, verify) via the `fast = True` flag on those agents.

## Extending

- **New platform:** add a `SocialPublisher` subclass and register it in
  `social/base.py::get_publisher`.
- **New agent / stage:** add a `BaseAgent` subclass + a schema, then call it from
  `Orchestrator`.
- **Real web trends:** implement `WebResearchConnector.fetch_signals` (e.g. a SERP/
  trends API, or expose the WebSearch tool to the research agent).
- **Scheduling:** wrap `Orchestrator.run_cycle` in a scheduler (cron / APScheduler)
  to make the pipeline fully autonomous on a cadence.
