"""Text-to-speech via Cartesia (Sonic), cached to disk by content hash.

If CARTESIA_API_KEY is missing, synth() returns None and the frontend falls back
to the browser's built-in speech synthesis."""
from __future__ import annotations

import hashlib

import requests

import voices
from config import (
    CACHE_DIR,
    CARTESIA_API_KEY,
    CARTESIA_MODEL,
    CARTESIA_VERSION,
    HAS_TTS,
)

_AUDIO_CACHE = CACHE_DIR / "audio"
_AUDIO_CACHE.mkdir(exist_ok=True)

_TTS_URL = "https://api.cartesia.ai/tts/bytes"


def _key(text: str, vibe: str, voice_id: str, language: str) -> str:
    h = hashlib.sha1(f"{voice_id}|{vibe}|{language}|{text}".encode("utf-8")).hexdigest()
    return h[:20]


def cached_path(text: str, vibe: str, voice_id: str | None = None, language: str = "en"):
    vid = (voice_id or "").strip() or voices.default_voice_id()
    p = _AUDIO_CACHE / f"{_key(text, vibe, vid, language)}.mp3"
    return p if p.exists() else None


def synth(text: str, vibe: str = "Storyteller", voice_id: str | None = None, language: str = "en"):
    """Return a Path to an mp3 for `text`, or None if TTS is unavailable. `voice_id`
    selects the Cartesia voice (defaults to a configured/auto-picked narrator); `language`
    is an ISO code (en, es, fr, ...). Cached per (voice, vibe, language, text)."""
    if not HAS_TTS or not text.strip():
        return None

    vid = (voice_id or "").strip() or voices.default_voice_id()
    if not vid:
        return None  # no usable voice (couldn't reach /voices) -> browser fallback

    out = _AUDIO_CACHE / f"{_key(text, vibe, vid, language)}.mp3"
    if out.exists():
        return out

    def _post(voice_id: str):
        return requests.post(
            _TTS_URL,
            headers={
                "Authorization": f"Bearer {CARTESIA_API_KEY}",
                "Cartesia-Version": CARTESIA_VERSION,
                "Content-Type": "application/json",
            },
            json={
                "model_id": CARTESIA_MODEL,
                "transcript": text,
                "voice": {"mode": "id", "id": voice_id},
                "language": language or "en",
                "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000},
            },
            timeout=120,
        )

    content = None
    for candidate in [vid, voices.default_voice_id()]:
        if not candidate:
            continue
        try:
            r = _post(candidate)
            r.raise_for_status()
            content = r.content
            break
        except requests.RequestException as e:
            # A bad/unsupported voice shouldn't drop us to the browser voice — retry
            # once with the default Cartesia voice before giving up.
            print(f"[tts] Cartesia voice {candidate} failed: {e}")
            if candidate == vid and candidate != voices.default_voice_id():
                continue
            return None

    if not content:
        return None
    out.write_bytes(content)
    return out
