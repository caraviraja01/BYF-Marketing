# Beyond Your Finance — Platform

This repo now hosts **two** products on one FastAPI + Claude stack:

1. **YourChartered.AI** — a client- and public-facing **AI Q&A platform** for finance,
   tax, accounting and startup questions. Every answer ends with the firm's compliance
   disclaimer and offers **Copy** and **💬 Connect an Expert** buttons. "Connect an
   Expert" opens a **live, WhatsApp-style chat** (WebSockets) with a Beyond Your Finance
   chartered accountant.
2. **Marketing Automation** — the firm-internal multi-agent content engine (below),
   reachable at `/dashboard` for admins.

## YourChartered.AI

| Route | Who | What |
|-------|-----|------|
| `/signup`, `/login` | everyone | Account-based access (roles: user / expert / admin). |
| `/ask` | users | ChatGPT-style threads answered live by Claude in the BYF voice. |
| `/expert` | experts | Inbox of "Connect an Expert" requests — claim one to chat live. |
| `/chat/{id}` | both | Real-time WhatsApp-style room over `ws://…/ws/chat/{id}`. |

After login each role lands on its home (`/` redirects: admin → `/dashboard`, expert →
`/expert`, everyone else → `/ask`). With no `ANTHROPIC_API_KEY` the assistant returns a
useful on-brand placeholder so the whole flow is clickable offline.

**Demo logins** (seeded automatically in non-production):
`admin@byf.test` / `admin123` · `expert@byf.test` / `expert123` · `user@byf.test` / `user123`.
In production, set `BYF_AUTH_USERNAME` / `BYF_AUTH_PASSWORD` to bootstrap the admin
account, and let clients self-serve via `/signup`.

---

# Marketing Automation

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
| Creatives — images, carousels & video (Higgsfield) | **Real** (submit + poll) | `app/integrations/higgsfield.py` |
| Social publishing (LinkedIn/IG/YouTube/X) | Stubbed behind one interface | `app/integrations/social/*` |
| Analytics fetch | Stubbed behind one interface | `app/integrations/analytics_providers.py` |

**Human-in-the-loop choices:** the Script and Creative agents each produce **3
variants** per content item; you pick one per tab in the dashboard, the chosen pair
is re-verified, and only then is it approved/published. If a live agent call fails,
the run falls back to a draft and flags it (a warning) rather than dying.

Each connector implements a clean interface, so swapping the stub for a live API is a
single-file change — no agent or pipeline code moves.

## Deploy

Host the dashboard on **Render** (a persistent Python service — not Netlify/Vercel,
which can't run this). A `render.yaml` blueprint is included; full steps in
[`docs/DEPLOY.md`](docs/DEPLOY.md). Running a cycle executes in a background task,
so the multi-minute pipeline never times out the request.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design and
[`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) for the financial-marketing guardrails.
