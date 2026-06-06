"""Bake a gallery-number -> {lat, lng, floor, floorId} lookup from the Met's public
Living Map vector tiles, so the guide can place every stop on the real floor plan and
route between galleries without a live dependency at request time.

The Met's map (maps.metmuseum.org) is a Living Map deployment whose tiles are served,
unauthenticated, at prod.cdn.livingmap.com/tiles/the_met/{z}/{x}/{y}.pbf. Each gallery
room is an `indoor` feature of type "gallery" whose `name` is its gallery number - the
same value as the collection's "Gallery Number". We extract those, project the geometry
to lat/lng, and write data/gallery_coords.json.

Run once (re-run to refresh):  python seed_map.py
"""
from __future__ import annotations

import json
import math

import requests

import mapbox_vector_tile as mvt

from config import DATA_DIR

TILE_URL = "https://prod.cdn.livingmap.com/tiles/the_met/{z}/{x}/{y}.pbf?lang=en-GB"
# The Met's two mapped locations: Fifth Avenue (main) and The Cloisters.
LOCATIONS = [
    ("The Met Fifth Avenue", 40.779448, -73.963517),
    ("The Met Cloisters", 40.864821, -73.931639),
]
ZOOM = 16
GRID = 2  # +/- this many tiles around each location's center


def _deg2tile(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y


def _tilepoint_to_lonlat(tx, ty, z, x, y, extent) -> tuple[float, float]:
    """Tile-local point (origin top-left, y down) -> (lon, lat)."""
    n = 2 ** z
    lon = (x + tx / extent) / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * (y + ty / extent) / n))))
    return lon, lat


def _ring_centroid(ring: list) -> tuple[float, float]:
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def main() -> None:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://maps.metmuseum.org",
            "Referer": "https://maps.metmuseum.org/",
        }
    )

    # gallery number -> {points:[(lon,lat)...], floor, floorId, location}
    acc: dict[str, dict] = {}

    for loc_name, lat, lon in LOCATIONS:
        cx, cy = _deg2tile(lat, lon, ZOOM)
        for dx in range(-GRID, GRID + 1):
            for dy in range(-GRID, GRID + 1):
                x, y = cx + dx, cy + dy
                url = TILE_URL.format(z=ZOOM, x=x, y=y)
                r = session.get(url, timeout=30)
                if r.status_code != 200 or not r.content:
                    continue
                tile = mvt.decode(r.content, y_coord_down=True)
                layer = tile.get("indoor")
                if not layer:
                    continue
                extent = layer.get("extent", 4096)
                for f in layer["features"]:
                    p = f["properties"]
                    if p.get("type") != "gallery":
                        continue
                    name = str(p.get("name", "")).strip()
                    if not name.isdigit():
                        continue
                    geom = f["geometry"]
                    gtype = geom["type"]
                    pts: list[tuple[float, float]] = []
                    is_point = False
                    if gtype == "Point":
                        pts = [tuple(geom["coordinates"])]
                        is_point = True
                    elif gtype == "Polygon":
                        pts = [_ring_centroid(geom["coordinates"][0])]
                    elif gtype == "MultiPolygon":
                        pts = [_ring_centroid(geom["coordinates"][0][0])]
                    else:
                        continue
                    lonlats = [_tilepoint_to_lonlat(px, py, ZOOM, x, y, extent) for px, py in pts]
                    entry = acc.setdefault(
                        name,
                        {"poly": [], "point": [], "floor": None, "floorId": None, "location": None},
                    )
                    entry["point" if is_point else "poly"].extend(lonlats)
                    entry["floor"] = p.get("floor_name") or entry["floor"]
                    entry["floorId"] = p.get("floor_id") or entry["floorId"]
                    entry["location"] = p.get("location_name") or loc_name

    coords: dict[str, dict] = {}
    for name, e in acc.items():
        # Prefer the dedicated label point; fall back to polygon centroids.
        chosen = e["point"] or e["poly"]
        if not chosen:
            continue
        lon = sum(c[0] for c in chosen) / len(chosen)
        lat = sum(c[1] for c in chosen) / len(chosen)
        coords[name] = {
            "lat": round(lat, 7),
            "lng": round(lon, 7),
            "floor": e["floor"],
            "floorId": e["floorId"],
            "location": e["location"],
        }

    out = DATA_DIR / "gallery_coords.json"
    out.write_text(json.dumps(coords, separators=(",", ":"), sort_keys=True))
    by_floor: dict[str, int] = {}
    for v in coords.values():
        by_floor[v["floor"]] = by_floor.get(v["floor"], 0) + 1
    print(f"Wrote {len(coords)} galleries with coordinates to {out}")
    for fl, c in sorted(by_floor.items(), key=lambda kv: str(kv[0])):
        print(f"  {c:4d}  {fl}")


if __name__ == "__main__":
    main()
