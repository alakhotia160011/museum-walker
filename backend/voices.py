"""Per-artwork voice selection for TTS.

Picks the best-fitting ElevenLabs voice for a stop from a small curated palette, so
each artist (or the anonymous maker of a culture) speaks in a voice that roughly
matches gender, age, and regional accent — instead of one fixed narrator for everyone.

The palette uses ElevenLabs' stable premade voices, which are present on every account.
That keeps the feature reliable and free of voice-generation latency, but it bounds
accent coverage: European / anglophone makers match well (US, British, Irish, Australian,
Italian, Nordic), while many world cultures (e.g. East Asian, Middle Eastern, African,
Latin American) have no premade accent and fall back to a neutral voice with gender and
age still matched. To improve accent coverage, add richer ElevenLabs Voice Library IDs to
PALETTE with the appropriate `accent` tag — the scorer will use them automatically.

A voice profile {gender, age, region} is inferred per stop: Claude for documented named
artists (it knows their gender, origin, and era), and a metadata heuristic for anonymous
or cultural makers (region from the culture/department; gender and age stay 'unknown' —
we never guess gender for an anonymous work).
"""
from __future__ import annotations

import json

from config import CLAUDE_MODEL, HAS_CLAUDE, ELEVENLABS_VOICE_ID

# Curated palette of ElevenLabs premade voices. accent ∈ {us, gb, ie, au, it, se}.
# Each gender carries young/middle/old so age can always be matched within a gender.
PALETTE = [
    # --- female ---
    {"voiceId": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel",    "gender": "female", "accent": "us", "age": "young",  "tone": "calm"},
    {"voiceId": "XB0fDUnXU5powFXDhCwa", "name": "Charlotte", "gender": "female", "accent": "se", "age": "young",  "tone": "warm"},
    {"voiceId": "EXAVITQu4vr4xnSDxMaL", "name": "Sarah",     "gender": "female", "accent": "us", "age": "middle", "tone": "soft"},
    {"voiceId": "XrExE9yKIg1WjnnlVkGX", "name": "Matilda",   "gender": "female", "accent": "us", "age": "middle", "tone": "warm"},
    {"voiceId": "Xb7hH8MSUJpSbSDYk0k2", "name": "Alice",     "gender": "female", "accent": "gb", "age": "middle", "tone": "confident"},
    {"voiceId": "pFZP5JQG7iQjIQuC4Bku", "name": "Lily",      "gender": "female", "accent": "gb", "age": "middle", "tone": "warm"},
    {"voiceId": "oWAxZDx7w5VEj9dCyTzz", "name": "Grace",     "gender": "female", "accent": "us", "age": "old",    "tone": "gentle"},
    # --- male ---
    {"voiceId": "ErXwobaYiN019PkySvjV", "name": "Antoni",    "gender": "male",   "accent": "us", "age": "young",  "tone": "warm"},
    {"voiceId": "CYw3kZ02Hs0563khs1Fj", "name": "Dave",      "gender": "male",   "accent": "gb", "age": "young",  "tone": "casual"},
    {"voiceId": "zcAOhNBS3c14rBihAFp1", "name": "Giovanni",  "gender": "male",   "accent": "it", "age": "young",  "tone": "expressive"},
    {"voiceId": "pNInz6obpgDQGcFmaJgB", "name": "Adam",      "gender": "male",   "accent": "us", "age": "middle", "tone": "deep"},
    {"voiceId": "VR6AewLTigWG4xSOukaG", "name": "Arnold",    "gender": "male",   "accent": "us", "age": "middle", "tone": "crisp"},
    {"voiceId": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel",    "gender": "male",   "accent": "gb", "age": "middle", "tone": "authoritative"},
    {"voiceId": "IKne3meq5aSn9XLyUdCD", "name": "Charlie",   "gender": "male",   "accent": "au", "age": "middle", "tone": "casual"},
    {"voiceId": "N2lVS1w4EtoT3dr4eOWO", "name": "Callum",    "gender": "male",   "accent": "us", "age": "middle", "tone": "intense"},
    {"voiceId": "JBFqnCBsd6RMkjVDRZzb", "name": "George",    "gender": "male",   "accent": "gb", "age": "old",    "tone": "warm"},
    {"voiceId": "D38z5RcWu1voky8WS1ja", "name": "Fin",       "gender": "male",   "accent": "ie", "age": "old",    "tone": "weathered"},
    {"voiceId": "pqHfZKP75CvOlQylNhV4", "name": "Bill",      "gender": "male",   "accent": "us", "age": "old",    "tone": "trustworthy"},
]

# Region token -> ordered preference of palette accents (best-fit first). For regions the
# premade voices can't accent (Middle Eastern, Asian, African, Latin American) this is just
# the least-wrong neutral fallback; gender and age still match.
REGION_ACCENT = {
    "north_american":  ["us", "gb"],
    "british":         ["gb", "ie", "us"],
    "irish":           ["ie", "gb", "us"],
    "australian":      ["au", "gb", "us"],
    "french":          ["it", "gb", "us"],
    "italian":         ["it", "gb", "us"],
    "iberian":         ["it", "gb", "us"],
    "greek":           ["it", "gb", "us"],
    "mediterranean":   ["it", "gb", "us"],
    "german":          ["gb", "se", "us"],
    "dutch":           ["gb", "se", "us"],
    "nordic":          ["se", "gb", "us"],
    "slavic":          ["se", "gb", "us"],
    "middle_eastern":  ["gb", "us"],
    "north_african":   ["gb", "us"],
    "african":         ["us", "gb"],
    "east_asian":      ["us", "gb"],
    "south_asian":     ["gb", "us"],
    "southeast_asian": ["us", "gb"],
    "latin_american":  ["it", "us", "gb"],
    "neutral":         ["us", "gb"],
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
        return "italian"  # generic continental-European stand-in within the premade palette
    return "neutral"


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
        f"- If the maker is a documented individual, use their actual gender, the regional "
        f"accent of their origin, and their approximate age while active (young/middle/old).\n"
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


_AGE_ORDER = {"young": 0, "middle": 1, "old": 2}


def _age_score(voice_age: str, want_age: str) -> int:
    if want_age not in _AGE_ORDER:
        return 0
    gap = abs(_AGE_ORDER[voice_age] - _AGE_ORDER[want_age])
    return {0: 3, 1: 1}.get(gap, 0)


def _stable_hash(s: str) -> int:
    """Small deterministic hash (Python's built-in hash() is salted per process)."""
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def select_voice(profile: dict, seed: str = "") -> str:
    """Score the palette against a profile and return the best-fit ElevenLabs voiceId.
    When several voices fit equally well, `seed` (the maker's identity) breaks the tie
    deterministically, so different makers spread across the palette while the same maker
    always lands on the same voice."""
    gender = profile.get("gender")
    age = profile.get("age")
    prefs = REGION_ACCENT.get(profile.get("region") or "neutral", REGION_ACCENT["neutral"])

    scored: list[tuple[int, dict]] = []
    for v in PALETTE:
        # Gender is a hard filter when known (a male artist should not get a female voice).
        if gender in ("male", "female") and v["gender"] != gender:
            continue
        score = 0
        if v["accent"] in prefs:
            score += (len(prefs) - prefs.index(v["accent"])) * 2  # earlier pref = higher
        score += _age_score(v["age"], age)
        scored.append((score, v))

    if not scored:
        return PALETTE[0]["voiceId"]
    top = max(s for s, _ in scored)
    best = [v for s, v in scored if s == top]
    return best[_stable_hash(seed) % len(best)]["voiceId"]


def voice_for_stop(stop: dict) -> str:
    """Resolve the ElevenLabs voiceId for a stop. Falls back to the configured default
    voice if anything goes wrong, so audio always has a usable voice."""
    try:
        seed = f"{stop.get('artist') or ''}|{stop.get('department') or ''}"
        return select_voice(infer_profile(stop), seed=seed)
    except Exception as e:
        print(f"[voices] voice_for_stop failed ({e}); using default voice")
        return ELEVENLABS_VOICE_ID
