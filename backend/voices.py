"""Per-artwork voice selection for TTS.

Picks the best-fitting Cartesia voice for a stop so each artist (or the anonymous maker
of a culture) speaks in a voice that roughly matches gender and regional accent — instead
of one fixed narrator for everyone.

Voices are fetched live from the account's Cartesia library (GET /voices, cached in
memory) and matched on the real metadata Cartesia returns: `gender`
(masculine/feminine/gender_neutral) and `country` (ISO-3166 alpha-2, the accent/locale).
Accent matching is done within English voices; non-English narration uses the default
voice with Cartesia's multilingual model handling the language. If /voices can't be
reached, everything falls back to the configured/auto default voice.

A voice profile {gender, age, region} is inferred per stop (age is currently unused —
Cartesia exposes no age metadata): Claude for documented named artists (it knows their
gender and origin), and a metadata heuristic for anonymous or cultural makers.
"""
from __future__ import annotations

import json

import requests

from config import (
    CARTESIA_API_KEY,
    CARTESIA_VERSION,
    CARTESIA_VOICE_ID,
    CLAUDE_MODEL,
    HAS_CLAUDE,
    HAS_TTS,
)

# Region token -> ordered preference of ISO-3166 alpha-2 country codes (best-fit first),
# matched against the `country` of English Cartesia voices. Regions without a distinct
# English accent fall back to a neutral US/GB voice (gender still matches).
REGION_ACCENT = {
    "north_american":  ["US", "CA", "GB"],
    "british":         ["GB", "IE", "US"],
    "irish":           ["IE", "GB", "US"],
    "australian":      ["AU", "GB", "US"],
    "french":          ["FR", "GB", "US"],
    "italian":         ["IT", "GB", "US"],
    "iberian":         ["ES", "PT", "GB", "US"],
    "greek":           ["GR", "IT", "GB", "US"],
    "mediterranean":   ["IT", "GR", "GB", "US"],
    "german":          ["DE", "GB", "US"],
    "dutch":           ["NL", "GB", "US"],
    "nordic":          ["SE", "NO", "DK", "GB", "US"],
    "slavic":          ["RU", "PL", "GB", "US"],
    "middle_eastern":  ["GB", "US"],
    "north_african":   ["GB", "US"],
    "african":         ["US", "GB"],
    "east_asian":      ["US", "GB"],
    "south_asian":     ["IN", "GB", "US"],
    "southeast_asian": ["US", "GB"],
    "latin_american":  ["ES", "US", "GB"],
    "neutral":         ["US", "GB"],
}
REGIONS = list(REGION_ACCENT.keys())

# Culture / nationality / place keywords -> region token, for the heuristic (anonymous and
# cultural makers, and the no-Claude fallback). Checked against artist + department text.
_REGION_KEYWORDS = [
    (("american", "united states", "u.s."), "north_american"),
    (("english", "british", "britain", "scottish", "welsh"), "british"),
    (("irish", "ireland"), "irish"),
    (("australian", "australia"), "australian"),
    (("french", "france"), "french"),
    (("italian", "italy", "roman", "rome", "etruscan", "venetian", "florentine"), "italian"),
    (("spanish", "spain", "catalan", "portuguese", "portugal", "iberian"), "iberian"),
    (("greek", "greece", "minoan", "mycenaean", "cypriot", "hellenistic"), "greek"),
    (("german", "germany", "austrian", "austria", "swiss", "bavarian", "saxon"), "german"),
    (("dutch", "netherland", "flemish", "flanders", "holland", "netherlandish"), "dutch"),
    (("swedish", "norwegian", "danish", "finnish", "scandinav", "nordic", "icelandic"), "nordic"),
    (("russian", "polish", "czech", "slavic", "byzantine", "ukrainian", "serbian"), "slavic"),
    (("egypt", "nubian", "coptic"), "north_african"),
    (("islamic", "ottoman", "persian", "iran", "safavid", "arab", "levant", "turkish",
      "mesopotamia", "assyrian", "babylonian", "sumerian", "sasanian", "phoenician"), "middle_eastern"),
    (("china", "chinese", "japan", "japanese", "korea", "korean", "tibet"), "east_asian"),
    (("india", "indian", "mughal", "nepal", "pakistan", "sri lanka", "gandhara"), "south_asian"),
    (("thai", "khmer", "javanese", "vietnam", "indonesia", "burmese", "cambod"), "southeast_asian"),
    (("africa", "african", "benin", "yoruba", "congo", "mali", "ashanti", "kuba"), "african"),
    (("mexic", "aztec", "maya", "inca", "peru", "andean", "olmec", "latin"), "latin_american"),
]

# Departments whose region is unambiguous even when the artist label is bare.
_DEPT_REGION = {
    "egyptian art": "north_african",
    "islamic art": "middle_eastern",
    "asian art": "east_asian",
    "the american wing": "north_american",
}


def _heuristic_region(stop: dict) -> str:
    text = f"{stop.get('artist') or ''} {stop.get('department') or ''}".lower()
    for keys, region in _REGION_KEYWORDS:
        if any(k in text for k in keys):
            return region
    dept = (stop.get("department") or "").lower()
    if dept in _DEPT_REGION:
        return _DEPT_REGION[dept]
    if "greek and roman" in dept:
        return "mediterranean"
    if "european" in dept or "medieval" in dept:
        return "italian"  # generic continental-European stand-in
    return "neutral"


# --- Cartesia voice library (fetched once, cached) ---------------------------
_VOICES: list[dict] | None = None


def _norm_gender(g: str | None) -> str:
    g = (g or "").lower()
    if g in ("masculine", "male", "man"):
        return "male"
    if g in ("feminine", "female", "woman"):
        return "female"
    return "unknown"


def _load_voices() -> list[dict]:
    """English Cartesia voices as [{id, gender, country}], fetched once and cached.
    Empty if TTS is unconfigured or /voices can't be reached."""
    global _VOICES
    if _VOICES is not None:
        return _VOICES
    _VOICES = []
    if not HAS_TTS:
        return _VOICES
    try:
        r = requests.get(
            "https://api.cartesia.ai/voices",
            headers={"Authorization": f"Bearer {CARTESIA_API_KEY}", "Cartesia-Version": CARTESIA_VERSION},
            params={"limit": 100},
            timeout=20,
        )
        r.raise_for_status()
        j = r.json()
        items = j["data"] if isinstance(j, dict) and "data" in j else (j if isinstance(j, list) else [])
        for v in items:
            if (v.get("language") or "").lower() != "en":
                continue
            vid = v.get("id")
            if vid:
                _VOICES.append({"id": vid, "gender": _norm_gender(v.get("gender")),
                                "country": (v.get("country") or "").upper()})
    except requests.RequestException as e:
        print(f"[voices] could not list Cartesia voices ({e})")
    return _VOICES


def default_voice_id() -> str:
    """A sensible default voice: the configured one, else a feminine US voice, else any."""
    if CARTESIA_VOICE_ID:
        return CARTESIA_VOICE_ID
    vs = _load_voices()
    for v in vs:
        if v["gender"] == "female" and v["country"] == "US":
            return v["id"]
    return vs[0]["id"] if vs else ""


_profile_cache: dict[tuple, dict] = {}


def _looks_named(artist: str | None) -> bool:
    """Cheap check for whether `artist` is a documented individual worth a Claude lookup."""
    from narrator import _is_named  # shared heuristic; avoids duplicating the culture set

    return _is_named(artist)


def _infer_profile_claude(stop: dict) -> dict | None:
    regions = ", ".join(REGIONS)
    system = (
        "You assign a fitting first-person narration voice to the maker of a museum "
        "artwork. Reply with ONLY a compact JSON object, no prose, no code fence."
    )
    user = (
        f"Artwork:\n"
        f"- Title: {stop.get('title')}\n"
        f"- Maker: {stop.get('artist')}\n"
        f"- Date: {stop.get('date')}\n"
        f"- Department: {stop.get('department')}\n\n"
        f'Return JSON: {{"gender": "male"|"female"|"unknown", '
        f'"age": "young"|"middle"|"old"|"unknown", "region": one of [{regions}]}}\n'
        f"Rules:\n"
        f"- If the maker is a documented individual, use their actual gender and the regional "
        f"accent of their origin.\n"
        f"- If the maker is Unknown, anonymous, or a culture/people, set gender and age to "
        f'"unknown" and choose region from the culture or department. Never guess a gender '
        f"for an anonymous work.\n"
        f"- region must be exactly one token from the list."
    )
    from narrator import _get_client

    resp = _get_client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=120,
        system=[{"type": "text", "text": system}],
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    data = json.loads(text[start : end + 1])
    region = data.get("region")
    return {
        "gender": data.get("gender") if data.get("gender") in ("male", "female") else "unknown",
        "age": data.get("age") if data.get("age") in ("young", "middle", "old") else "unknown",
        "region": region if region in REGION_ACCENT else _heuristic_region(stop),
    }


def infer_profile(stop: dict) -> dict:
    """Return {gender, age, region} for the stop's maker, cached by (artist, department).
    Named individuals get a Claude lookup; anonymous/cultural makers use the heuristic."""
    key = ((stop.get("artist") or "").strip().lower(), (stop.get("department") or "").strip().lower())
    if key in _profile_cache:
        return _profile_cache[key]

    profile = {"gender": "unknown", "age": "unknown", "region": _heuristic_region(stop)}
    if HAS_CLAUDE and _looks_named(stop.get("artist")):
        try:
            claude = _infer_profile_claude(stop)
            if claude:
                profile = claude
        except Exception as e:  # never let voice inference break narration
            print(f"[voices] profile inference failed ({e}); using heuristic")

    _profile_cache[key] = profile
    return profile


def _stable_hash(s: str) -> int:
    """Small deterministic hash (Python's built-in hash() is salted per process)."""
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def select_voice(profile: dict, seed: str = "") -> str:
    """Score the fetched English voices against a profile and return the best-fit voice id.
    Gender is a hard filter when known; accent (country) is the soft preference; `seed`
    (the maker's identity) breaks ties deterministically so makers spread across voices."""
    voices = _load_voices()
    if not voices:
        return default_voice_id()

    gender = profile.get("gender")
    prefs = REGION_ACCENT.get(profile.get("region") or "neutral", REGION_ACCENT["neutral"])

    scored: list[tuple[int, dict]] = []
    for v in voices:
        if gender in ("male", "female") and v["gender"] not in (gender, "unknown"):
            continue  # don't give a male artist a clearly-female voice
        score = 0
        if v["country"] in prefs:
            score += (len(prefs) - prefs.index(v["country"])) * 2  # earlier pref = higher
        if gender in ("male", "female") and v["gender"] == gender:
            score += 1  # prefer an exact gender match over an unknown-gender voice
        scored.append((score, v))

    if not scored:
        return default_voice_id()
    top = max(s for s, _ in scored)
    best = [v for s, v in scored if s == top]
    return best[_stable_hash(seed) % len(best)]["id"]


def voice_for_stop(stop: dict) -> str:
    """Resolve the Cartesia voice id for a stop. Falls back to the default voice if
    anything goes wrong, so audio always has a usable voice."""
    try:
        seed = f"{stop.get('artist') or ''}|{stop.get('department') or ''}"
        return select_voice(infer_profile(stop), seed=seed)
    except Exception as e:
        print(f"[voices] voice_for_stop failed ({e}); using default voice")
        return default_voice_id()
