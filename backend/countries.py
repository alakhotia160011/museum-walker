"""Region / "where it's from" classification, the geographic counterpart to eras.py.

The MET pool carries several free-form origin signals per object — `culture`
("Greek, Attic"), `country` ("Egypt"), and `artistNationality` ("French") — plus the
collecting `department` ("Egyptian Art"), which is itself an unambiguous origin for some
wings. This module folds all of those into a single set of visitor-facing regions and a
`match(obj, selected)` test, so a region preference can hard-filter curation the same way
eras and themes steer it.

The region labels here are load-bearing: they must stay in sync with COUNTRIES in
frontend/src/components/Onboarding.jsx.
"""
from __future__ import annotations

# Region id -> (visitor-facing label, keyword tuple). Continent-scale buckets — kept to a
# short, legible set — matched as plain substrings against an object's lowercased origin
# text (culture + country + artistNationality). Ancient Greece/Rome and Egypt are split out
# from "Europe"/"Africa" because they're among the Met's largest and most distinct holdings.
_REGIONS: list[tuple[str, str, tuple[str, ...]]] = [
    ("north_america", "North America", (
        "american", "united states", "u.s.", "canada", "canadian",
    )),
    ("europe", "Europe", (
        "french", "france", "paris", "limoges", "sèvres", "sevres",
        "british", "english", "england", "britain", "scottish", "scotland", "welsh",
        "london", "irish", "ireland",
        "german", "germany", "austrian", "austria", "swiss", "switzerland", "bavarian",
        "saxon", "meissen", "viennese", "vienna",
        "dutch", "netherland", "flemish", "flanders", "holland", "netherlandish",
        "spanish", "spain", "catalan", "portuguese", "portugal", "iberian", "valencia",
        "italian", "italy", "venetian", "venice", "florentine", "florence", "naples",
        "sicilian", "tuscan",
        "byzantine", "russian", "russia", "polish", "poland", "czech", "scandinav",
        "swedish", "norwegian", "danish", "european",
    )),
    ("classical", "Ancient Greece & Rome", (
        "greek", "greece", "attic", "minoan", "mycenaean", "cypriot", "cyprus",
        "hellenistic", "corinthian", "roman", "rome", "etruscan", "pompeii",
    )),
    ("egypt", "Egypt", (
        "egypt", "egyptian", "nubian", "coptic",
    )),
    ("middle_east", "Middle East & Persia", (
        "islamic", "ottoman", "persian", "iran", "safavid", "qajar", "arab",
        "levant", "turkish", "turkey", "syria", "iraq", "mesopotamia", "assyrian",
        "babylonian", "sumerian", "sasanian", "phoenician", "anatolia",
    )),
    ("east_asia", "East Asia", (
        "china", "chinese", "tibet", "tibetan", "qing", "ming", "tang", "song dynasty",
        "japan", "japanese", "edo", "meiji", "korea", "korean", "joseon",
    )),
    ("south_se_asia", "South & Southeast Asia", (
        "india", "indian", "mughal", "nepal", "nepalese", "pakistan", "sri lanka",
        "gandhara", "kashmir", "bengal",
        "thai", "thailand", "khmer", "cambod", "java", "javanese", "indonesia",
        "vietnam", "burmese", "burma", "myanmar", "philippine",
    )),
    ("africa", "Africa", (
        "african", "africa", "benin", "yoruba", "congo", "mali", "ashanti", "kuba",
        "nigeria", "ghana", "ethiopia", "dogon",
    )),
    ("americas", "Latin & Ancient America", (
        "mexic", "aztec", "maya", "inca", "peru", "peruvian", "andean", "olmec",
        "colombia", "bolivia", "guatemala", "latin american", "pre-columbian",
    )),
]

# Departments whose origin is unambiguous even when the per-object origin text is bare.
_DEPT_REGION = {
    10: "egypt",        # Egyptian Art
    13: "classical",    # Greek and Roman Art
    14: "middle_east",  # Islamic Art
}

REGION_IDS = {rid for rid, _, _ in _REGIONS}


def region_list() -> list[dict]:
    """Shape for the frontend onboarding chips."""
    return [{"id": rid, "label": label} for rid, label, _ in _REGIONS]


def _origin_text(obj: dict) -> str:
    """The object's origin signals, lowercased and concatenated. Chinese export wares
    are tagged 'for American market' — strip that so they don't read as American."""
    text = " ".join((
        obj.get("culture") or "",
        obj.get("country") or "",
        obj.get("artistNationality") or "",
    )).lower()
    return text.replace("american market", "").replace("for american", "")


def regions_of(obj: dict) -> set[str]:
    """Every region this object plausibly belongs to (origin text + unambiguous dept)."""
    text = _origin_text(obj)
    hits = {rid for rid, _, kws in _REGIONS if any(k in text for k in kws)}
    dept_region = _DEPT_REGION.get(obj.get("departmentId"))
    if dept_region:
        hits.add(dept_region)
    return hits


def match(obj: dict, selected: list[str]) -> bool:
    """True if the object comes from any of the selected regions (or none selected)."""
    if not selected:
        return True
    sel = {s for s in selected if s in REGION_IDS}
    if not sel:
        return True
    return bool(regions_of(obj) & sel)


def score_regions(obj: dict, selected: list[str]) -> int:
    """1 if the object matches any selected region, else 0 (for department ranking)."""
    if not selected:
        return 0
    return 1 if match(obj, selected) else 0
