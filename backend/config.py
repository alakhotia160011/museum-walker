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

# --- MET scope: the full museum. Every collecting department; we seed all of
# their *on-view, imaged* works so the guide can route you through the real galleries.
DEPARTMENTS = {
    1: "The American Wing",
    3: "Ancient Near Eastern Art",
    4: "Arms and Armor",
    5: "Arts of Africa, Oceania, and the Americas",
    6: "Asian Art",
    7: "The Cloisters",
    8: "The Costume Institute",
    9: "Drawings and Prints",
    10: "Egyptian Art",
    11: "European Paintings",
    12: "European Sculpture and Decorative Arts",
    13: "Greek and Roman Art",
    14: "Islamic Art",
    15: "The Robert Lehman Collection",
    16: "The Libraries",
    17: "Medieval Art",
    18: "Musical Instruments",
    19: "Photographs",
    21: "Modern and Contemporary Art",
}
# Per-department cap when seeding. None = no cap (take every on-view, imaged work).
SEED_PER_DEPARTMENT = None
# Source of bulk metadata: the Met's Open Access dataset (Git LFS CSV on GitHub).
# Lets us hydrate metadata for the whole on-view set without per-object API calls.
OPENACCESS_CSV_URL = (
    "https://media.githubusercontent.com/media/metmuseum/openaccess/master/MetObjects.csv"
)

MET_API_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"

# --- Path coherence: how many departments (wings) a single tour may span, by time.
# Keeps a walk geographically tight instead of scattering across the museum.
def department_budget(minutes: int) -> int:
    if minutes <= 25:
        return 1
    if minutes <= 60:
        return 2
    return 3

# --- Timing model (minutes) -------------------------------------------------
# Average listening time per stop by knowledge level, plus walking/viewing buffer.
LISTEN_MINUTES = {"Casual": 1.5, "Enthusiast": 2.5, "Expert": 3.5}
WALK_BUFFER_MINUTES = 1.5
WORDS_PER_MINUTE = 150  # speaking pace, used to size scripts + estimate duration

# --- AI settings ------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = "claude-sonnet-4-6"           # quality, used for Q&A
CLAUDE_FAST_MODEL = "claude-haiku-4-5"        # fast, used for per-stop narration/intro/voice

# --- Voice: Cartesia (TTS + STT) --------------------------------------------
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "").strip()
# Optional default voice id (UUID). If blank, voices.py picks one from /voices.
CARTESIA_VOICE_ID = os.getenv("CARTESIA_VOICE_ID", "").strip()
CARTESIA_MODEL = os.getenv("CARTESIA_MODEL", "").strip() or "sonic-2"  # multilingual TTS
CARTESIA_STT_MODEL = "ink-whisper"
CARTESIA_VERSION = "2026-03-01"  # required Cartesia-Version header

HAS_CLAUDE = bool(ANTHROPIC_API_KEY)
HAS_TTS = bool(CARTESIA_API_KEY)
