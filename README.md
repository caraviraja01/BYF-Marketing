# Beyond Your Finance — Marketing Automation

An end-to-end, multi-agent marketing engine for **Beyond Your Finance (BYF)**. Six
specialised AI agents take a topic from market research all the way to a
publish-ready, compliance-checked social post — with a human approval gate before
anything goes live — and then learn from the analytics to improve the next cycle.

```
 ┌────────────┐   ┌──────────┐   ┌────────┐   ┌──────────┐   ┌────────┐   🧑 you   ┌─────────┐   ┌───────────┐
 │  Research  │──▶│ Strategy │──▶│ Script │──▶│ Creative │──▶│ Verify │──▶ review ─▶│ Publish │──▶│ Analytics │
 └────────────┘   └──────────┘   └────────┘   └──────────┘   └────────┘           └─────────┘   └─────┬─────┘
       ▲                                                                                               │
       └───────────────────────────── optimisation feedback ──────────────────────────────────────────┘
```

| # | Agent | Job |
|---|-------|-----|
| 1 | **Market Research** | Find trending finance topics + analyse competitor content, spot content gaps. |
| 2 | **Strategy** | Turn research into a content plan: pillars, cadence, ideas mapped to the funnel. |
| 3 | **Script** | Write platform-specific copy/scripts (hook → value → CTA) per channel. |
| 4 | **Creative** | Produce on-brand visuals via Canva (or detailed creative briefs). |
| 5 | **Verify** | QA for brand voice, platform rules, and **financial-marketing compliance**. |
| 6 | **Analytics** | Track traction after publishing and recommend what to do differently. |

The **human review gate** sits between Verify and Publish — nothing is posted until you
approve it in the dashboard.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add ANTHROPIC_API_KEY for real generation (optional)
python -m app.seed              # create the SQLite DB + demo data
uvicorn app.main:app --reload   # open http://localhost:8000
```

Run a full pipeline cycle from the CLI:

```bash
python -m app.cli run --topic "ELSS vs PPF for tax saving"
python -m app.cli run            # let the Research agent pick the topic
```

> **No API key?** The system runs out-of-the-box in **mock mode** — every agent
> returns realistic structured output so you can see the whole flow before wiring
> in credentials. Add `ANTHROPIC_API_KEY` to switch on real Claude generation.

## How "real" vs "scaffolded" works

| Capability | Status | Where to plug in |
|------------|--------|------------------|
| All 6 agents | **Real** (Claude) | `app/agents/*` — runs live with an API key |
| Trend / competitor web data | Pluggable | `app/integrations/web_research.py` |
| Canva creatives | Pluggable | `app/integrations/canva.py` |
| Social publishing (LinkedIn/IG/YouTube/X) | Stubbed behind one interface | `app/integrations/social/*` |
| Analytics fetch | Stubbed behind one interface | `app/integrations/analytics_providers.py` |

Each connector implements a clean interface, so swapping the stub for a live API is a
single-file change — no agent or pipeline code moves.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design and
[`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) for the financial-marketing guardrails.
