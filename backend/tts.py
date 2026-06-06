"""Text-to-speech via ElevenLabs, cached to disk by content hash.

If ELEVENLABS_API_KEY is missing, synth() returns None and the frontend falls back
to the browser's built-in speech synthesis."""
from __future__ import annotations

import hashlib

import requests

from config import (
    CACHE_DIR,
    ELEVENLABS_API_KEY,
    ELEVENLABS_MODEL,
    ELEVENLABS_VOICE_ID,
    HAS_TTS,
)

_AUDIO_CACHE = CACHE_DIR / "audio"
_AUDIO_CACHE.mkdir(exist_ok=True)


def _key(text: str, vibe: str) -> str:
    h = hashlib.sha1(f"{ELEVENLABS_VOICE_ID}|{vibe}|{text}".encode("utf-8")).hexdigest()
    return h[:20]


def cached_path(text: str, vibe: str):
    p = _AUDIO_CACHE / f"{_key(text, vibe)}.mp3"
    return p if p.exists() else None


def synth(text: str, vibe: str = "Storyteller"):
    """Return a Path to an mp3 for `text`, or None if TTS is unavailable.
    Cached so repeated/identical requests are instant."""
    if not HAS_TTS or not text.strip():
        return None

    out = _AUDIO_CACHE / f"{_key(text, vibe)}.mp3"
    if out.exists():
        return out

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    try:
        r = requests.post(
            url,
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "accept": "audio/mpeg",
                "content-type": "application/json",
            },
            json={
                "text": text,
                "model_id": ELEVENLABS_MODEL,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=120,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[tts] ElevenLabs failed: {e}")
        return None

    out.write_bytes(r.content)
    return out
