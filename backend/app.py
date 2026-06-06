"""Flask JSON API for the personalized MET audio guide."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

import curator
import narrator
import tts
from config import HAS_CLAUDE, HAS_TTS
from themes import theme_list

app = Flask(__name__)
CORS(app)


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
    must_see = bool(body.get("mustSee", True))

    stops = curator.build_itinerary(minutes, themes, level, must_see)

    # Generate narration scripts concurrently (fast when using the fallback; with
    # Claude this overlaps the per-stop latency).
    def make(stop):
        result = narrator.generate_script(stop, themes, level, vibe)
        stop["script"] = result["script"]
        stop["estSeconds"] = result["estSeconds"]
        stop["scriptSource"] = result["source"]
        return stop

    if stops:
        with ThreadPoolExecutor(max_workers=min(8, len(stops))) as ex:
            stops = list(ex.map(make, stops))

    # Total tour time = listening + walking/viewing buffer per stop.
    from config import WALK_BUFFER_MINUTES

    total_seconds = sum(s["estSeconds"] for s in stops) + int(len(stops) * WALK_BUFFER_MINUTES * 60)
    return jsonify(
        {
            "meta": {
                "requestedMinutes": minutes,
                "themes": themes,
                "level": level,
                "vibe": vibe,
                "mustSee": must_see,
                "stopCount": len(stops),
                "estMinutes": round(total_seconds / 60, 1),
                "hasTts": HAS_TTS,
            },
            "stops": stops,
        }
    )


@app.post("/api/audio")
def audio():
    """Synthesize (or serve cached) speech for a script. Stateless: the client posts
    the script text it already has. Returns mp3, or 204 if TTS is unavailable."""
    body = request.get_json(force=True) or {}
    text = (body.get("text") or "").strip()
    vibe = body.get("vibe", "Storyteller")
    if not text:
        return jsonify({"error": "missing text"}), 400
    path = tts.synth(text, vibe)
    if not path:
        return ("", 204)  # signal: client should use browser speech synthesis
    return send_file(path, mimetype="audio/mpeg")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
