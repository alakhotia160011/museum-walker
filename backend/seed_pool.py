"""Dev-time script: build a curated local pool of MET objects so the live demo is
fast, offline-safe, and rate-limit-proof.

Run once:  python seed_pool.py
Writes data/pool.json (~40-60 objects across the configured departments)."""
from __future__ import annotations

import json

import met_client
from config import DATA_DIR, DEPARTMENTS, SEED_PER_DEPARTMENT


def slim(obj: dict) -> dict | None:
    """Keep only what the app needs; drop objects without a usable image."""
    img = obj.get("primaryImageSmall") or obj.get("primaryImage")
    if not img:
        return None
    return {
        "objectID": obj.get("objectID"),
        "title": obj.get("title") or "Untitled",
        "artist": obj.get("artistDisplayName") or obj.get("culture") or "Unknown",
        "date": obj.get("objectDate") or "",
        "medium": obj.get("medium") or "",
        "department": obj.get("department") or "",
        "departmentId": obj.get("departmentId"),
        "gallery": obj.get("GalleryNumber") or "",
        "isHighlight": bool(obj.get("isHighlight")),
        "image": img,
        "imageLarge": obj.get("primaryImage") or img,
        "metUrl": obj.get("objectURL") or "",
        "tags": [t.get("term") for t in (obj.get("tags") or []) if t.get("term")],
        "creditLine": obj.get("creditLine") or "",
        "culture": obj.get("culture") or "",
    }


def main() -> None:
    pool: list[dict] = []
    seen: set[int] = set()
    for dept_id, dept_name in DEPARTMENTS.items():
        print(f"Searching {dept_name} (dept {dept_id})...")
        # Tier 1: highlighted on-view works. Tier 2: any on-view work with images.
        # De-dup across tiers so highlights come first but the department still fills out.
        highlight_ids = met_client.search(
            dept_id, isOnView="true", hasImages="true", isHighlight="true"
        )
        onview_ids = met_client.search(dept_id, isOnView="true", hasImages="true")
        # Fallback for sparse departments: any imaged work (not necessarily on view).
        any_ids = met_client.search(dept_id, hasImages="true", isHighlight="true")
        merged: list[int] = []
        for group in (highlight_ids, onview_ids, any_ids):
            for i in group:
                if i not in merged:
                    merged.append(i)
        ordered = merged
        print(
            f"  {len(highlight_ids)} hl-onview, {len(onview_ids)} on-view, "
            f"{len(any_ids)} hl-any; fetching up to {SEED_PER_DEPARTMENT}"
        )
        kept = 0
        for oid in ordered:
            if kept >= SEED_PER_DEPARTMENT:
                break
            if oid in seen:
                continue
            obj = met_client.get_object(oid)
            if not obj:
                continue
            slimmed = slim(obj)
            if not slimmed:
                continue
            pool.append(slimmed)
            seen.add(oid)
            kept += 1
        print(f"  kept {kept}")

    out = DATA_DIR / "pool.json"
    out.write_text(json.dumps(pool, indent=2))
    print(f"\nWrote {len(pool)} objects to {out}")


if __name__ == "__main__":
    main()
