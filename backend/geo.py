"""Coordinate-aware route ordering.

Turns a set of chosen stops into a *walkable* sequence using the real gallery
coordinates baked by seed_map.py (data/gallery_coords.json). The big wins over a
plain gallery-number sort:
  - never crisscross buildings (Fifth Avenue and The Cloisters are ~9.5km apart),
  - visit floors monotonically so you never bounce up and down stairs,
  - order stops within a floor by actual walking distance (nearest-neighbour + 2-opt).

Pure CPU, zero network. Falls back to the caller's sort key if coordinates are
missing, so the app still works without the coords file.
"""
from __future__ import annotations

import json
import math

from config import DATA_DIR

_COORDS: dict | None = None

# The Met Fifth Avenue main entrance / Great Hall - where a visit begins.
GREAT_HALL = {"lat": 40.7794, "lng": -73.9632}


def _load() -> dict:
    global _COORDS
    if _COORDS is None:
        path = DATA_DIR / "gallery_coords.json"
        _COORDS = json.loads(path.read_text()) if path.exists() else {}
    return _COORDS


def _norm(gallery) -> str | None:
    """Normalise a gallery value to a coords key: digits only, leading zeros stripped
    ("014" -> "14"). Returns None for non-numeric galleries ("in Great Hall")."""
    digits = "".join(c for c in str(gallery or "") if c.isdigit())
    if not digits:
        return None
    return str(int(digits))


def locate(gallery) -> dict | None:
    """Return {lat, lng, floor, floorId, location} for a gallery, or None."""
    key = _norm(gallery)
    return _load().get(key) if key else None


def distance(a: dict, b: dict) -> float:
    """Equirectangular distance in metres. Only valid within one building."""
    mean = math.radians((a["lat"] + b["lat"]) / 2)
    dx = (b["lng"] - a["lng"]) * math.cos(mean) * 111320
    dy = (b["lat"] - a["lat"]) * 110540
    return math.hypot(dx, dy)


def _open_tsp(pts: list[dict], seed: int) -> list[int]:
    """Order indices of `pts` as a short open path starting at `seed`, via
    nearest-neighbour then 2-opt. `pts` are coord dicts; N is small (<= ~15)."""
    n = len(pts)
    if n <= 1:
        return list(range(n))

    # Nearest-neighbour from the seed.
    unvisited = set(range(n))
    order = [seed]
    unvisited.discard(seed)
    while unvisited:
        last = order[-1]
        nxt = min(unvisited, key=lambda j: (distance(pts[last], pts[j]), j))
        order.append(nxt)
        unvisited.discard(nxt)

    # 2-opt improvement on the open path (don't move the fixed start).
    def seg_len(o: list[int]) -> float:
        return sum(distance(pts[o[i]], pts[o[i + 1]]) for i in range(len(o) - 1))

    best = seg_len(order)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for k in range(i + 1, n):
                cand = order[:i] + order[i:k + 1][::-1] + order[k + 1:]
                cand_len = seg_len(cand)
                if cand_len + 1e-9 < best:
                    order, best, improved = cand, cand_len, True
    return order


def order_route(stops: list[dict], fallback_key) -> list[dict]:
    """Return `stops` reordered into a walkable sequence. Mutates each stop to attach
    lat/lng/floor/floorId/building (None when no coordinate is known). Never drops a stop.

    `fallback_key` is curator._gallery_key - used to order coordinate-less stops and as a
    whole-route fallback when no coordinates are available at all.
    """
    if not stops:
        return stops

    # 1. Attach coordinates.
    placed: list[dict] = []
    unplaced: list[dict] = []
    for s in stops:
        c = locate(s.get("gallery"))
        if c:
            s["lat"], s["lng"] = c["lat"], c["lng"]
            s["floor"], s["floorId"] = c.get("floor"), c.get("floorId")
            s["building"] = c.get("location")
            placed.append(s)
        else:
            s["lat"] = s["lng"] = s["floor"] = s["floorId"] = s["building"] = None
            unplaced.append(s)

    # 2. Fallback: no usable coordinates -> today's behaviour.
    if not placed:
        return sorted(stops, key=fallback_key)

    # 3. Partition by building (Fifth Avenue first, then everything else); never interleave.
    buildings: dict[str, list[dict]] = {}
    for s in placed:
        buildings.setdefault(s["building"] or "", []).append(s)

    def building_rank(name: str) -> tuple:
        # Fifth Avenue is the bulk; visit it first, then others by size desc, then name.
        return (0 if name == "The Met Fifth Avenue" else 1, -len(buildings[name]), name)

    ordered: list[dict] = []
    for bname in sorted(buildings, key=building_rank):
        group = buildings[bname]
        # 4. Cluster by floor, visit floors ascending (monotonic = minimal transitions).
        floors: dict[int, list[dict]] = {}
        for s in group:
            floors.setdefault(s["floorId"] if s["floorId"] is not None else 9999, []).append(s)

        prev_last: dict | None = None
        for fid in sorted(floors):
            floor_stops = floors[fid]
            # 5. Seed the floor's open-path: first floor from the Great Hall, later
            #    floors from the stop nearest the previous floor's exit point.
            anchor = prev_last if prev_last is not None else GREAT_HALL
            seed = min(range(len(floor_stops)), key=lambda i: (distance(anchor, floor_stops[i]), i))
            seq = _open_tsp(floor_stops, seed)
            ordered.extend(floor_stops[i] for i in seq)
            prev_last = floor_stops[seq[-1]]

    # 6. Coordinate-less stops go last, in the fallback order (never dropped).
    ordered.extend(sorted(unplaced, key=fallback_key))
    return ordered
