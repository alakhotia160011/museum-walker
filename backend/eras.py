"""Historical-period (era) classification from an object's free-form date string.

The MET pool only carries a human date string ("ca. 1550-1295 B.C.", "late 17th
century", "1847-50"), with no numeric begin/end fields. This module parses that
string into a single representative year (negative for B.C.) and buckets it into
one of the onboarding eras, so era preferences can steer curation the same way
themes do. Matching the era labels here to the frontend chips is load-bearing:
they must stay in sync with ERAS in frontend/src/components/Onboarding.jsx.
"""
from __future__ import annotations

import re

# Era label -> (min_year, max_year) inclusive, years negative for B.C.
# Non-overlapping buckets aligned to the onboarding chips. Baroque is treated as
# the 17th century, "18th-19th c." as 1700-1899, Modern as 1900 onward.
ERA_BOUNDS: dict[str, tuple[float, float]] = {
    "Ancient": (-float("inf"), 499),
    "Medieval": (500, 1399),
    "Renaissance": (1400, 1599),
    "Baroque": (1600, 1699),
    "18th–19th c.": (1700, 1899),
    "Modern": (1900, float("inf")),
}

_ORDINAL = re.compile(r"(\d+)\s*(?:st|nd|rd|th)\s+century", re.IGNORECASE)
_YEAR = re.compile(r"\d{1,4}")


def parse_year(date: str | None) -> int | None:
    """Return a representative year for `date` (negative for B.C.), or None if no
    year can be read. Ranges collapse to their midpoint; centuries to their middle
    year; abbreviated range ends ("1847-50") are expanded against the start."""
    if not date:
        return None
    s = date.strip()
    if not s:
        return None
    bc = bool(re.search(r"\bB\.?C\.?(?:E\.?)?\b", s, re.IGNORECASE))

    century = _ORDINAL.search(s)
    if century:
        n = int(century.group(1))
        year = (n - 1) * 100 + 50  # middle of the century
        return -year if bc else year

    nums = [int(m) for m in _YEAR.findall(s)]
    if not nums:
        return None
    if len(nums) >= 2:
        a, b = nums[0], nums[1]
        # Expand an abbreviated A.D. range end ("1847-50" -> 1850, "1745-55" -> 1755).
        if not bc and a >= 100 and b < 100:
            b = (a // 100) * 100 + b
        year = (a + b) // 2
    else:
        year = nums[0]
    return -year if bc else year


def classify_era(date: str | None) -> str | None:
    """Bucket `date` into one of ERA_BOUNDS, or None if it can't be placed."""
    year = parse_year(date)
    if year is None:
        return None
    for label, (lo, hi) in ERA_BOUNDS.items():
        if lo <= year <= hi:
            return label
    return None


def era_list() -> list[dict]:
    """Shape for the frontend onboarding chips (label order = chronological)."""
    return [{"id": label, "label": label} for label in ERA_BOUNDS]


def score_eras(obj: dict, selected: list[str]) -> int:
    """1 if the object's era is among the visitor's selected periods, else 0."""
    if not selected:
        return 0
    era = classify_era(obj.get("date"))
    return 1 if era in selected else 0
