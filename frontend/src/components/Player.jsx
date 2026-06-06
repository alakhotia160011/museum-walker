import { useEffect, useRef, useState } from "react";
import { fetchAudioUrl, askDocent } from "../api.js";

const SUGGESTED = ["Tell me more about the artist", "What should I look for?", "Where do I go next?"];

export default function Stop({ stops, index, setIndex, hasTts, hasClaude, vibe, level, themes, next, onBack }) {
  const stop = stops[index];
  const [playing, setPlaying] = useState(false);
  const [loadingAudio, setLoadingAudio] = useState(false);
  const [progress, setProgress] = useState(0);
  const [imgError, setImgError] = useState(false);
  const [thread, setThread] = useState([]); // [{role:'user'|'assistant', content}]
  const [draft, setDraft] = useState("");
  const [asking, setAsking] = useState(false);
  const audioRef = useRef(null);
  const audioUrlRef = useRef(null);
  const answerAudioRef = useRef(null);

  // The narration audio includes the spoken walking cue; the printed essay does not.
  const essay =
    stop.transition && stop.script?.endsWith(stop.transition)
      ? stop.script.slice(0, -stop.transition.length).trim()
      : stop.script;

  function stopAll() {
    if (audioRef.current) audioRef.current.pause();
    if (answerAudioRef.current) answerAudioRef.current.pause();
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    setPlaying(false);
    setProgress(0);
  }

  useEffect(() => {
    stopAll();
    setImgError(false);
    setThread([]);
    setDraft("");
    setAsking(false);
    return stopAll;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  async function ask(question) {
    const q = question.trim();
    if (!q || asking) return;
    const history = thread;
    setThread((t) => [...t, { role: "user", content: q }]);
    setDraft("");
    setAsking(true);
    try {
      const { answer } = await askDocent({ stop, question: q, level, vibe, themes, history, nextStop: next });
      setThread((t) => [...t, { role: "assistant", content: answer }]);
    } catch (e) {
      setThread((t) => [...t, { role: "assistant", content: "Sorry — I couldn't reach the docent just now. Try again in a moment." }]);
    } finally {
      setAsking(false);
    }
  }

  // Speak an answer aloud — ElevenLabs when available, else the browser voice.
  async function speakAnswer(text) {
    stopAll();
    if (hasTts) {
      const url = await fetchAudioUrl(text, vibe);
      if (url && answerAudioRef.current) {
        answerAudioRef.current.src = url;
        answerAudioRef.current.play();
        return;
      }
    }
    if (window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(text);
      u.rate = vibe === "Quick hits" ? 1.12 : 1.0;
      window.speechSynthesis.speak(u);
    }
  }

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

        <div className="ask">
          <p className="eyebrow">Ask the docent</p>
          <div className="chips ask-suggestions">
            {SUGGESTED.map((q) => (
              <button key={q} type="button" className="chip" onClick={() => ask(q)} disabled={asking}>
                {q}
              </button>
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
                    <button className="ask-play" onClick={() => speakAnswer(m.content)} aria-label="Hear this answer">
                      ▶ Hear this
                    </button>
                  </div>
                )
              )}
            </div>
          )}
          {asking && <p className="ask-thinking">The docent is thinking…</p>}

          <form
            className="ask-form"
            onSubmit={(e) => { e.preventDefault(); ask(draft); }}
          >
            <input
              className="ask-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask anything about this work…"
              disabled={asking}
            />
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
        onEnded={() => { setPlaying(false); setProgress(1); }}
        hidden
      />
      <audio ref={answerAudioRef} hidden />
    </div>
  );
}
