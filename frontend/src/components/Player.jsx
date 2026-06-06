import { useEffect, useRef, useState } from "react";
import { fetchAudioUrl } from "../api.js";

export default function Player({ stops, index, setIndex, hasTts, vibe, onBack }) {
  const stop = stops[index];
  const [showTranscript, setShowTranscript] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [loadingAudio, setLoadingAudio] = useState(false);
  const [progress, setProgress] = useState(0); // 0..1
  const audioRef = useRef(null);
  const audioUrlRef = useRef(null);

  // Stop any audio when the stop changes or component unmounts.
  function stopAll() {
    if (audioRef.current) {
      audioRef.current.pause();
    }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    setPlaying(false);
    setProgress(0);
  }

  useEffect(() => {
    stopAll();
    return stopAll;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  async function play() {
    if (playing) return;
    // Server TTS path
    if (hasTts) {
      setLoadingAudio(true);
      try {
        if (!audioUrlRef.current) {
          audioUrlRef.current = await fetchAudioUrl(stop.script, vibe);
        }
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
    // Browser speech-synthesis fallback
    browserSpeak();
  }

  function browserSpeak() {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(stop.script);
    u.rate = vibe === "Quick hits" ? 1.12 : 1.0;
    u.onend = () => {
      setPlaying(false);
      setProgress(1);
    };
    window.speechSynthesis.speak(u);
    setPlaying(true);
  }

  function pause() {
    if (audioRef.current && !audioRef.current.paused) audioRef.current.pause();
    if (window.speechSynthesis?.speaking) window.speechSynthesis.pause();
    setPlaying(false);
  }

  function resume() {
    if (audioRef.current?.src && audioRef.current.paused) {
      audioRef.current.play();
      setPlaying(true);
      return;
    }
    if (window.speechSynthesis?.paused) {
      window.speechSynthesis.resume();
      setPlaying(true);
      return;
    }
    play();
  }

  function go(delta) {
    const next = index + delta;
    if (next < 0 || next >= stops.length) return;
    audioUrlRef.current = null;
    setIndex(next);
  }

  return (
    <div className="screen player">
      <div className="player-top">
        <button className="link" onClick={onBack}>← Path</button>
        <span className="counter">{index + 1} / {stops.length}</span>
      </div>

      <div className="art">
        <img src={stop.imageLarge || stop.image} alt={stop.title} />
      </div>

      <div className="art-meta">
        <h1>{stop.title}</h1>
        <p className="artist">{stop.artist}{stop.date ? `, ${stop.date}` : ""}</p>
        <p className="muted">
          {stop.department}{stop.gallery ? ` · Gallery ${stop.gallery}` : ""}
        </p>
      </div>

      <div className="progress">
        <div className="bar" style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>

      <div className="controls">
        <button className="ctrl" onClick={() => go(-1)} disabled={index === 0}>⏮</button>
        <button className="ctrl big" onClick={playing ? pause : resume}>
          {loadingAudio ? "…" : playing ? "⏸" : "▶"}
        </button>
        <button className="ctrl" onClick={() => go(1)} disabled={index === stops.length - 1}>⏭</button>
      </div>

      <button className="transcript-toggle" onClick={() => setShowTranscript((v) => !v)}>
        {showTranscript ? "Hide transcript" : "Show transcript"}
      </button>
      {showTranscript && <p className="transcript">{stop.script}</p>}

      {!hasTts && (
        <p className="hint">Using your device's built-in voice. Add an ElevenLabs key for studio-quality narration.</p>
      )}

      <audio
        ref={audioRef}
        onTimeUpdate={(e) => {
          const a = e.target;
          if (a.duration) setProgress(a.currentTime / a.duration);
        }}
        onEnded={() => { setPlaying(false); setProgress(1); }}
        hidden
      />
    </div>
  );
}
