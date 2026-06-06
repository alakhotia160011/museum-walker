"""Path-building engine: turn (time budget + preferences) into an ordered tour.

Algorithm:
  1. per_stop = listen_minutes(level) + walk buffer  ->  N = floor(minutes / per_stop)
  2. score each pool object by theme overlap (+ highlight/image bonuses)
  3. force-include top highlights if 'must-see' is on
  4. take top-N, then order by department + gallery number (proximity proxy)
"""
from __future__ import annotations

import json

from config import DATA_DIR, LISTEN_MINUTES, WALK_BUFFER_MINUTES, WORDS_PER_MINUTE
from themes import score_themes

_POOL: list[dict] | None = None


def load_pool() -> list[dict]:
    global _POOL
    if _POOL is None:
        path = DATA_DIR / "pool.json"
        _POOL = json.loads(path.read_text()) if path.exists() else []
    return _POOL


def _gallery_key(obj: dict):
    """Sort key for proximity: group by department, then numeric gallery if possible."""
    gallery = str(obj.get("gallery") or "")
    digits = "".join(c for c in gallery if c.isdigit())
    gnum = int(digits) if digits else 9999
    return (obj.get("departmentId") or 0, gnum, gallery)


def target_words(level: str) -> int:
    return int(LISTEN_MINUTES.get(level, 2.0) * WORDS_PER_MINUTE)


def num_stops(minutes: int, level: str) -> int:
    per_stop = LISTEN_MINUTES.get(level, 2.0) + WALK_BUFFER_MINUTES
    return max(1, int(minutes // per_stop))


def build_itinerary(minutes: int, themes: list[str], level: str, must_see: bool) -> list[dict]:
    pool = load_pool()
    if not pool:
        return []

    n = min(num_stops(minutes, level), len(pool))

    def score(obj: dict) -> float:
        s = float(score_themes(obj, themes)) * 3.0
        if obj.get("isHighlight"):
            s += 2.0
        if obj.get("imageLarge"):
            s += 0.5
        return s

    ranked = sorted(pool, key=score, reverse=True)

    chosen: list[dict] = []
    chosen_ids: set[int] = set()

    # Must-see highlights first (kept inside the budget).
    if must_see:
        for obj in sorted(pool, key=lambda o: not o.get("isHighlight")):
            if not obj.get("isHighlight"):
                break
            if len(chosen) >= n:
                break
            if obj["objectID"] not in chosen_ids:
                chosen.append(obj)
                chosen_ids.add(obj["objectID"])

    # Fill remaining slots by theme/highlight score.
    for obj in ranked:
        if len(chosen) >= n:
            break
        if obj["objectID"] not in chosen_ids:
            chosen.append(obj)
            chosen_ids.add(obj["objectID"])

    # Order the selected stops by proximity (department, then gallery).
    chosen.sort(key=_gallery_key)

    words = target_words(level)
    est_seconds_per_stop = int(words / WORDS_PER_MINUTE * 60)
    stops = []
    for i, obj in enumerate(chosen):
        stops.append(
            {
                "stopId": f"{obj['objectID']}",
                "index": i,
                "objectID": obj["objectID"],
                "title": obj["title"],
                "artist": obj["artist"],
                "date": obj["date"],
                "medium": obj["medium"],
                "department": obj["department"],
                "gallery": obj["gallery"],
                "image": obj["image"],
                "imageLarge": obj["imageLarge"],
                "metUrl": obj.get("metUrl", ""),
                "isHighlight": obj.get("isHighlight", False),
                "tags": obj.get("tags", []),
                "themeMatch": score_themes(obj, themes),
                "targetWords": words,
                "estSeconds": est_seconds_per_stop,
            }
        )
    return stops
