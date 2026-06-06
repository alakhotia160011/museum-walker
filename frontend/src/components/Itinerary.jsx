const runtime = (s) => `${Math.max(1, Math.round((s.estSeconds || 0) / 60))} min`;

export default function Route({ tour, onOpen, onRestart }) {
  const { meta, stops } = tour;
  const wings = [...new Set(stops.map((s) => s.department).filter(Boolean))];

  return (
    <div className="screen">
      <div className="page stagger">
        <button className="linkback" onClick={onRestart}>← Compose another</button>

        <header className="route-head">
          <p className="eyebrow">Your route</p>
          <h1 className="serif">{wings.join(" & ") || "A walk through The Met"}</h1>
          <div className="route-meta">
            <span className="num">{meta.estMinutes} minutes</span>
            <span className="dot num">{meta.stopCount} stops</span>
            <span className="dot themes">
              {meta.themes?.length ? meta.themes.join(" · ") : "A considered cross-section"}
            </span>
          </div>
        </header>

        <ol className="itinerary">
          {stops.map((s, i) => (
            <li key={s.stopId} className="stop-row" onClick={() => onOpen(i)}>
              <span className="idx num">{String(i + 1).padStart(2, "0")}</span>
              <span className="thumb">
                {s.image ? <img src={s.image} alt={s.title} loading="lazy" /> : null}
              </span>
              <span className="info">
                <h3 className="title">{s.title}</h3>
                <p className="by">{s.artist}{s.date ? `, ${s.date}` : ""}</p>
                <p className="where">
                  {s.department}
                  {s.gallery ? ` · Gallery ${s.gallery}` : ""}
                  {s.isHighlight ? <span className="star"> · ★ Signature work</span> : ""}
                </p>
              </span>
              <span className="runtime">{runtime(s)}</span>
            </li>
          ))}
        </ol>
      </div>

      <div className="actionbar">
        <button className="cta" onClick={() => onOpen(0)}>
          Begin the walk <span className="arrow">→</span>
        </button>
      </div>
    </div>
  );
}
