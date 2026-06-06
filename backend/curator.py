"""Path-building engine: turn (time budget + preferences) into an ordered, *walkable* tour.

Algorithm:
  1. per_stop = listen_minutes(level) + walk buffer  ->  N = floor(minutes / per_stop)
  2. score every on-view object by theme overlap (+ highlight/image bonuses)
  3. pick the best few departments (wings) for those themes, capped by time, so the
     route stays geographically tight instead of crisscrossing the whole museum
  4. inside those wings: force-include must-see highlights, then fill by score
  5. order by department + gallery number (proximity proxy), and attach a spoken
     transition telling the visitor how to walk to the next stop

Image URLs are NOT stored in the pool; they're hydrated lazily for the chosen stops
(see app.py) so we never fetch tens of thousands of images.
"""
from __future__ import annotations

import json
from collections import defaultdict

from config import (
    DATA_DIR,
    LISTEN_MINUTES,
    WALK_BUFFER_MINUTES,
    WORDS_PER_MINUTE,
    department_budget,
)
from themes import score_themes

_POOL: list[dict] | None = None


def load_pool() -> list[dict]:
    global _POOL
    if _POOL is None:
        path = DATA_DIR / "pool.json"
        _POOL = json.loads(path.read_text()) if path.exists() else []
    return _POOL


def _gallery_num(obj: dict) -> int:
    digits = "".join(c for c in str(obj.get("gallery") or "") if c.isdigit())
    return int(digits) if digits else 9999


def _gallery_key(obj: dict):
    """Sort key for proximity: group by department, then numeric gallery if possible."""
    return (obj.get("departmentId") or 0, _gallery_num(obj), str(obj.get("gallery") or ""))


def target_words(level: str) -> int:
    return int(LISTEN_MINUTES.get(level, 2.0) * WORDS_PER_MINUTE)


def num_stops(minutes: int, level: str) -> int:
    per_stop = LISTEN_MINUTES.get(level, 2.0) + WALK_BUFFER_MINUTES
    return max(1, int(minutes // per_stop))


def _score(obj: dict, themes: list[str]) -> float:
    s = float(score_themes(obj, themes)) * 3.0
    if obj.get("isHighlight"):
        s += 2.0
    return s


def _pick_departments(pool: list[dict], themes: list[str], max_depts: int) -> set[int]:
    """Rank wings by how well they fit the chosen themes (falling back to highlight
    density when no themes are selected) and keep the top `max_depts`."""
    weight: dict[int, float] = defaultdict(float)
    for obj in pool:
        d = obj.get("departmentId")
        if d is None:
            continue
        if themes:
            weight[d] += float(score_themes(obj, themes))
        elif obj.get("isHighlight"):
            weight[d] += 1.0
    ranked = [d for d, w in sorted(weight.items(), key=lambda kv: -kv[1]) if w > 0]
    if not ranked:  # no signal at all -> keep the biggest wings so a tour still exists
        counts: dict[int, int] = defaultdict(int)
        for obj in pool:
            counts[obj.get("departmentId")] += 1
        ranked = [d for d, _ in sorted(counts.items(), key=lambda kv: -kv[1])]
    return set(ranked[:max_depts])


def transition_line(current: dict, nxt: dict | None) -> str:
    """A short, accurate spoken cue for walking from `current` to the next stop.
    Directions are gallery-/wing-based (the only location data the Met publishes)."""
    if nxt is None:
        return "That's the last stop on your path. Take your time, and enjoy the rest of the Met."
    title = nxt["title"]
    g_now = str(current.get("gallery") or "")
    g_next = str(nxt.get("gallery") or "")
    same_dept = current.get("departmentId") == nxt.get("departmentId")
    if g_next and g_now and g_next == g_now:
        return f"Our next piece is right here in this gallery. Turn and look for {title}."
    if same_dept:
        where = f"Gallery {g_next}" if g_next else f"the next room in {nxt['department']}"
        return f"When you're ready, head to {where}, where {title} is waiting."
    where = f"{nxt['department']}"
    if g_next:
        where += f", Gallery {g_next}"
    return f"Now we'll leave this wing. Make your way to {where} for our next stop, {title}."


def build_itinerary(minutes: int, themes: list[str], level: str, must_see: bool) -> list[dict]:
    pool = load_pool()
    if not pool:
        return []

    n = min(num_stops(minutes, level), len(pool))
    allowed = _pick_departments(pool, themes, department_budget(minutes))
    candidates = [o for o in pool if o.get("departmentId") in allowed] or pool

    ranked = sorted(candidates, key=lambda o: _score(o, themes), reverse=True)

    chosen: list[dict] = []
    chosen_ids: set[int] = set()

    # Must-see highlights first (within the chosen wings, kept inside the budget).
    if must_see:
        for obj in sorted(candidates, key=lambda o: (not o.get("isHighlight"), -_score(o, themes))):
            if len(chosen) >= n or not obj.get("isHighlight"):
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
                "departmentId": obj.get("departmentId"),
                "gallery": obj["gallery"],
                "metUrl": obj.get("metUrl", ""),
                "isHighlight": obj.get("isHighlight", False),
                "tags": obj.get("tags", []),
                "themeMatch": score_themes(obj, themes),
                "targetWords": words,
                "estSeconds": est_seconds_per_stop,
                # image / imageLarge are filled in lazily by app.py
                "image": "",
                "imageLarge": "",
            }
        )

    # Attach a walking cue from each stop to the next.
    for i, s in enumerate(stops):
        s["transition"] = transition_line(s, stops[i + 1] if i + 1 < len(stops) else None)
    return stops
