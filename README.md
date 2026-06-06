# MET · Personalized Audio Guide

Tell the app **how long you have** and **what you care about**, and it crafts a
time-boxed, interest-tuned walking path through The Met with **AI-narrated audio**
for each stop. Built for people who don't have the time or attention span for a
full audio guide. (Inspired by [Artlas](https://www.artlas.art/en).)

## How it works
- **Data** — [MET Collection API](https://metmuseum.github.io/) (free, CC0). `seed_pool.py`
  bakes a curated set of on-view, image-rich works across a few departments into
  `backend/data/pool.json` so the demo is fast and rate-limit-proof.
- **Path-building** (`curator.py`) — time budget → number of stops; score works by
  interest-theme tag overlap (+ highlights); order by gallery for minimal backtracking.
- **Narration** (`narrator.py`) — Claude writes a spoken script per stop, tuned to your
  themes / knowledge level / vibe. Falls back to a readable template if no API key.
- **Voice** (`tts.py`) — ElevenLabs synth, cached. If no key, the frontend uses the
  browser's built-in speech synthesis.

## Run locally
```bash
# Backend
cd backend
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env          # optional: add ANTHROPIC_API_KEY + ELEVENLABS_API_KEY
./.venv/bin/python seed_pool.py   # builds data/pool.json (run once)
./.venv/bin/python app.py         # serves on :5050

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api to :5050)
```
Without API keys it still runs fully: template narration + your device's voice.
Add the keys to `backend/.env` to unlock real Claude scripts and ElevenLabs audio.

## Deploy to Vercel
The repo is configured for a single Vercel deployment (static frontend + Python
serverless API). From the project root:
```bash
npm i -g vercel       # if needed
vercel                # first deploy (link/create project)
vercel --prod         # production
```
Then in the Vercel dashboard → Project → Settings → Environment Variables, add:
- `ANTHROPIC_API_KEY`
- `ELEVENLABS_API_KEY` (optional; without it, browser voice is used)

`vercel.json` builds `frontend/` to static, runs `api/index.py` as the Flask
serverless function, bundles `backend/**` (including `pool.json`), and rewrites
`/api/*` to the function. The audio cache writes to `/tmp` (ephemeral per instance,
which is fine — it's just a cache).

> Note: serverless functions have a time limit (set to 60s here) and an ephemeral
> filesystem. That's fine for this app. If you'd rather run the backend as a
> always-on server with a persistent audio cache, deploy `backend/` to Render/Railway
> and point the frontend's `BASE` in `frontend/src/api.js` at that URL.

## Tuning
- Departments, timing, and models: `backend/config.py`
- Interest themes → MET tag keywords: `backend/themes.py`
