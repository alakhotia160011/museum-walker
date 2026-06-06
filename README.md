# Docent · A Personalized Audio Walk Through The Met

**Live:** https://museum-walker.vercel.app

Tell the app **how long you have** and **what you care about**, and it composes a
time-boxed, interest-tuned, *walkable* route through The Metropolitan Museum of Art —
with a Claude-written narration for each stop, voiced by ElevenLabs (or your device).
You can ask the on-screen docent questions about any work as you go. Built for people
who don't have the time or attention span for a full audio guide.
(Inspired by [Artlas](https://www.artlas.art/en).)

The interface — "Docent" — is a quiet monochrome ink-on-paper exhibition catalog
(Fraunces + Hanken Grotesk); the artwork is the only colour on screen.

## How it works

The pipeline is **data → curate → optimize route → narrate → voice**, with an
interactive Q&A layered on the player.

- **Data — the whole on-view museum.** [`seed_pool.py`](backend/seed_pool.py) builds
  `backend/data/pool.json` (~49,500 works) from The Met's
  [Open Access dataset](https://github.com/metmuseum/openaccess). A work is "on view"
  iff it has a **Gallery Number**, which is the reliable on-view signal (the Search
  API's `isOnView` filter badly undercounts). Titles/fields are de-HTML'd at seed time.
- **Real gallery coordinates.** [`seed_map.py`](backend/seed_map.py) bakes
  `backend/data/gallery_coords.json` — `gallery → {lat, lng, floor, floorId, building}`
  for ~455 galleries — by decoding the Met's public
  [Living Map](https://maps.metmuseum.org) vector tiles. This places ~99% of on-view
  works on the real floor plan and is what makes location-aware routing possible.
- **Curation** ([`curator.py`](backend/curator.py)) — time budget → number of stops;
  score works by interest-theme tag overlap (+ highlights); **cluster into 1–3 adjacent
  wings** by time so a tour doesn't crisscross the building; then hand the chosen works
  to the route optimizer.
- **Route optimization** ([`geo.py`](backend/geo.py)) — orders the stops for the
  shortest, least-stair-heavy walk. See [Optimizing for location](#optimizing-for-location).
- **Narration** ([`narrator.py`](backend/narrator.py)) — Claude writes a spoken script
  per stop, tuned to your themes / knowledge level / vibe, with a **floor-aware walking
  cue** woven in ("take the stairs up to the second floor and find Gallery 824…").
  Falls back to a readable template if no API key.
- **Q&A** (`narrator.answer_question` → `POST /api/ask`) — ask the docent anything about
  the current work; Claude answers in the docent voice, grounded in the metadata (no
  invented facts), with multi-turn follow-ups and "where do I go next?" support.
- **Voice** ([`tts.py`](backend/tts.py)) — ElevenLabs synth, cached by content hash. No
  key → the browser's built-in speech synthesis. Q&A answers get their own play button.

## Optimizing for location

The selection step decides *what* you see (relevance); the optimizer decides the *order*
you see it in (a walkable path). `curator.build_itinerary` calls
[`geo.order_route(stops)`](backend/geo.py) instead of a naïve gallery-number sort. The
algorithm, in order of priority:

1. **Partition by building.** Fifth Avenue and The Cloisters are ~9.5 km apart — never
   interleave them. (In practice a themed tour stays in one building.)
2. **Batch by floor, ascending.** Within a building, group stops by floor and visit floors
   bottom-to-top. Because `floorId` is monotonic with height, this yields the *minimum
   possible* number of stair/elevator changes: `(#distinct floors − 1)`. Eliminating
   floor-hopping is the single biggest comfort win and is prioritized over raw distance.
3. **Shortest walk within each floor.** Solve an open-path TSP per floor —
   nearest-neighbour seeded at an anchor, then 2-opt refinement (stop counts are small, so
   this is exact-enough and instant). Distances are equirectangular metres from the baked
   lat/lng.
4. **Sensible start & flow.** The first floor's path is seeded at the Met's **Great Hall
   entrance**; each subsequent floor is seeded at the stop nearest the previous floor's
   exit — approximating where you arrive off the stairs.
5. **Graceful degradation.** A work whose gallery has no coordinate (e.g. "in Great Hall")
   is appended at the end, never dropped. If the coords file is missing entirely, the whole
   route falls back to the original `(department, gallery number)` sort.

The ordering is fully **deterministic** (stable tie-breaks), which keeps the audio cache
valid. Measured across test tours, this takes a route that bounced floors up to 5× down to
the theoretical minimum, for comparable or shorter total walking distance.

> Honest limit: the Met publishes gallery coordinates but not a stairwell/corridor graph,
> so "take the stairs" is a floor-aware cue, not turn-by-turn wayfinding. The baked
> coordinates are also the foundation for a future on-screen floor-plan map.

## Run locally

```bash
# Backend
cd backend
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env          # optional: add ANTHROPIC_API_KEY + ELEVENLABS_API_KEY
./.venv/bin/python seed_pool.py   # build data/pool.json (downloads the ~300MB Open Access CSV once, then cached)
./.venv/bin/python seed_map.py    # build data/gallery_coords.json from the Living Map tiles
./.venv/bin/python app.py         # serves on :5050

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api to :5050)
```

`pool.json` and `gallery_coords.json` are committed, so you only need to re-run the seed
scripts to refresh the data. Without API keys the app still runs fully: template narration,
metadata-based Q&A fallback, and your device's voice. Add the keys to `backend/.env` for
real Claude scripts/answers and ElevenLabs audio.

`seed_map.py` needs `mapbox-vector-tile` (a dev-only dependency, not required at runtime):
`./.venv/bin/pip install mapbox-vector-tile`.

## Deploy to Vercel

Single deployment: static frontend + a Python serverless function. From the project root:

```bash
vercel --prod
```

[`vercel.json`](vercel.json) builds `frontend/` to static, runs [`api/index.py`](api/index.py)
as the Flask serverless function, bundles `backend/**` (including the JSON data), and
rewrites `/api/*` to the function. The audio cache writes to `/tmp` (ephemeral per
instance — fine, it's only a cache).

Two settings to get right in the Vercel dashboard (Project → Settings):
- **Root Directory** must be the repo root (empty), *not* `frontend/` — otherwise the
  build can't find `frontend/` and the Python API never deploys.
- **Environment Variables** → add `ANTHROPIC_API_KEY` and `ELEVENLABS_API_KEY`
  (optional: `ELEVENLABS_VOICE_ID`). Env vars only apply to **new** deployments, so
  redeploy after adding them. `/api/config` reports `hasClaude` / `hasTts`.

Cost note: with keys set, every itinerary builds Claude scripts and every question/▶ is a
live Claude/ElevenLabs call on your account — fine for a demo, worth knowing for a public link.

## Project layout

```
backend/
  app.py           Flask API: /api/config, /api/themes, /api/itinerary, /api/audio, /api/ask
  curator.py       stop selection, wing clustering, floor-aware transitions
  geo.py           coordinate-aware route optimizer (building → floor → TSP)
  narrator.py      Claude narration scripts + "Ask the docent" Q&A (+ fallbacks)
  tts.py           ElevenLabs synthesis, content-hash cached
  themes.py        interest themes → Met tag keywords
  config.py        departments, timing, models, voice, per-tour wing budget
  seed_pool.py     build data/pool.json from the Open Access CSV
  seed_map.py      build data/gallery_coords.json from Living Map tiles
frontend/src/
  App.jsx          screen flow: compose → curating → route → stop
  components/      Onboarding (Compose), Curating, Itinerary (Route), Player (Stop)
  styles.css       the "Docent" monochrome design system
```

## Tuning
- Departments, timing, models, and the per-tour wing budget: [`backend/config.py`](backend/config.py)
- Interest themes → Met tag keywords: [`backend/themes.py`](backend/themes.py)
- Narration voice/level personas and the Q&A system prompt: [`backend/narrator.py`](backend/narrator.py)
- Route optimizer (floor penalty model, entrance anchor): [`backend/geo.py`](backend/geo.py)
