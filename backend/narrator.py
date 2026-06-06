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
    "You are the voice of a personalized museum audio guide at The Metropolitan Museum of Art. "
    "You write short spoken-word narration scripts for a single artwork, meant to be heard "
    "(not read) while the visitor stands in front of the piece. Speak directly to the listener. "
    "No headings, no markdown, no stage directions, no 'welcome to'—just the narration itself. "
    "Be accurate to the metadata provided; do not invent facts, signatures, or provenance."
)

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic()
    return _client


def _fallback_script(stop: dict, themes: list[str]) -> str:
    title = stop["title"]
    artist = stop["artist"]
    date = stop.get("date") or "an uncertain date"
    medium = stop.get("medium") or "mixed media"
    tags = ", ".join(stop.get("tags", [])[:4])
    theme_line = f" If you came for {themes[0].lower()}, look closely here." if themes else ""
    return (
        f"Take a moment with {title}. This piece is by {artist}, dating from {date}. "
        f"It's made in {medium}.{(' Notice the ' + tags + '.') if tags else ''} "
        f"Let your eye travel across the composition—where does it rest first, and why might the "
        f"artist have wanted it there?{theme_line} "
        f"When you're ready, take one last look, then move on to the next stop."
    )


def generate_script(stop: dict, themes: list[str], level: str, vibe: str) -> dict:
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
        f"Write a roughly {target}-word spoken narration for this artwork.\n\n"
        f"Voice/persona: {persona}.\n"
        f"Listener level: {level}. {level_note}\n"
        f"The visitor chose these interests, so frame the piece toward them where honest: {interests}.\n\n"
        f"Artwork metadata:\n"
        f"- Title: {stop['title']}\n"
        f"- Artist/culture: {stop['artist']}\n"
        f"- Date: {stop.get('date')}\n"
        f"- Medium: {stop.get('medium')}\n"
        f"- Department: {stop.get('department')}\n"
        f"- Subject tags: {tags}\n\n"
        f"Return only the narration text."
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
    "You are the voice of a personalized museum audio guide at The Metropolitan Museum of Art, "
    "standing beside the visitor in front of an artwork and answering their questions out loud. "
    "Speak directly to the listener in a warm, knowledgeable docent's voice. Keep answers short and "
    "spoken — roughly 40 to 80 words, no headings, no markdown, no lists. Be accurate to the metadata "
    "and narration you are given; never invent facts, signatures, provenance, or attributions you "
    "aren't sure of — if you don't know, say so briefly and offer what you can. For questions about "
    "where to go next, use the next-stop location provided. Gently redirect questions unrelated to the "
    "art or the museum."
)


def _qa_fallback(stop: dict, question: str, next_stop: dict | None) -> str:
    q = question.lower()
    if next_stop and any(w in q for w in ("next", "where", "go", "after this", "onward")):
        g = next_stop.get("gallery")
        fl = next_stop.get("floor")
        loc = f"Gallery {g}" + (f" on {fl}" if fl else "") if g else "the next room"
        return f"Your next stop is {next_stop.get('title','the next work')}, in {loc}. Head there when you're ready."
    bits = [f"This is {stop.get('title','this work')}"]
    if stop.get("artist") and stop["artist"] != "Unknown":
        bits.append(f"by {stop['artist']}")
    if stop.get("date"):
        bits.append(f"dating from {stop['date']}")
    line = ", ".join(bits) + "."
    if stop.get("medium"):
        line += f" It's made in {stop['medium']}."
    if stop.get("department"):
        line += f" You'll find it in {stop['department']}."
    return line + " Ask me about the artist, the materials, or what to look for."


def answer_question(
    stop: dict,
    question: str,
    level: str = "Casual",
    vibe: str = "Storyteller",
    themes: list[str] | None = None,
    history: list[dict] | None = None,
    next_stop: dict | None = None,
) -> dict:
    """Answer a visitor's question about the current artwork in the docent's voice.
    Returns {'answer': str, 'source': 'claude'|'fallback'}."""
    themes = themes or []
    if not HAS_CLAUDE:
        return {"answer": _qa_fallback(stop, question, next_stop), "source": "fallback"}

    persona = VIBES.get(vibe, VIBES["Storyteller"])
    level_note = LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE["Casual"])
    tags = ", ".join(stop.get("tags", [])[:8])
    nxt = ""
    if next_stop:
        g = next_stop.get("gallery")
        nxt = (
            f"\nNext stop on the tour: {next_stop.get('title')} in "
            f"{('Gallery ' + str(g)) if g else 'the next room'}"
            f"{(', ' + next_stop['floor']) if next_stop.get('floor') else ''}."
        )

    context = (
        f"You are standing in front of this artwork:\n"
        f"- Title: {stop.get('title')}\n"
        f"- Artist/culture: {stop.get('artist')}\n"
        f"- Date: {stop.get('date')}\n"
        f"- Medium: {stop.get('medium')}\n"
        f"- Department: {stop.get('department')}\n"
        f"- Gallery: {stop.get('gallery')}\n"
        f"- Subject tags: {tags}\n"
        f"The narration you already gave the visitor:\n\"{(stop.get('script') or '').strip()}\"\n"
        f"Voice: {persona}. Listener level: {level}. {level_note}{nxt}\n\n"
        f"Answer the visitor's question."
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
