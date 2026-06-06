"""Vercel Python serverless entry point.

Vercel's @vercel/python runtime serves a module-level WSGI `app`. We add the
backend package to the path and re-export the Flask app. All /api/* routes are
rewritten to this function (see vercel.json), and Flask sees the original path."""
import os
import sys
from pathlib import Path

# Make the backend modules importable when bundled by Vercel.
BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

# Audio cache must live in the only writable dir on Vercel.
os.environ.setdefault("CACHE_DIR", "/tmp/met-audio-cache")

from app import app  # noqa: E402  (Flask WSGI app)

# Vercel looks for `app`.
