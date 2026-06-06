"""Build the local pool of the Met's *on-view* collection so the live guide is fast,
offline-safe, and rate-limit-proof.

The Met populates an object's "Gallery Number" only while it's physically on display,
so that field in the Open Access dataset is the authoritative "on view" signal (the
Search API's isOnView filter badly undercounts). We therefore:

  1. Download the Open Access CSV once (~300MB Git-LFS file, cached locally).
  2. Keep every row that has a Gallery Number  ->  the full on-view collection.
  3. Write a slim data/pool.json (metadata only). Image URLs are hydrated lazily for
     the handful of works a tour actually chooses (see app.py), so we never fetch
     ~50k images.

Run once (re-run to refresh):  python seed_pool.py
"""
from __future__ import annotations

import csv
import json
import sys

import requests

from config import DATA_DIR, DEPARTMENTS, OPENACCESS_CSV_URL, SEED_PER_DEPARTMENT

csv.field_size_limit(10_000_000)

_CSV_CACHE = DATA_DIR.parent / "cache" / "MetObjects.csv"


def _norm(name: str) -> str:
    return name.strip().lower().removeprefix("the ").strip()


# CSV stores department *names*; we want our canonical ids for routing/clustering.
_NAME_TO_ID = {_norm(name): dept_id for dept_id, name in DEPARTMENTS.items()}


def ensure_csv() -> bool:
    """Download the Open Access CSV to the cache if absent. Returns False on failure."""
    if _CSV_CACHE.exists() and _CSV_CACHE.stat().st_size > 1_000_000:
        print(f"Using cached CSV: {_CSV_CACHE} ({_CSV_CACHE.stat().st_size // 1_000_000} MB)")
        return True
    _CSV_CACHE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Met Open Access CSV (~300MB) -> {_CSV_CACHE} ...")
    try:
        with requests.get(OPENACCESS_CSV_URL, stream=True, timeout=600) as r:
            r.raise_for_status()
            done = 0
            with open(_CSV_CACHE, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    if done % (40 << 20) < (1 << 20):
                        print(f"  ...{done // 1_000_000} MB")
        print("  download complete")
        return True
    except requests.RequestException as e:
        print(f"  ! CSV download failed: {e}")
        if _CSV_CACHE.exists():
            _CSV_CACHE.unlink()
        return False


def _slim(row: dict) -> dict:
    dept_name = (row.get("Department") or "").strip()
    tags = [t.strip() for t in (row.get("Tags") or "").split("|") if t.strip()]
    return {
        "objectID": int(row["Object ID"]),
        "title": (row.get("Title") or "").strip() or "Untitled",
        "artist": (row.get("Artist Display Name") or row.get("Culture") or "").strip() or "Unknown",
        "date": (row.get("Object Date") or "").strip(),
        "medium": (row.get("Medium") or "").strip(),
        "department": dept_name,
        "departmentId": _NAME_TO_ID.get(_norm(dept_name), 0),
        "gallery": (row.get("Gallery Number") or "").strip(),
        "isHighlight": (row.get("Is Highlight") or "").strip().lower() == "true",
        "isPublicDomain": (row.get("Is Public Domain") or "").strip().lower() == "true",
        "metUrl": (row.get("Link Resource") or "").strip(),
        "tags": tags[:12],
        "classification": (row.get("Classification") or "").strip(),
    }


def main() -> None:
    if not ensure_csv():
        print("CSV unavailable; cannot seed. Aborting.")
        sys.exit(1)

    print("Scanning for on-view works (rows with a gallery number)...")
    pool: list[dict] = []
    per_dept: dict[int, int] = {}
    with open(_CSV_CACHE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not (row.get("Gallery Number") or "").strip():
                continue
            try:
                obj = _slim(row)
            except (KeyError, ValueError):
                continue
            if SEED_PER_DEPARTMENT:
                d = obj["departmentId"]
                if per_dept.get(d, 0) >= SEED_PER_DEPARTMENT:
                    continue
                per_dept[d] = per_dept.get(d, 0) + 1
            pool.append(obj)

    out = DATA_DIR / "pool.json"
    out.write_text(json.dumps(pool, separators=(",", ":")))
    by_dept: dict[str, int] = {}
    for o in pool:
        by_dept[o["department"]] = by_dept.get(o["department"], 0) + 1
    print(f"\nWrote {len(pool)} on-view objects to {out} ({out.stat().st_size // 1000} KB)")
    for dept, c in sorted(by_dept.items(), key=lambda kv: -kv[1]):
        print(f"  {c:6d}  {dept}")


if __name__ == "__main__":
    main()
