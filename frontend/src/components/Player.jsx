import { useEffect, useRef, useState } from "react";
import { fetchAudioUrl } from "../api.js";

export default function Stop({ stops, index, setIndex, hasTts, hasClaude, vibe, onBack }) {
  const stop = stops[index];
  const next = stops[index + 1];
  const [playing, setPlaying] = useState(false);
  const [loadingAudio, setLoadingAudio] = useState(false);
  const [progress, setProgress] = useState(0);
  const [imgError, setImgError] = useState(false);
  const audioRef = useRef(null);
  const audioUrlRef = useRef(null);

  // The narration audio includes the spoken walking cue; the printed essay does not.
  const essay =
    stop.transition && stop.script?.endsWith(stop.transition)
      ? stop.script.slice(0, -stop.transition.length).trim()
      : stop.script;

  function stopAll() {
    if (audioRef.current) audioRef.current.pause();
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    setPlaying(false);
    setProgress(0);
  }

  useEffect(() => {
    stopAll();
    setImgError(false);
    return stopAll;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  async function play() {
    if (hasTts) {
      setLoadingAudio(true);
      try {
        if (!audioUrlRef.current) audioUrlRef.current = await fetchAudioUrl(stop.script, vibe);
      } finally {
        setLoadingAudio(false);
      }
      if (audioUrlRef.current) {
        const el = audioRef.current;
        el.src = audioUrlRef.current;
        el.play();
        setPlaying(true);
        return;
      }
    }
    browserSpeak();
  }

  function browserSpeak() {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(stop.script);
    u.rate = vibe === "Quick hits" ? 1.12 : 1.0;
    u.onend = () => { setPlaying(false); setProgress(1); };
    window.speechSynthesis.speak(u);
    setPlaying(true);
  }

  function pause() {
    if (audioRef.current && !audioRef.current.paused) audioRef.current.pause();
    if (window.speechSynthesis?.speaking) window.speechSynthesis.pause();
    setPlaying(false);
  }

  function resume() {
    if (audioRef.current?.src && audioRef.current.paused) { audioRef.current.play(); setPlaying(true); return; }
    if (window.speechSynthesis?.paused) { window.speechSynthesis.resume(); setPlaying(true); return; }
    play();
  }

  function go(delta) {
    const n = index + delta;
    if (n < 0 || n >= stops.length) return;
    audioUrlRef.current = null;
    setIndex(n);
  }

  const caption =
    `${stop.scriptSource === "claude" || hasClaude ? "Script composed by Claude" : "Script from a template"}` +
    ` · ${hasTts ? "voiced by ElevenLabs" : "voiced in your browser"}`;

  return (
    <div className="screen">
      <div className="page stop stagger">
        <div className="stop-head">
          <button className="linkback" onClick={onBack}>← The route</button>
          <span className="where num">
            Stop {index + 1} of {stops.length}{stop.gallery ? ` · Gallery ${stop.gallery}` : ""}
          </span>
        </div>

        <header className="wall">
          <p className="eyebrow artist">{stop.artist}</p>
          <h1 className="serif">{stop.title}</h1>
          <p className="meta">
            {stop.date && <span>{stop.date}</span>}
            {stop.medium && <span>{stop.medium}</span>}
            {stop.department && <span>{stop.department}</span>}
            {stop.gallery && <span>Gallery {stop.gallery}</span>}
          </p>
        </header>

        <figure className={`plate${imgError || !stop.imageLarge ? " broken" : ""}`}>
          <div className="plate-inner">
            {!imgError && (stop.imageLarge || stop.image) && (
              <img
                src={stop.imageLarge || stop.image}
                alt={stop.title}
                onError={() => setImgError(true)}
              />
            )}
          </div>
        </figure>

        <div className="player">
          <div className="scrubber">
            <div className="fill" style={{ width: `${Math.round(progress * 100)}%` }} />
          </div>
          <div className="transport">
            <button className="skip" onClick={() => go(-1)} disabled={index === 0}>← Prev</button>
            <button className="play" onClick={playing ? pause : resume} aria-label={playing ? "Pause" : "Play"}>
              {loadingAudio ? "···" : playing ? "❚❚" : "▶"}
            </button>
            <span className={`eq ${playing ? "on" : ""}`} aria-hidden="true">
              <span></span><span></span><span></span><span></span>
            </span>
            <button className="skip next" onClick={() => go(1)} disabled={index === stops.length - 1}>Next →</button>
          </div>
        </div>

        <div className="essay">
          <p>{essay}</p>
          <p className="caption">{caption}.</p>
        </div>

        <div className="onward">
          <p className="eyebrow">{next ? "Onward" : "The end of the walk"}</p>
          <p>{stop.transition}</p>
        </div>

        <nav className="stopnav">
          <button onClick={() => go(-1)} disabled={index === 0}>
            <span className="dir">← Previous</span>
            {index > 0 && <span className="t">{stops[index - 1].title}</span>}
          </button>
          <button className="next" onClick={() => go(1)} disabled={!next}>
            <span className="dir">Next →</span>
            {next && <span className="t">{next.title}</span>}
          </button>
        </nav>
      </div>

      <audio
        ref={audioRef}
        onTimeUpdate={(e) => { const a = e.target; if (a.duration) setProgress(a.currentTime / a.duration); }}
        onEnded={() => { setPlaying(false); setProgress(1); }}
        hidden
      />
    </div>
  );
}
