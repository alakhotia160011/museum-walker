"""Human-friendly interest themes mapped to MET AAT tag keywords.

Drives both the onboarding chips and candidate scoring in the curator.
Matching is case-insensitive substring against an object's tag terms."""
from __future__ import annotations

# label -> {keywords: [...], blurb: str}
THEMES = {
    "Portraits": {
        "keywords": ["portrait", "men", "women", "self-portrait", "face", "child", "family"],
        "blurb": "Faces and the people behind them",
    },
    "Religion & Myth": {
        "keywords": [
            "christ", "madonna", "saint", "angel", "virgin", "crucifixion", "god",
            "goddess", "myth", "deity", "biblical", "sacred", "annunciation",
        ],
        "blurb": "Gods, saints, and sacred stories",
    },
    "Power & War": {
        "keywords": [
            "armor", "sword", "helmet", "weapon", "shield", "battle", "soldier",
            "king", "emperor", "horse", "warrior", "gun", "dagger",
        ],
        "blurb": "Armor, rulers, and the art of conflict",
    },
    "Death & the Afterlife": {
        "keywords": [
            "mummy", "coffin", "sarcophagus", "tomb", "funerary", "death", "burial",
            "afterlife", "skull", "amulet",
        ],
        "blurb": "Tombs, mummies, and eternity",
    },
    "Daily Life": {
        "keywords": [
            "interior", "still life", "food", "market", "work", "music", "dance",
            "household", "vessel", "jewelry", "game", "domestic",
        ],
        "blurb": "How people lived, worked, and played",
    },
    "Nature & Landscape": {
        "keywords": [
            "landscape", "flower", "tree", "animal", "bird", "river", "mountain",
            "garden", "sky", "sea", "fruit", "horse",
        ],
        "blurb": "Land, creatures, and the natural world",
    },
    "Color & Technique": {
        "keywords": [
            "oil", "fresco", "gold", "drawing", "watercolor", "engraving",
            "painting", "marble", "bronze", "tempera",
        ],
        "blurb": "Materials, craft, and how it was made",
    },
}


def theme_list() -> list[dict]:
    """Shape for the frontend onboarding chips."""
    return [{"id": name, "label": name, "blurb": meta["blurb"]} for name, meta in THEMES.items()]


def object_tag_terms(obj: dict) -> list[str]:
    """Lowercased tag terms for an object, with title/medium folded in as a fallback
    (some objects have sparse tags)."""
    terms: list[str] = []
    for t in obj.get("tags") or []:
        # Pool tags are plain strings; raw MET objects use {"term": ...} dicts.
        term = (t.get("term") if isinstance(t, dict) else t) or ""
        term = term.lower()
        if term:
            terms.append(term)
    for field in ("title", "medium", "classification", "objectName"):
        val = (obj.get(field) or "").lower()
        if val:
            terms.append(val)
    return terms


def score_themes(obj: dict, selected: list[str]) -> int:
    """Count how many selected-theme keywords appear in the object's tag terms."""
    if not selected:
        return 0
    terms = " ".join(object_tag_terms(obj))
    score = 0
    for theme in selected:
        for kw in THEMES.get(theme, {}).get("keywords", []):
            if kw in terms:
                score += 1
    return score
