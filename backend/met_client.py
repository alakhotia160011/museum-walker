"""Thin wrapper over the MET Collection API with on-disk caching.

MET objects are effectively static, so cached object JSON never expires.
Docs: https://metmuseum.github.io/  (free, no auth, CC0)."""
from __future__ import annotations

import json
import time

import requests

from config import CACHE_DIR, MET_API_BASE

_OBJ_CACHE = CACHE_DIR / "objects"
_OBJ_CACHE.mkdir(exist_ok=True)

_session = requests.Session()
_session.headers.update({"User-Agent": "met-audio-guide-hackathon/1.0"})


def search(department_id: int, **params) -> list[int]:
    """Return object IDs for a department, with optional filters
    (isOnView, isHighlight, hasImages, q, tags, ...)."""
    q = {"departmentId": department_id, "q": params.pop("q", "*")}
    q.update(params)
    r = _session.get(f"{MET_API_BASE}/search", params=q, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("objectIDs") or []


def get_object(object_id: int) -> dict | None:
    """Fetch a single object record, caching the JSON to disk."""
    cached = _OBJ_CACHE / f"{object_id}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    try:
        r = _session.get(f"{MET_API_BASE}/objects/{object_id}", timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
    except requests.RequestException:
        return None
    obj = r.json()
    cached.write_text(json.dumps(obj))
    time.sleep(0.05)  # stay polite (limit is 80 req/s)
    return obj
