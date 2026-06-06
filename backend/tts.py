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


def _key(text: str, vibe: str, voice_id: str) -> str:
    h = hashlib.sha1(f"{voice_id}|{vibe}|{text}".encode("utf-8")).hexdigest()
    return h[:20]


def cached_path(text: str, vibe: str, voice_id: str | None = None):
    vid = (voice_id or "").strip() or ELEVENLABS_VOICE_ID
    p = _AUDIO_CACHE / f"{_key(text, vibe, vid)}.mp3"
    return p if p.exists() else None


def synth(text: str, vibe: str = "Storyteller", voice_id: str | None = None):
    """Return a Path to an mp3 for `text`, or None if TTS is unavailable. `voice_id`
    selects the ElevenLabs voice (defaults to the configured narrator). Cached per
    (voice, vibe, text) so repeated/identical requests are instant."""
    if not HAS_TTS or not text.strip():
        return None

    vid = (voice_id or "").strip() or ELEVENLABS_VOICE_ID
    out = _AUDIO_CACHE / f"{_key(text, vibe, vid)}.mp3"
    if out.exists():
        return out

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
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
