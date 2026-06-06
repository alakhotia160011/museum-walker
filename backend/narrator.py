"""Narration script generation.

Uses Claude when ANTHROPIC_API_KEY is set (with prompt caching on the shared system
prompt so multi-stop generation is cheap/fast). Falls back to a readable template
script when no key is present, so the app always works for a demo."""
from __future__ import annotations

from config import CLAUDE_MODEL, HAS_CLAUDE, WORDS_PER_MINUTE

VIBES = {
    "Storyteller": "a warm, vivid storyteller who hooks the listener with narrative and human detail",
    "Art historian": "a precise art historian who explains style, technique, and historical context",
    "Quick hits": "punchy and efficient, leading with the single most striking thing",
    "Kid-friendly": "playful and clear, like talking to a curious 10-year-old, no jargon",
}

LEVEL_GUIDANCE = {
    "Casual": "Assume no background. Avoid jargon. Keep it light and memorable.",
    "Enthusiast": "Assume genuine interest. You can name movements and techniques.",
    "Expert": "Assume deep knowledge. Offer nuanced, specific, less-obvious observations.",
}

_SYSTEM = (
    "You ARE the artist who made the work being described, speaking aloud in the first person "
    "to a visitor standing in front of it at The Metropolitan Museum of Art. Use 'I' and 'my': "
    "talk about why I made it, what I was reaching for, the materials in my hands, and the world "
    "I worked in. This is spoken word, meant to be heard, not read, no headings, no markdown, no "
    "stage directions, no 'welcome to', just my own voice. "
    "Stay truthful to the metadata you are given: never invent names, dates, signatures, patrons, "
    "or provenance you weren't told. You may imagine inner intent and feeling in a grounded, "
    "plausible way, but never state invented facts as history. "
    "If the maker is listed as Unknown, a culture, a people, a dynasty, or a workshop rather than "
    "a named individual, speak as an unnamed maker from that culture and time, and never claim a "
    "name you don't have."
)

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic()
    return _client


# Culture / nationality / place labels that the MET stores in the `artist` field for
# anonymous works ("Roman", "Greek, Attic", "Egyptian"). Used only by the no-API fallback
# to avoid "I am Roman"; the Claude path is told to make this judgment itself.
_CULTURES = {
    "american", "french", "british", "english", "german", "italian", "spanish", "dutch",
    "flemish", "netherlandish", "austrian", "swiss", "russian", "irish", "scottish", "danish",
    "swedish", "norwegian", "belgian", "portuguese", "greek", "roman", "etruscan", "cypriot",
    "minoan", "mycenaean", "hellenistic", "byzantine", "coptic", "egyptian", "nubian", "assyrian",
    "babylonian", "sumerian", "mesopotamian", "sasanian", "achaemenid", "persian", "phoenician",
    "celtic", "frankish", "catalan", "chinese", "china", "japanese", "korean", "indian", "tibetan",
    "nepalese", "thai", "khmer", "javanese", "islamic", "ottoman", "mughal", "safavid", "mexican",
    "peruvian", "mayan", "aztec", "olmec", "incan", "near eastern", "south netherlandish",
    "north netherlandish",
}


def _is_named(artist: str | None) -> bool:
    """True if `artist` reads as a named individual rather than Unknown or a culture/workshop.
    A heuristic for the no-API fallback only; the Claude path lets the model decide."""
    a = (artist or "").strip()
    if not a:
        return False
    low = a.lower()
    if low in ("unknown", "unknown artist", "anonymous", "unidentified", "unidentified artist"):
        return False
    markers = ("culture", "dynasty", "workshop", "manufactory", "factory", "people", "tribe")
    if any(m in low for m in markers):
        return False
    head = low.split(",")[0].strip()  # "greek, attic" -> "greek"
    return head not in _CULTURES


def _fallback_script(stop: dict, themes: list[str]) -> str:
    title = stop["title"]
    artist = stop["artist"]
    date = stop.get("date") or "a time I can no longer name"
    medium = stop.get("medium") or "what I had to hand"
    tags = ", ".join(stop.get("tags", [])[:4])
    theme_line = f" If you came for {themes[0].lower()}, look closely here." if themes else ""
    if _is_named(artist):
        opener = f"I am {artist}."
    elif artist and artist.strip().lower() not in ("unknown", "anonymous", "unidentified"):
        opener = f"You won't find my name on this, but I made it, a maker of the {artist} world."
    else:
        opener = "You won't find my name on this, but the hands that made it were mine."
    return (
        f"{opener} This is {title}, which I made in {date}, worked in {medium}."
        f"{(' Look for the ' + tags + '.') if tags else ''} "
        f"Let your eye travel across it, where does it settle first? That is where I wanted "
        f"you to begin.{theme_line} "
        f"Stay as long as you like, then carry on to the next piece."
    )


def _lang_note(language: str | None) -> str:
    """Instruction appended to a prompt so Claude writes in the visitor's language.
    Empty for English (the default)."""
    lang = (language or "English").strip()
    if not lang or lang.lower() == "english":
        return ""
    return (
        f"Write your entire response in {lang} — natural, fluent {lang}, not a word-for-word "
        f"translation. Keep any proper names (artist, place, the work's title) as they are. "
    )


def generate_script(stop: dict, themes: list[str], level: str, vibe: str, language: str = "English") -> dict:
    """Return {'script': str, 'estSeconds': int, 'source': 'claude'|'fallback'}."""
    if not HAS_CLAUDE:
        text = _fallback_script(stop, themes)
        return {"script": text, "estSeconds": _est_seconds(text), "source": "fallback"}

    persona = VIBES.get(vibe, VIBES["Storyteller"])
    level_note = LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE["Casual"])
    target = stop.get("targetWords", 250)
    interests = ", ".join(themes) if themes else "general interest"
    tags = ", ".join(stop.get("tags", [])[:8])

    user_prompt = (
        f"Speak as the maker of this work, in the first person, for roughly {target} words.\n\n"
        f"Tone: {persona}.\n"
        f"Listener level: {level}. {level_note}\n"
        f"The visitor came especially for these interests, so lean toward them where it's honest "
        f"to your work: {interests}.\n\n"
        f"The work, in the museum's words (this is what you must stay truthful to):\n"
        f"- Title: {stop['title']}\n"
        f"- Maker (you): {stop['artist']}\n"
        f"- Date: {stop.get('date')}\n"
        f"- Medium: {stop.get('medium')}\n"
        f"- Department: {stop.get('department')}\n"
        f"- Subject tags: {tags}\n\n"
        f"If 'Maker (you)' is a named person, speak as them. If it is Unknown or a "
        f"culture/people/dynasty/workshop, speak as an unnamed maker of that culture and period. "
        f"{_lang_note(language)}"
        f"Return only your spoken words."
    )

    try:
        client = _get_client()
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=900,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        if not text:
            raise ValueError("empty response")
        return {"script": text, "estSeconds": _est_seconds(text), "source": "claude"}
    except Exception as e:  # graceful fallback keeps the demo alive
        print(f"[narrator] Claude failed ({e}); using fallback")
        text = _fallback_script(stop, themes)
        return {"script": text, "estSeconds": _est_seconds(text), "source": "fallback"}


def _est_seconds(text: str) -> int:
    words = len(text.split())
    return max(15, int(words / WORDS_PER_MINUTE * 60))


# --- Interactive Q&A: "Ask the docent" -------------------------------------
_QA_SYSTEM = (
    "You ARE the artist who created the artwork the visitor is standing in front of at The "
    "Metropolitan Museum of Art, answering their questions out loud, in the first person, in your "
    "own voice. Keep answers short and spoken, roughly 40 to 80 words, no headings, no markdown, "
    "no lists. Stay truthful to the metadata and to what you already told them; never invent names, "
    "dates, signatures, patrons, provenance, or attributions you weren't given, if you don't know, "
    "say so plainly and offer what you can. You may speak to your own intent and feeling in a "
    "grounded way. If the maker is listed as Unknown or a culture rather than a named individual, "
    "speak as an unnamed maker of that culture and never claim a name. For questions about where to "
    "go next, tell them the next stop and where to find it. Gently redirect questions unrelated to "
    "the art or the museum."
)


def _qa_fallback(stop: dict, question: str, next_stop: dict | None) -> str:
    q = question.lower()
    if next_stop and any(w in q for w in ("next", "where", "go", "after this", "onward")):
        g = next_stop.get("gallery")
        fl = next_stop.get("floor")
        loc = f"Gallery {g}" + (f" on {fl}" if fl else "") if g else "the next room"
        return (
            f"From here, go on to {next_stop.get('title','the next work')}, in {loc}. "
            f"I hope it speaks to you."
        )
    title = stop.get("title", "this work")
    opener = f"I made {title}" if _is_named(stop.get("artist")) else f"You're looking at {title}, which I made"
    line = opener
    if stop.get("date"):
        line += f", back in {stop['date']}"
    line += "."
    if stop.get("medium"):
        line += f" I worked it in {stop['medium']}."
    return line + " Ask me why I made it, what it's made of, or what to look for."


def answer_question(
    stop: dict,
    question: str,
    level: str = "Casual",
    vibe: str = "Storyteller",
    themes: list[str] | None = None,
    eras: list[str] | None = None,
    history: list[dict] | None = None,
    next_stop: dict | None = None,
    language: str = "English",
) -> dict:
    """Answer a visitor's question about the current artwork in the artist's own (first-person)
    voice, tuned to the visitor's tastes (themes = type of art, eras = time periods).
    Returns {'answer': str, 'source': 'claude'|'fallback'}."""
    themes = themes or []
    eras = eras or []
    if not HAS_CLAUDE:
        return {"answer": _qa_fallback(stop, question, next_stop), "source": "fallback"}

    persona = VIBES.get(vibe, VIBES["Storyteller"])
    level_note = LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE["Casual"])
    tags = ", ".join(stop.get("tags", [])[:8])
    taste = []
    if themes:
        taste.append(f"kinds of art: {', '.join(themes)}")
    if eras:
        taste.append(f"time periods: {', '.join(eras)}")
    taste_line = (
        f"This visitor is especially drawn to {'; '.join(taste)}. Where it's honest and "
        f"relevant, connect your answer to those interests (e.g. how this work relates to "
        f"that period or theme) - but never force it or invent connections.\n"
        if taste else ""
    )
    nxt = ""
    if next_stop:
        g = next_stop.get("gallery")
        nxt = (
            f"\nNext stop on the tour: {next_stop.get('title')} in "
            f"{('Gallery ' + str(g)) if g else 'the next room'}"
            f"{(', ' + next_stop['floor']) if next_stop.get('floor') else ''}."
        )

    context = (
        f"You made this work:\n"
        f"- Title: {stop.get('title')}\n"
        f"- Maker (you): {stop.get('artist')}\n"
        f"- Date: {stop.get('date')}\n"
        f"- Medium: {stop.get('medium')}\n"
        f"- Department: {stop.get('department')}\n"
        f"- Gallery: {stop.get('gallery')}\n"
        f"- Subject tags: {tags}\n"
        f"What you already told the visitor about it:\n\"{(stop.get('script') or '').strip()}\"\n"
        f"{taste_line}"
        f"Tone: {persona}. Listener level: {level}. {level_note}{nxt}\n\n"
        f"If 'Maker (you)' is a named person, answer as them; if it is Unknown or a culture, "
        f"answer as an unnamed maker of that culture. {_lang_note(language)}"
        f"Answer the visitor's question in your own voice."
    )

    messages = [{"role": "user", "content": context}]
    for turn in (history or [])[-6:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question.strip()})

    try:
        client = _get_client()
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=400,
            system=[{"type": "text", "text": _QA_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        if not text:
            raise ValueError("empty response")
        return {"answer": text, "source": "claude"}
    except Exception as e:
        print(f"[narrator] Q&A Claude failed ({e}); using fallback")
        return {"answer": _qa_fallback(stop, question, next_stop), "source": "fallback"}


# --- Route intro: orient the visitor before the first work --------------------
_INTRO_SYSTEM = (
    "You are the voice of a personalized audio guide at The Metropolitan Museum of Art, "
    "welcoming a visitor at the start of their self-guided walk. Speak directly, warm and "
    "composed, like a docent setting off. Orient them: where the walk begins, the wings and "
    "floors it moves through, and its scope. Keep it to 2-3 spoken sentences (~50-70 words), "
    "no headings or markdown or lists, and end by inviting them to the first work. Be accurate "
    "to the facts given; do not invent galleries, names, or details."
)


def _intro_fallback(summary: dict) -> str:
    start = summary.get("start") or {}
    wings = summary.get("wings") or []
    title = start.get("title") or "your first work"
    where = start.get("department") or "the galleries"
    g = start.get("gallery")
    floor = start.get("floor")
    loc = where + (f", Gallery {g}" if g else "") + (f" on {floor}" if floor else "")
    rest = ""
    if len(wings) > 1:
        rest = f" From there we'll move through {', '.join(wings[1:])}."
    count = summary.get("stopCount")
    minutes = summary.get("estMinutes")
    scope = f" {count} works, about {minutes} minutes." if count and minutes else ""
    return f"Welcome. We'll begin with {title}, in {loc}.{rest}{scope} Let's step in."


def route_intro(summary: dict, level: str, vibe: str, themes=None, eras=None, language: str = "English") -> dict:
    """A short spoken welcome that orients the visitor before the first stop.
    `summary` = {start:{title,department,gallery,floor}, wings:[...], floors:[...],
    stopCount, estMinutes}. Returns {'intro': str, 'source': 'claude'|'fallback'}."""
    themes = themes or []
    eras = eras or []
    if not HAS_CLAUDE:
        return {"intro": _intro_fallback(summary), "source": "fallback"}

    start = summary.get("start") or {}
    persona = VIBES.get(vibe, VIBES["Storyteller"])
    facts = (
        f"- Begins with: {start.get('title')} in {start.get('department')}"
        f"{', Gallery ' + str(start.get('gallery')) if start.get('gallery') else ''}"
        f"{' on ' + start.get('floor') if start.get('floor') else ''}\n"
        f"- Wings on the route, in order: {', '.join(summary.get('wings') or []) or 'one wing'}\n"
        f"- Floors visited, in order: {', '.join(summary.get('floors') or []) or 'one floor'}\n"
        f"- Scope: {summary.get('stopCount')} works, about {summary.get('estMinutes')} minutes\n"
        f"- Visitor leans toward: {', '.join(themes) or 'a bit of everything'}"
        f"{'; periods ' + ', '.join(eras) if eras else ''}\n"
    )
    user_prompt = (
        f"Voice/persona: {persona}.\n"
        f"{_lang_note(language)}"
        f"Write the opening welcome for this walk.\n\n{facts}"
    )
    try:
        client = _get_client()
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            system=[{"type": "text", "text": _INTRO_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        if not text:
            raise ValueError("empty response")
        return {"intro": text, "source": "claude"}
    except Exception as e:
        print(f"[narrator] intro Claude failed ({e}); using fallback")
        return {"intro": _intro_fallback(summary), "source": "fallback"}
