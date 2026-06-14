# Deploying the dashboard (Render)

This app is a **persistent Python web service** (FastAPI + SQLite), not a static
site — so it needs a host that runs Python processes. **Render** is the simplest
fit. (Netlify/Vercel are for static sites + short-lived JS/Go functions and can't
run this; a 4-minute pipeline would also blow past serverless timeouts.)

## One-time setup (≈5 minutes)

1. **Push the repo to GitHub** (done — branch `claude/relaxed-einstein-wern1x`).
2. Go to **https://render.com → New → Blueprint**.
3. Connect your GitHub and select this repo + branch. Render reads `render.yaml`
   and proposes a `byf-marketing` web service.
4. When prompted, set the **`ANTHROPIC_API_KEY`** secret (marked `sync: false`,
   so it's never stored in git). Use a **freshly rotated** key.
5. Click **Apply**. First build installs `requirements.txt` and boots
   `uvicorn app.main:app`.
6. Open the generated `https://byf-marketing-XXXX.onrender.com` URL.

## How it runs in production

- **Non-blocking pipeline.** Clicking "Run a new cycle" creates the run and kicks
  the multi-minute agent pipeline off in a **background task**; the run page
  auto-refreshes every 6s until it reaches the review gate. No request timeouts.
- **Publishing** stays in simulation mode (`BYF_SIMULATE_PUBLISH=true`) until you
  add real social credentials — approving + "publishing" produces a clearly
  labelled `simulated://` reference so you can test the full loop.

## Important caveats on the free plan

- **Ephemeral storage + spin-down.** Free instances sleep after ~15 min idle and
  reset their filesystem, so the SQLite DB (`/tmp/byf.db`) is wiped on restart.
  Great for testing; not for keeping data. First request after sleep is slow
  (cold start).
- **For persistence:** upgrade the instance and either attach a **Render Disk**
  (point `BYF_DB_URL` at the mounted path) or switch to a **managed Postgres**
  (`BYF_DB_URL=postgresql+psycopg://…`; SQLAlchemy already supports it).

## Env vars (set in `render.yaml`, secrets in the dashboard)

| Var | Purpose |
|-----|---------|
| `ANTHROPIC_API_KEY` | **Secret** — enables live Claude generation |
| `BYF_MODEL` / `BYF_FAST_MODEL` | Reasoning / fast model ids |
| `BYF_DB_URL` | Database URL (default ephemeral SQLite) |
| `BYF_SIMULATE_PUBLISH` | `true` until real social APIs are wired |

## Security

- Never commit `.env` or the API key (`.gitignore` already excludes `.env`).
- Set a **spend limit** on the Anthropic key — the dashboard is open by default;
  add auth (e.g. Render's basic-auth env, or an app-level login) before sharing
  the URL publicly, since anyone with the link can trigger paid Claude runs.
