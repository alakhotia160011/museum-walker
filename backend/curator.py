"""Path-building engine: turn (time budget + preferences) into an ordered, *walkable* tour.

Algorithm:
  1. per_stop = listen_minutes(level) + walk buffer  ->  N = floor(minutes / per_stop)
  2. score every on-view object by theme overlap + era (period) match (+ highlight bonus)
  3. pick the best few departments (wings) for those themes/eras, capped by time, so the
     route stays geographically tight instead of crisscrossing the whole museum
  4. inside those wings: force-include must-see highlights, then fill by score
  5. order by department + gallery number (proximity proxy), and attach a spoken
     transition telling the visitor how to walk to the next stop

Image URLs are NOT stored in the pool; they're hydrated lazily for the chosen stops
(see app.py) so we never fetch tens of thousands of images.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict

from config import (
    DATA_DIR,
    LISTEN_MINUTES,
    WALK_BUFFER_MINUTES,
    WORDS_PER_MINUTE,
    department_budget,
)
from themes import score_themes
from eras import classify_era, score_eras
import countries
import geo

_POOL: list[dict] | None = None


def load_pool() -> list[dict]:
    global _POOL
    if _POOL is None:
        path = DATA_DIR / "pool.json"
        _POOL = json.loads(path.read_text()) if path.exists() else []
    return _POOL


# CJK / Kana / Hangul / fullwidth blocks — the Met keeps some Asian titles in the original
# script (sometimes as "<original>|<English>", sometimes with the script inline) and a few
# works are flatly "Untitled". We show a readable English title so the visitor never hears
# or reads raw characters their device may not even render.
_CJK = re.compile(
    r"[　-〿぀-ヿㇰ-ㇿ㐀-䶿一-鿿"
    r"豈-﫿가-힯＀-￯]"
)
_HAS_LATIN = re.compile(r"[A-Za-z]")


def _display_title(obj: dict) -> str:
    """A clean, speakable English title: prefer the English side of an '<original>|English'
    pair, strip any inline original-script characters, and fall back to the work's
    classification (then medium) when nothing readable remains or it's 'Untitled'."""
    t = (obj.get("title") or "").strip()
    if "|" in t:  # "<original script>|<English>" — keep the English (last Latin segment)
        latin = [p.strip() for p in t.split("|") if _HAS_LATIN.search(p)]
        if latin:
            t = latin[-1]
    if _CJK.search(t):  # strip inline original-script characters and tidy the leftovers
        t = _CJK.sub("", t)
        t = re.sub(r"\(\s*\)", "", t)        # emptied parentheses
        t = re.sub(r"\s{2,}", " ", t)
        t = t.strip(" -–—|·,")
    if not _HAS_LATIN.search(t) or t.lower().startswith("untitled"):
        cls = (obj.get("classification") or "").strip()
        medium = (obj.get("medium") or "").strip()
        base = cls or (medium.split(",")[0].strip() if medium else "") or "Work"
        place = _origin_place(obj)
        t = f"{base} from {place}" if place else base
    return t


def _origin_place(obj: dict) -> str:
    """A short place name (the first segment of culture/country/nationality), for naming
    works the Met left 'Untitled' — e.g. 'India, Tamil Nadu' -> 'India'."""
    for field in ("culture", "country", "artistNationality"):
        v = (obj.get(field) or "").strip()
        if v:
            v = re.split(r"[,(|]", v)[0].strip()
            if v:
                return v
    return ""


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


def _score(obj: dict, themes: list[str], eras: list[str], regions: list[str]) -> float:
    s = float(score_themes(obj, themes)) * 3.0
    s += float(score_eras(obj, eras)) * 3.0
    s += float(countries.score_regions(obj, regions)) * 3.0
    if obj.get("isHighlight"):
        s += 2.0
    return s


def _pick_departments(
    pool: list[dict], themes: list[str], eras: list[str], regions: list[str], max_depts: int
) -> set[int]:
    """Rank wings by how well they fit the chosen themes/eras/regions (falling back to
    highlight density when nothing is selected) and keep the top `max_depts`. Operates on
    the *already era/region-filtered* pool, so it picks the wings densest in matches."""
    weight: dict[int, float] = defaultdict(float)
    for obj in pool:
        d = obj.get("departmentId")
        if d is None:
            continue
        if themes or eras or regions:
            weight[d] += (
                float(score_themes(obj, themes))
                + float(score_eras(obj, eras))
                + float(countries.score_regions(obj, regions))
            )
        elif obj.get("isHighlight"):
            weight[d] += 1.0
    ranked = [d for d, w in sorted(weight.items(), key=lambda kv: -kv[1]) if w > 0]
    if not ranked:  # no signal at all -> keep the biggest wings so a tour still exists
        counts: dict[int, int] = defaultdict(int)
        for obj in pool:
            counts[obj.get("departmentId")] += 1
        ranked = [d for d, _ in sorted(counts.items(), key=lambda kv: -kv[1])]
    return set(ranked[:max_depts])


_FLOOR_NAME = {
    "Floor G": "the ground floor",
    "Floor 1": "the first floor",
    "Floor 1M": "the mezzanine",
    "Floor 2": "the second floor",
    "Floor 3": "the third floor",
    "Floor 4": "the fourth floor",
    "Floor 5": "the fifth floor",
}


def transition_line(current: dict, nxt: dict | None) -> str:
    """A short, accurate spoken cue for walking from `current` to the next stop.
    Uses real floor data (attached by geo.order_route) when available; otherwise
    falls back to gallery-/wing-based wording. Never invents left/right directions."""
    if nxt is None:
        return "That's the last stop on your path. Take your time, and enjoy the rest of the Met."
    title = nxt["title"]
    g_now = str(current.get("gallery") or "")
    g_next = str(nxt.get("gallery") or "")
    here = f"Gallery {g_next}" if g_next else "the next room"

    # Different building (rare; never say "stairs" across a 9.5km gap).
    if current.get("building") and nxt.get("building") and current["building"] != nxt["building"]:
        return f"Our next stop is over at {nxt['building']} - {here}, for {title}."

    # Same gallery.
    if g_next and g_now and g_next == g_now:
        return f"Our next piece is right here in this gallery. Turn and look for {title}."

    # Floor-aware, when both stops have a known floor.
    fc, fn = current.get("floorId"), nxt.get("floorId")
    if fc is not None and fn is not None and fc != fn:
        direction = "up" if fn > fc else "down"
        floor_name = _FLOOR_NAME.get(nxt.get("floor") or "", nxt.get("floor") or "the next floor")
        return f"Take the stairs {direction} to {floor_name} and find {here}, where {title} is waiting."

    # Same floor (or floors unknown but same department) - short walk.
    if (fc is not None and fc == fn) or current.get("departmentId") == nxt.get("departmentId"):
        return f"When you're ready, continue on this floor to {here}, where {title} is waiting."

    # Fallback: cross-department without floor data.
    where = nxt["department"] + (f", Gallery {g_next}" if g_next else "")
    return f"Now we'll move on. Make your way to {where} for our next stop, {title}."


# A small over-select so app.py can drop the rare imageless work and still fill the
# tour. The pool is public-domain-only (~100% imaged), so this can stay small — fewer
# MET image fetches per tour also means less chance of hitting its rate limit.
_IMAGE_BUFFER = 6


def _build_stop(
    obj: dict, themes: list[str], eras: list[str], words: int, est_seconds: int
) -> dict:
    return {
        "stopId": f"{obj['objectID']}",
        "objectID": obj["objectID"],
        "title": _display_title(obj),
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
        "eraMatch": score_eras(obj, eras),
        "era": classify_era(obj.get("date")),
        "targetWords": words,
        "estSeconds": est_seconds,
        # script is generated on demand (/api/narrate);
        # lat/lng/floor/floorId/building are attached by geo.order_route.
        "script": "",
        # Use the baked image URL when the pool has one (no MET call needed);
        # app.py live-hydrates only stops still missing it.
        "image": obj.get("image", "") or "",
        "imageLarge": obj.get("imageLarge", "") or "",
    }


def _filter_pool(pool: list[dict], eras: list[str], regions: list[str]) -> list[dict]:
    """Apply era + region as HARD filters: every kept work is from a selected period AND
    a selected region. This is what makes the onboarding chips actually constrain the tour
    (a 'Modern' tour contains only post-1900 works; an 'Egypt' tour only Egyptian ones)."""
    out = pool
    if eras:
        out = [o for o in out if classify_era(o.get("date")) in eras]
    if regions:
        out = [o for o in out if countries.match(o, regions)]
    return out


def select_candidates(
    minutes: int,
    themes: list[str],
    level: str,
    must_see: bool,
    eras: list[str] | None = None,
    regions: list[str] | None = None,
):
    """Pick the works for a tour. Returns (n, candidates) where `candidates` is a ranked
    list of up to n + buffer stop dicts (unordered, no narration) so the caller can drop
    imageless works and still assemble n imaged stops.

    Era + region are HARD filters: we never pad a tour with works that don't match them —
    a too-strict combination yields a shorter, honest tour instead. We only relax a filter
    (region first, then era) if it would otherwise leave *nothing* to show."""
    eras = eras or []
    regions = regions or []
    pool = load_pool()
    if not pool:
        return 0, []

    n = min(num_stops(minutes, level), len(pool))

    # Hard filter, with graceful relaxation only when a combination empties the pool.
    base = _filter_pool(pool, eras, regions)
    if not base and regions:
        base = _filter_pool(pool, eras, [])     # drop region constraint
    if not base and eras:
        base = _filter_pool(pool, [], regions)  # drop era constraint
    if not base:
        base = pool

    allowed = _pick_departments(base, themes, eras, regions, department_budget(minutes))
    candidates = [o for o in base if o.get("departmentId") in allowed] or base
    cap = min(len(candidates), n + _IMAGE_BUFFER)

    score = lambda o: _score(o, themes, eras, regions)  # noqa: E731
    ranked = sorted(candidates, key=score, reverse=True)
    chosen: list[dict] = []
    chosen_ids: set[int] = set()

    if must_see:
        for obj in sorted(candidates, key=lambda o: (not o.get("isHighlight"), -score(o))):
            if len(chosen) >= cap or not obj.get("isHighlight"):
                break
            if obj["objectID"] not in chosen_ids:
                chosen.append(obj)
                chosen_ids.add(obj["objectID"])

    for obj in ranked:
        if len(chosen) >= cap:
            break
        if obj["objectID"] not in chosen_ids:
            chosen.append(obj)
            chosen_ids.add(obj["objectID"])

    words = target_words(level)
    est = int(words / WORDS_PER_MINUTE * 60)
    return n, [_build_stop(o, themes, eras, words, est) for o in chosen]


def finalize(stops: list[dict]) -> list[dict]:
    """Order the chosen stops into a walkable route, number them, and attach walking cues."""
    stops = geo.order_route(stops, _gallery_key)
    for i, s in enumerate(stops):
        s["index"] = i
    for i, s in enumerate(stops):
        s["transition"] = transition_line(s, stops[i + 1] if i + 1 < len(stops) else None)
    return stops


def build_itinerary(
    minutes: int,
    themes: list[str],
    level: str,
    must_see: bool,
    eras: list[str] | None = None,
    regions: list[str] | None = None,
) -> list[dict]:
    """Convenience for offline use/tests: select n works and finalize the route
    (no image filtering, no narration). The API hydrates images and narration separately."""
    n, candidates = select_candidates(minutes, themes, level, must_see, eras, regions)
    stops = finalize(candidates[:n])
    return stops
