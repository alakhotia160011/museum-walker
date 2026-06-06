"""Speech-to-text via ElevenLabs (Scribe).

The browser's Web Speech API is unreliable (no Firefox support, flaky Safari, needs
Google's servers in Chrome), so "Ask the artist" records the mic and transcribes here
instead — which works in every browser that can record audio. Uses the same
ELEVENLABS_API_KEY as TTS; returns None if unavailable so the client falls back to typing."""
from __future__ import annotations

import requests

from config import ELEVENLABS_API_KEY, HAS_TTS

_STT_MODEL = "scribe_v1"


def transcribe(audio: bytes, filename: str = "question.webm", content_type: str = "audio/webm"):
    """Return the transcribed text for an audio clip, or None if STT is unavailable
    or nothing intelligible was heard."""
    if not HAS_TTS or not audio:
        return None
    try:
        r = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            files={"file": (filename, audio, content_type)},
            data={"model_id": _STT_MODEL},
            timeout=60,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[stt] ElevenLabs failed: {e}")
        return None
    text = (r.json().get("text") or "").strip()
    return text or None
