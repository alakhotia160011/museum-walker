export default function Itinerary({ tour, onOpen, onRestart }) {
  const { meta, stops } = tour;
  return (
    <div className="screen itinerary">
      <header className="itin-head">
        <button className="link" onClick={onRestart}>← New tour</button>
        <h1>Your path</h1>
        <p className="sub">
          {meta.stopCount} stops · about {meta.estMinutes} min ·{" "}
          {meta.themes.length ? meta.themes.join(" · ") : "A bit of everything"}
        </p>
        <p className="sub small">Level: {meta.level} · Voice: {meta.vibe}</p>
      </header>

      <ol className="stop-list">
        {stops.map((s, i) => (
          <li key={s.stopId} className="stop-card" onClick={() => onOpen(i)}>
            <span className="num">{i + 1}</span>
            <img src={s.image} alt={s.title} loading="lazy" />
            <div className="stop-meta">
              <h3>{s.title}</h3>
              <p>{s.artist}</p>
              <p className="muted">
                {s.department}
                {s.gallery ? ` · Gallery ${s.gallery}` : ""}
                {s.isHighlight ? " · ★ Highlight" : ""}
              </p>
            </div>
            <span className="play-dot">▶</span>
          </li>
        ))}
      </ol>

      <button className="cta" onClick={() => onOpen(0)}>
        Start the tour →
      </button>
    </div>
  );
}
