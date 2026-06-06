import { useEffect, useRef, useState } from "react";
import { fetchAudioUrl, askDocent, narrate } from "../api.js";

const SUGGESTED = ["Tell me more about the artist", "What should I look for?", "Where do I go next?"];
const SR = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);

export default function Stop({ stops, index, setIndex, hasTts, hasClaude, vibe, level, themes, eras, next, onBack }) {
  const stop = stops[index];
  const [narration, setNarration] = useState(null); // { script, spoken, source }
  const [loadingNarration, setLoadingNarration] = useState(true);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [imgError, setImgError] = useState(false);
  const [thread, setThread] = useState([]); // [{role, content}]
  const [asking, setAsking] = useState(false);
  const [listening, setListening] = useState(false);
  const [draft, setDraft] = useState("");
  const audioRef = useRef(null);          // narration audio
  const answerAudioRef = useRef(null);    // Q&A answer audio
  const narrationUrlRef = useRef(null);
  const recRef = useRef(null);

  function stopVoice() {
    if (audioRef.current) audioRef.current.pause();
    if (answerAudioRef.current) answerAudioRef.current.pause();
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    setPlaying(false);
  }

  // Speak text aloud: ElevenLabs when available, else the browser voice.
  async function speak(text, { isNarration } = {}) {
    stopVoice();
    if (hasTts) {
      let url = isNarration ? narrationUrlRef.current : null;
      if (!url) {
        url = await fetchAudioUrl(text, vibe);
        if (isNarration) narrationUrlRef.current = url;
      }
      if (url) {
        const el = isNarration ? audioRef.current : answerAudioRef.current;
        el.src = url;
        try { await el.play(); if (isNarration) setPlaying(true); } catch (e) { /* autoplay blocked */ }
        return;
      }
    }
    if (window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(text);
      u.rate = vibe === "Quick hits" ? 1.12 : 1.0;
      if (isNarration) { u.onend = () => { setPlaying(false); setProgress(1); }; setPlaying(true); }
      window.speechSynthesis.speak(u);
    }
  }

  // On arriving at a stop: reset, fetch the narration, and start speaking.
  useEffect(() => {
    stopVoice();
    if (recRef.current) { try { recRef.current.abort(); } catch (e) {} }
    setNarration(null);
    setLoadingNarration(true);
    setProgress(0);
    setImgError(false);
    setThread([]);
    setDraft("");
    setAsking(false);
    setListening(false);
    narrationUrlRef.current = null;
    if (audioRef.current) audioRef.current.removeAttribute("src");

    let cancelled = false;
    (async () => {
      try {
        const n = await narrate({ stop, themes, level, vibe });
        if (cancelled) return;
        setNarration(n);
        setLoadingNarration(false);
        speak(n.spoken || n.script, { isNarration: true }); // auto-play the guide's voice
      } catch (e) {
        if (!cancelled) setLoadingNarration(false);
      }
    })();

    return () => { cancelled = true; stopVoice(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  function pause() {
    if (audioRef.current && !audioRef.current.paused) audioRef.current.pause();
    if (window.speechSynthesis?.speaking) window.speechSynthesis.pause();
    setPlaying(false);
  }
  function resume() {
    if (audioRef.current?.src && audioRef.current.paused) { audioRef.current.play(); setPlaying(true); return; }
    if (window.speechSynthesis?.paused) { window.speechSynthesis.resume(); setPlaying(true); return; }
    if (narration) speak(narration.spoken || narration.script, { isNarration: true });
  }

  function go(delta) {
    const n = index + delta;
    if (n < 0 || n >= stops.length) return;
    setIndex(n);
  }

  // --- Ask the docent, by voice ---
  async function ask(question) {
    const q = (question || "").trim();
    if (!q || asking) return;
    const history = thread;
    setThread((t) => [...t, { role: "user", content: q }]);
    setDraft("");
    setAsking(true);
    try {
      const { answer } = await askDocent({ stop, question: q, level, vibe, themes, eras, history, nextStop: next });
      setThread((t) => [...t, { role: "assistant", content: answer }]);
      speak(answer); // speak the answer aloud
    } catch (e) {
      setThread((t) => [...t, { role: "assistant", content: "Sorry — I couldn't reach the docent just now." }]);
    } finally {
      setAsking(false);
    }
  }

  function listen() {
    if (listening) { try { recRef.current?.stop(); } catch (e) {} return; }
    if (!SR) return; // no speech recognition — text box is the fallback
    stopVoice(); // don't talk over the visitor
    const rec = new SR();
    recRef.current = rec;
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = (e) => { const t = e.results[0][0].transcript; ask(t); };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    try { rec.start(); setListening(true); } catch (e) { setListening(false); }
  }

  const essay = loadingNarration ? "Composing this stop…" : (narration?.script || "");
  const caption =
    `${(narration?.source === "claude") ? "Story by Claude" : "Story from the label"}` +
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
              <img src={stop.imageLarge || stop.image} alt={stop.title} onError={() => setImgError(true)} />
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
              {loadingNarration ? "···" : playing ? "❚❚" : "▶"}
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

        <div className="ask">
          <p className="eyebrow">Ask the docent</p>
          <div className="ask-bar">
            <button className={`mic ${listening ? "live" : ""}`} onClick={listen} disabled={asking}>
              <span className="mic-dot" />
              {listening ? "Listening — tap to stop" : (SR ? "Hold a question? Tap and speak" : "Ask a question below")}
            </button>
          </div>
          <div className="chips ask-suggestions">
            {SUGGESTED.map((q) => (
              <button key={q} type="button" className="chip" onClick={() => ask(q)} disabled={asking}>{q}</button>
            ))}
          </div>

          {thread.length > 0 && (
            <div className="ask-thread">
              {thread.map((m, i) =>
                m.role === "user" ? (
                  <p key={i} className="ask-q">{m.content}</p>
                ) : (
                  <div key={i} className="ask-a">
                    <p>{m.content}</p>
                    <button className="ask-play" onClick={() => speak(m.content)}>▶ Hear again</button>
                  </div>
                )
              )}
            </div>
          )}
          {asking && <p className="ask-thinking">The docent is thinking…</p>}

          <form className="ask-form" onSubmit={(e) => { e.preventDefault(); ask(draft); }}>
            <input className="ask-input" value={draft} onChange={(e) => setDraft(e.target.value)}
              placeholder="…or type a question" disabled={asking} />
            <button className="ask-send" type="submit" disabled={asking || !draft.trim()}>Ask</button>
          </form>
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
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => { setPlaying(false); setProgress(1); }}
        hidden
      />
      <audio ref={answerAudioRef} hidden />
    </div>
  );
}
