// API base: same-origin in production (Vercel), proxied in dev.
const BASE = "";

export async function getConfig() {
  const r = await fetch(`${BASE}/api/config`);
  return r.json();
}

export async function getThemes() {
  const r = await fetch(`${BASE}/api/themes`);
  const d = await r.json();
  return d.themes;
}

export async function buildItinerary(prefs) {
  const r = await fetch(`${BASE}/api/itinerary`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(prefs),
  });
  if (!r.ok) throw new Error("itinerary failed");
  return r.json();
}

// Generate a stop's narration on demand. Returns { script, spoken, source, estSeconds }.
export async function narrate({ stop, themes, level, vibe }) {
  const r = await fetch(`${BASE}/api/narrate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ stop, themes, level, vibe }),
  });
  if (!r.ok) throw new Error("narrate failed");
  return r.json();
}

// Ask the docent a question about the current artwork. Returns { answer, source }.
export async function askDocent({ stop, question, level, vibe, themes, eras, history, nextStop }) {
  const r = await fetch(`${BASE}/api/ask`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ stop, question, level, vibe, themes, eras, history, nextStop }),
  });
  if (!r.ok) throw new Error("ask failed");
  return r.json();
}

// Returns an object URL for the mp3, or null if the server has no TTS (use browser voice).
export async function fetchAudioUrl(text, vibe) {
  const r = await fetch(`${BASE}/api/audio`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text, vibe }),
  });
  if (r.status === 204) return null;
  if (!r.ok) return null;
  const blob = await r.blob();
  return URL.createObjectURL(blob);
}
