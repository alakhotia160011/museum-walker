"""Flask JSON API for the personalized MET audio guide."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

import curator
import met_client
import narrator
import stt
import tts
import voices
from config import HAS_CLAUDE, HAS_TTS
from themes import theme_list

app = Flask(__name__)
CORS(app)

# Onboarding language labels -> ISO codes Cartesia accepts (TTS + STT).
LANG_CODE = {
    "english": "en", "spanish": "es", "french": "fr", "german": "de",
    "italian": "it", "mandarin": "zh", "japanese": "ja", "hindi": "hi",
}


def _lang_code(label) -> str:
    return LANG_CODE.get((label or "English").strip().lower(), "en")


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/config")
def get_config():
    """Tells the frontend whether real AI voice is available (else use browser TTS)."""
    return jsonify({"hasClaude": HAS_CLAUDE, "hasTts": HAS_TTS, "poolSize": len(curator.load_pool())})


@app.get("/api/themes")
def get_themes():
    return jsonify({"themes": theme_list()})


@app.post("/api/itinerary")
def itinerary():
    body = request.get_json(force=True) or {}
    minutes = int(body.get("minutes", 45))
    themes = body.get("themes") or []
    level = body.get("level", "Casual")
    vibe = body.get("vibe", "Storyteller")
    eras = body.get("eras") or []
    language = body.get("language", "English")
    must_see = bool(body.get("mustSee", True))

    # Pick more candidates than we need, then drop any without an image so the tour is
    # never padded with "image unavailable" plates. Narration is NOT generated here - it's
    # produced per stop on demand (/api/narrate) so the route appears fast.
    n, candidates = curator.select_candidates(minutes, themes, level, must_see, eras)

    def hydrate(stop):
        if stop.get("image"):
            return stop  # baked URL already present — no MET call
        obj = met_client.get_object(stop["objectID"])
        if obj:
            img = obj.get("primaryImageSmall") or obj.get("primaryImage") or ""
            stop["image"] = img
            stop["imageLarge"] = obj.get("primaryImage") or img
        return stop

    need = [c for c in candidates if not c.get("image")]
    if need:
        with ThreadPoolExecutor(max_workers=min(12, len(need))) as ex:
            list(ex.map(hydrate, need))

    imaged = [c for c in candidates if c.get("image")]
    keep = imaged[:n] if len(imaged) >= n else (imaged + [c for c in candidates if not c.get("image")])[:n]
    stops = curator.finalize(keep)

    # Total tour time = listening + walking/viewing buffer per stop (target-based estimate).
    from config import WALK_BUFFER_MINUTES

    total_seconds = sum(s["estSeconds"] for s in stops) + int(len(stops) * WALK_BUFFER_MINUTES * 60)
    return jsonify(
        {
            "meta": {
                "requestedMinutes": minutes,
                "themes": themes,
                "level": level,
                "vibe": vibe,
                "eras": eras,
                "language": language,
                "mustSee": must_see,
                "stopCount": len(stops),
                "estMinutes": round(total_seconds / 60, 1),
                "hasTts": HAS_TTS,
            },
            "stops": stops,
        }
    )


@app.post("/api/narrate")
def narrate():
    """Generate the spoken narration for a single stop, on demand. The walking cue
    (stop.transition) is appended so the guide leads you onward in the audio."""
    body = request.get_json(force=True) or {}
    stop = body.get("stop") or {}
    themes = body.get("themes") or []
    level = body.get("level", "Casual")
    vibe = body.get("vibe", "Storyteller")
    language = body.get("language", "English")
    english = (language or "English").strip().lower() == "english"
    # Resolve the artist's voice in parallel with writing the script so picking a
    # gender/age/accent-matched voice adds no latency. Accent-matching is English-only —
    # for other languages we use the default multilingual voice (no forced accent).
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_script = ex.submit(narrator.generate_script, stop, themes, level, vibe, language)
        f_voice = ex.submit(voices.voice_for_stop, stop) if english else None
        result = f_script.result()
        voice_id = f_voice.result() if f_voice else None
    script = result["script"]
    cue = (stop.get("transition") or "").strip()
    spoken = f"{script.rstrip()} {cue}".strip() if cue else script
    return jsonify({
        "script": script,        # printed essay (no walking cue)
        "spoken": spoken,        # what the voice reads (narration + walking cue)
        "source": result["source"],
        "estSeconds": result["estSeconds"],
        "voiceId": voice_id,     # the matched artist voice for /api/audio
    })


@app.post("/api/intro")
def intro():
    """A spoken welcome that orients the visitor (where we start, which wings/floors,
    the scope) before they dive into the first work."""
    body = request.get_json(force=True) or {}
    result = narrator.route_intro(
        body.get("summary") or {},
        level=body.get("level", "Casual"),
        vibe=body.get("vibe", "Storyteller"),
        themes=body.get("themes") or [],
        eras=body.get("eras") or [],
        language=body.get("language", "English"),
    )
    return jsonify({"intro": result["intro"], "source": result["source"]})


@app.post("/api/ask")
def ask():
    """Answer a visitor's question about the current artwork in the docent voice.
    Stateless: the client posts the stop it's on plus a short conversation history."""
    body = request.get_json(force=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "missing question"}), 400
    stop = body.get("stop") or {}
    result = narrator.answer_question(
        stop,
        question,
        level=body.get("level", "Casual"),
        vibe=body.get("vibe", "Storyteller"),
        themes=body.get("themes") or [],
        eras=body.get("eras") or [],
        history=body.get("history") or [],
        next_stop=body.get("nextStop"),
        language=body.get("language", "English"),
    )
    return jsonify({"answer": result["answer"], "source": result["source"]})


@app.post("/api/transcribe")
def transcribe():
    """Transcribe a recorded question clip to text (Cartesia Ink-Whisper). The client
    records the mic and posts the audio as multipart 'audio'. Returns {text, ok}."""
    f = request.files.get("audio")
    if f is None:
        return jsonify({"error": "missing audio"}), 400
    language = _lang_code(request.form.get("language"))
    text = stt.transcribe(f.read(), f.filename or "question.webm", f.mimetype or "audio/webm", language)
    return jsonify({"text": text or "", "ok": bool(text)})


@app.get("/api/debug/voices")
def debug_voices():
    """Temporary: paginate ALL Cartesia voices and report country/language coverage."""
    import requests as _rq
    from collections import Counter
    from config import CARTESIA_API_KEY, CARTESIA_VERSION
    hdr = {"Authorization": f"Bearer {CARTESIA_API_KEY}", "Cartesia-Version": CARTESIA_VERSION}
    items, after, pages = [], None, 0
    try:
        while pages < 15:
            params = {"limit": 100}
            if after:
                params["starting_after"] = after
            r = _rq.get("https://api.cartesia.ai/voices", headers=hdr, params=params, timeout=20)
            j = r.json()
            page = j.get("data", []) if isinstance(j, dict) else (j if isinstance(j, list) else [])
            items += page
            pages += 1
            if not (isinstance(j, dict) and j.get("has_more") and page):
                break
            after = page[-1].get("id")
            if not after:
                break
    except Exception as e:
        return jsonify({"error": str(e), "got": len(items)}), 500
    return jsonify({
        "pages": pages,
        "total": len(items),
        "country_hist": dict(Counter((v.get("country") or "?") for v in items)),
        "lang_hist": dict(Counter((v.get("language") or "?") for v in items)),
        "lang_country_pairs": dict(Counter(f"{(v.get('language') or '?')}/{(v.get('country') or '?')}" for v in items)),
    })


@app.post("/api/audio")
def audio():
    """Synthesize (or serve cached) speech for a script. Stateless: the client posts
    the script text it already has. Returns mp3, or 204 if TTS is unavailable."""
    body = request.get_json(force=True) or {}
    text = (body.get("text") or "").strip()
    vibe = body.get("vibe", "Storyteller")
    voice_id = body.get("voiceId")
    language = _lang_code(body.get("language"))
    if not text:
        return jsonify({"error": "missing text"}), 400
    path = tts.synth(text, vibe, voice_id, language)
    if not path:
        return ("", 204)  # signal: client should use browser speech synthesis
    return send_file(path, mimetype="audio/mpeg")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
