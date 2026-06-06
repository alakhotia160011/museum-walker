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
