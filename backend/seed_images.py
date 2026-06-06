"""Bake image URLs into data/pool.json and drop works that have no image.

Why: hydrating images from the MET API at request time gets the serverless function's
shared IP rate-limited (tours come back with blank plates). Baking the URLs once means
the app makes ZERO MET API calls at request time — images are instant and reliable, and
imageless on-view works never reach a tour.

Idempotent + resumable: works that already carry an `image` are skipped, and progress is
saved periodically, so you can re-run to fill in anything that failed (e.g. transient
rate-limiting). Run:  python seed_images.py
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from config import DATA_DIR, MET_API_BASE

POOL = DATA_DIR / "pool.json"
WORKERS = 16
SAVE_EVERY = 1000

_session = requests.Session()
_session.headers.update({"User-Agent": "met-audio-guide/1.0"})
_adapter = requests.adapters.HTTPAdapter(pool_connections=WORKERS, pool_maxsize=WORKERS)
_session.mount("https://", _adapter)


def fetch_image(obj: dict) -> dict:
    """Fill obj['image']/['imageLarge'] from the MET API (with backoff). Leaves them
    empty on a hard failure so a later re-run can retry."""
    if obj.get("image"):
        return obj
    oid = obj["objectID"]
    for attempt in range(4):
        try:
            r = _session.get(f"{MET_API_BASE}/objects/{oid}", timeout=30)
            if r.status_code == 404:
                return obj
            if r.status_code in (403, 429, 500, 502, 503):
                time.sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
            small = data.get("primaryImageSmall") or data.get("primaryImage") or ""
            obj["image"] = small
            obj["imageLarge"] = data.get("primaryImage") or small
            return obj
        except requests.RequestException:
            time.sleep(1.0 * (attempt + 1))
    return obj


def main() -> None:
    pool = json.loads(POOL.read_text())
    todo = [o for o in pool if not o.get("image")]
    print(f"pool={len(pool)} | need images for {len(todo)}")

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for _ in ex.map(fetch_image, todo):
            done += 1
            if done % SAVE_EVERY == 0:
                POOL.write_text(json.dumps(pool, separators=(",", ":")))
                have = sum(1 for o in pool if o.get("image"))
                print(f"  {done}/{len(todo)} processed · {have} have images")

    imaged = [o for o in pool if o.get("image")]
    POOL.write_text(json.dumps(imaged, separators=(",", ":")))
    print(f"\nDone. Kept {len(imaged)} works with images (dropped {len(pool) - len(imaged)} imageless).")


if __name__ == "__main__":
    main()
