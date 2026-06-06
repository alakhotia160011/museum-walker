"""Central config: scope, timing constants, model + voice settings.

Everything here is tunable live for the demo (departments, timing, models)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
# Cache must be writable. On serverless hosts (Vercel) only /tmp is writable, so
# allow an override; default there to /tmp via the CACHE_DIR env var.
CACHE_DIR = Path(os.getenv("CACHE_DIR") or (BASE_DIR / "cache"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

# --- MET scope: a few departments with strong on-view, image-rich highlights ---
DEPARTMENTS = {
    11: "European Paintings",
    10: "Egyptian Art",
    14: "Islamic Art",
}
# How many candidate objects to pull per department when seeding the pool.
SEED_PER_DEPARTMENT = 25

MET_API_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"

# --- Timing model (minutes) -------------------------------------------------
# Average listening time per stop by knowledge level, plus walking/viewing buffer.
LISTEN_MINUTES = {"Casual": 1.5, "Enthusiast": 2.5, "Expert": 3.5}
WALK_BUFFER_MINUTES = 1.5
WORDS_PER_MINUTE = 150  # speaking pace, used to size scripts + estimate duration

# --- AI settings ------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = "claude-sonnet-4-6"  # fast + cheap enough for many stops

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
# "Rachel" — a common default ElevenLabs voice id.
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip() or "21m00Tcm4TlvDq8ikWAM"
ELEVENLABS_MODEL = "eleven_turbo_v2_5"

HAS_CLAUDE = bool(ANTHROPIC_API_KEY)
HAS_TTS = bool(ELEVENLABS_API_KEY)
