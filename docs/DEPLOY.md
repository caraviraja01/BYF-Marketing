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

## Persistence (run history)

The blueprint provisions a **free Render Postgres** (`byf-db`) and wires
`BYF_DB_URL` to its connection string, so **run history persists** across restarts
and redeploys. (The web instance's own filesystem is ephemeral — that's why SQLite
history vanished before.) The app rewrites `postgres://` URLs to the psycopg driver
automatically. Free Render Postgres expires after ~30 days; recreate it or upgrade
to keep data longer. Locally it still defaults to SQLite.

## Important caveats on the free plan

- **Spin-down.** Free web instances sleep after ~15 min idle; the first request
  after is a slow cold start. History itself is safe in Postgres.
- **Creative generation** (Higgsfield image/video) runs as a background job and can
  take a few minutes; the item page auto-refreshes until the asset is ready.

## Daily calendar preparation

A cycle now schedules a **7-day content calendar** as items; only **today's** item is
prepared immediately, the rest stay `scheduled` and are prepared **one day at a time**.

- **Manual:** the cycle's Content tab has a **"Prepare next day"** button.
- **Automatic:** point a cron at
  `https://<your-app>/tasks/prepare-daily?token=<BYF_CRON_TOKEN>` once a day. Use
  **Render Cron Jobs** (`curl` the URL) or a free service like cron-job.org. The
  endpoint is token-protected (no login needed) and prepares every item due that day.
  Render auto-generates `BYF_CRON_TOKEN`; copy its value from the dashboard into the
  cron's URL.

## Env vars (set in `render.yaml`, secrets in the dashboard)

| Var | Purpose |
|-----|---------|
| `ANTHROPIC_API_KEY` | **Secret** — enables live Claude generation |
| `BYF_MODEL` / `BYF_FAST_MODEL` | Reasoning / fast model ids |
| `BYF_DB_URL` | Database URL (default ephemeral SQLite) |
| `BYF_SIMULATE_PUBLISH` | `true` until real social APIs are wired |

## Security

- Never commit `.env` or the API key (`.gitignore` already excludes `.env`).
- **Protect the URL with the built-in login.** Set **`BYF_AUTH_PASSWORD`** (and
  optionally `BYF_AUTH_USERNAME`, default `admin`) in the Render dashboard. Login
  is enforced whenever a password is set — every page redirects to `/login` until
  you sign in. `render.yaml` auto-generates `BYF_SECRET_KEY` to sign the session
  cookie. Without a password the dashboard is open (handy for local dev only).
- Set a **spend limit** on the Anthropic key as a backstop, since an authenticated
  user can trigger paid Claude runs.
