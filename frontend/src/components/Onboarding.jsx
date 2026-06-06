import { useState } from "react";

const TIMES = [20, 45, 90];
const LEVELS = ["Casual", "Enthusiast", "Expert"];
const VIBES = ["Storyteller", "Art historian", "Quick hits", "Kid-friendly"];
const ERAS = ["Ancient", "Medieval", "Renaissance", "Baroque", "18th–19th c.", "Modern"];

// mirrors curator.py timing so the visitor sees a derived stop count
const LISTEN = { Casual: 1.5, Enthusiast: 2.5, Expert: 3.5 };
const BUFFER = 1.5;
const derivedStops = (minutes, level) =>
  Math.max(1, Math.floor(minutes / (LISTEN[level] + BUFFER)));

export default function Compose({ themes, onCompose, error }) {
  const [minutes, setMinutes] = useState(45);
  const [selected, setSelected] = useState([]);
  const [level, setLevel] = useState("Casual");
  const [vibe, setVibe] = useState("Storyteller");
  const [eras, setEras] = useState([]);
  const [mustSee, setMustSee] = useState(true);

  const toggleTheme = (id) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const toggleEra = (e) =>
    setEras((s) => (s.includes(e) ? s.filter((x) => x !== e) : [...s, e]));

  const Chip = ({ on, onClick, children, title }) => (
    <button type="button" className="chip" aria-pressed={on} onClick={onClick} title={title}>
      {children}
    </button>
  );

  return (
    <div className="screen">
      <div className="page stagger">
        <header className="masthead">
          <p className="eyebrow">The Metropolitan Museum of Art</p>
          <h1 className="wordmark">Docent</h1>
          <hr className="rule" />
          <p className="colophon">
            Your own voice docent. Tell me how long you have and what moves you, and I'll
            compose a geospatially optimized route through the real galleries — least
            backtracking, fewest stairs — narrate each stop aloud, and answer whatever you
            ask. Artwork and collection data are public domain, courtesy of the{" "}
            <a href="https://metmuseum.github.io/" target="_blank" rel="noreferrer">
              Met Collection API
            </a>.
          </p>
        </header>

        <p className="lede serif">Compose your visit.</p>

        <section className="section">
          <div className="section-head">
            <span className="numeral">I</span>
            <span className="label">How long you have</span>
            <span className="aside num">about {derivedStops(minutes, level)} stops</span>
          </div>
          <div className="chips">
            {TIMES.map((t) => (
              <Chip key={t} on={minutes === t} onClick={() => setMinutes(t)}>
                <span className="num">{t}</span> minutes
              </Chip>
            ))}
          </div>
        </section>

        <section className="section">
          <div className="section-head">
            <span className="numeral">II</span>
            <span className="label">What you care about</span>
            <span className="aside">{selected.length ? `${selected.length} chosen` : "optional"}</span>
          </div>
          <div className="chips">
            {themes.map((t) => (
              <Chip key={t.id} on={selected.includes(t.id)} onClick={() => toggleTheme(t.id)} title={t.blurb}>
                {t.label}
              </Chip>
            ))}
          </div>
          <div className="field-group">
            <p className="field-label">Periods you're drawn to</p>
            <div className="chips">
              {ERAS.map((e) => (
                <Chip key={e} on={eras.includes(e)} onClick={() => toggleEra(e)}>{e}</Chip>
              ))}
            </div>
          </div>
        </section>

        <section className="section">
          <div className="section-head">
            <span className="numeral">III</span>
            <span className="label">The voice</span>
          </div>
          <div className="field-group">
            <p className="field-label">How much you already know</p>
            <div className="chips">
              {LEVELS.map((l) => (
                <Chip key={l} on={level === l} onClick={() => setLevel(l)}>{l}</Chip>
              ))}
            </div>
          </div>
          <div className="field-group">
            <p className="field-label">The tone of the narration</p>
            <div className="chips">
              {VIBES.map((v) => (
                <Chip key={v} on={vibe === v} onClick={() => setVibe(v)}>{v}</Chip>
              ))}
            </div>
          </div>

          <label className="toggle">
            <input type="checkbox" checked={mustSee} onChange={(e) => setMustSee(e.target.checked)} />
            <span>Include the museum's signature works</span>
          </label>
        </section>

        {error && <p className="error">{error}</p>}
      </div>

      <div className="actionbar">
        <button
          className="cta"
          onClick={() => onCompose({ minutes, themes: selected, level, vibe, eras, mustSee })}
        >
          Compose the route <span className="arrow">→</span>
        </button>
      </div>
    </div>
  );
}
