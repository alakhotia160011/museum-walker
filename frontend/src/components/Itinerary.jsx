import { useEffect, useRef, useState } from "react";
import { routeIntro, fetchAudioUrl } from "../api.js";

const runtime = (s) => `${Math.max(1, Math.round((s.estSeconds || 0) / 60))} min`;
const distinct = (arr) => [...new Set(arr.filter(Boolean))];

export default function Route({ tour, onOpen, onRestart }) {
  const { meta, stops } = tour;
  const wings = distinct(stops.map((s) => s.department));
  const [intro, setIntro] = useState(null);
  const [speaking, setSpeaking] = useState(false);
  const audioRef = useRef(null);

  function stopSpeak() {
    if (audioRef.current) audioRef.current.pause();
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    setSpeaking(false);
  }

  async function speak(text) {
    if (!text) return;
    stopSpeak();
    if (meta.hasTts) {
      const url = await fetchAudioUrl(text, meta.vibe);
      if (url && audioRef.current) {
        audioRef.current.src = url;
        try { await audioRef.current.play(); setSpeaking(true); } catch (e) { /* autoplay blocked */ }
        return;
      }
    }
    if (window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(text);
      u.onend = () => setSpeaking(false);
      window.speechSynthesis.speak(u);
      setSpeaking(true);
    }
  }

  useEffect(() => {
    const s0 = stops[0] || {};
    const summary = {
      start: { title: s0.title, department: s0.department, gallery: s0.gallery, floor: s0.floor },
      wings,
      floors: distinct(stops.map((s) => s.floor)),
      stopCount: meta.stopCount,
      estMinutes: meta.estMinutes,
    };
    let cancelled = false;
    routeIntro({ summary, level: meta.level, vibe: meta.vibe, themes: meta.themes, eras: meta.eras })
      .then((r) => { if (!cancelled) { setIntro(r.intro); speak(r.intro); } })
      .catch(() => {});
    return () => { cancelled = true; stopSpeak(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

        <div className="intro">
          <button
            className={`intro-play ${speaking ? "live" : ""}`}
            onClick={() => (speaking ? stopSpeak() : speak(intro))}
            disabled={!intro}
            aria-label={speaking ? "Pause welcome" : "Hear welcome"}
          >
            {speaking ? "❚❚" : "▶"}
          </button>
          <p className="intro-text serif">{intro || "Your guide is gathering the welcome…"}</p>
        </div>

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
        <button className="cta" onClick={() => { stopSpeak(); onOpen(0); }}>
          Begin the walk <span className="arrow">→</span>
        </button>
      </div>
      <audio ref={audioRef} onEnded={() => setSpeaking(false)} hidden />
    </div>
  );
}
