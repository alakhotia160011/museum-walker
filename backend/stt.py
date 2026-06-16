"""Speech-to-text via Cartesia (Ink-Whisper, batch /stt endpoint).

The browser's Web Speech API is unreliable (no Firefox support, flaky Safari, needs
Google's servers in Chrome), so "Ask the artist" records the mic and transcribes here
instead — which works in every browser that can record audio. Uses the same
CARTESIA_API_KEY as TTS; returns None if unavailable so the client falls back to typing."""
from __future__ import annotations

import requests

from config import CARTESIA_API_KEY, CARTESIA_STT_MODEL, CARTESIA_VERSION, HAS_TTS

_STT_URL = "https://api.cartesia.ai/stt"


def transcribe(audio: bytes, filename: str = "question.webm",
               content_type: str = "audio/webm", language: str = "en"):
    """Return the transcribed text for an audio clip, or None if STT is unavailable
    or nothing intelligible was heard. `language` is an ISO code (en, es, ...)."""
    if not HAS_TTS or not audio:
        return None
    try:
        r = requests.post(
            _STT_URL,
            headers={
                "Authorization": f"Bearer {CARTESIA_API_KEY}",
                "Cartesia-Version": CARTESIA_VERSION,
            },
            files={"file": (filename, audio, content_type)},
            data={"model": CARTESIA_STT_MODEL, "language": language or "en"},
            timeout=60,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[stt] Cartesia failed: {e}")
        return None
    text = (r.json().get("text") or "").strip()
    return text or None
