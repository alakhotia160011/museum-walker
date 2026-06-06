import { useState } from "react";

const TIMES = [20, 45, 90];
const LEVELS = ["Casual", "Enthusiast", "Expert"];
const VIBES = ["Storyteller", "Art historian", "Quick hits", "Kid-friendly"];

export default function Onboarding({ themes, onStart, loading, error }) {
  const [minutes, setMinutes] = useState(45);
  const [selected, setSelected] = useState([]);
  const [level, setLevel] = useState("Casual");
  const [vibe, setVibe] = useState("Storyteller");
  const [mustSee, setMustSee] = useState(true);

  function toggleTheme(id) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  return (
    <div className="screen onboarding">
      <header className="hero">
        <p className="kicker">The Met · Personalized Audio Guide</p>
        <h1>How do you want to experience the museum today?</h1>
        <p className="sub">Tell us your time and your taste. We'll craft a path just for you.</p>
      </header>

      <section className="block">
        <h2>I have…</h2>
        <div className="pills">
          {TIMES.map((t) => (
            <button
              key={t}
              className={`pill ${minutes === t ? "on" : ""}`}
              onClick={() => setMinutes(t)}
            >
              {t} min
            </button>
          ))}
        </div>
      </section>

      <section className="block">
        <h2>I'm interested in…</h2>
        <div className="chips">
          {themes.map((t) => (
            <button
              key={t.id}
              className={`chip ${selected.includes(t.id) ? "on" : ""}`}
              onClick={() => toggleTheme(t.id)}
              title={t.blurb}
            >
              {t.label}
            </button>
          ))}
        </div>
      </section>

      <section className="block two">
        <div>
          <h2>My level</h2>
          <div className="pills">
            {LEVELS.map((l) => (
              <button key={l} className={`pill ${level === l ? "on" : ""}`} onClick={() => setLevel(l)}>
                {l}
              </button>
            ))}
          </div>
        </div>
        <div>
          <h2>Narration vibe</h2>
          <div className="pills">
            {VIBES.map((v) => (
              <button key={v} className={`pill ${vibe === v ? "on" : ""}`} onClick={() => setVibe(v)}>
                {v}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="block">
        <label className="toggle">
          <input type="checkbox" checked={mustSee} onChange={(e) => setMustSee(e.target.checked)} />
          <span>Always include must-see highlights</span>
        </label>
      </section>

      {error && <p className="error">{error}</p>}

      <button
        className="cta"
        disabled={loading}
        onClick={() => onStart({ minutes, themes: selected, level, vibe, mustSee })}
      >
        {loading ? "Crafting your path…" : "Build my tour →"}
      </button>
    </div>
  );
}
