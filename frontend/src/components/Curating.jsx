import { useEffect, useRef, useState } from "react";

// A tiny monochrome endless-runner to play while the route is composed.
// Tap / click / space to hop over the pedestals.
function RunnerGame() {
  const canvasRef = useRef(null);
  const [over, setOver] = useState(false);
  const [score, setScore] = useState(0);
  const stateRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const W = canvas.clientWidth;
    const H = 150;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.scale(dpr, dpr);

    const INK = "#15120E", PAPER = "#F4EFE7", MUTE = "#857C6C";
    const GROUND = H - 26;

    function reset() {
      stateRef.current = {
        y: GROUND, vy: 0, onGround: true,
        obstacles: [], spawn: 0, speed: 3.0, dist: 0, dead: false, raf: 0,
      };
      setOver(false);
      setScore(0);
    }
    reset();

    function jump() {
      const s = stateRef.current;
      if (s.dead) { reset(); loop(); return; }
      if (s.onGround) { s.vy = -9.2; s.onGround = false; }
    }

    function loop() {
      const s = stateRef.current;
      // physics
      s.vy += 0.55;
      s.y += s.vy;
      if (s.y >= GROUND) { s.y = GROUND; s.vy = 0; s.onGround = true; }

      s.dist += s.speed;
      s.speed = 3.0 + s.dist / 2200;
      s.spawn -= s.speed;
      if (s.spawn <= 0) {
        const h = 18 + Math.floor((s.dist % 3) * 7) + (s.obstacles.length % 2) * 6;
        s.obstacles.push({ x: W + 10, w: 12, h });
        s.spawn = 230 + (s.dist % 90); // deterministic-ish spacing
      }
      s.obstacles.forEach((o) => (o.x -= s.speed));
      s.obstacles = s.obstacles.filter((o) => o.x + o.w > -10);

      // collision (player box ~22x22 at x=44)
      const px = 44, pw = 22, ph = 22, pyTop = s.y - ph;
      for (const o of s.obstacles) {
        if (px + pw > o.x && px < o.x + o.w && pyTop + ph > GROUND - o.h) {
          s.dead = true;
          break;
        }
      }

      // draw
      ctx.clearRect(0, 0, W, H);
      ctx.strokeStyle = MUTE;
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(0, GROUND + 1); ctx.lineTo(W, GROUND + 1); ctx.stroke();
      // visitor (a little figure)
      ctx.fillStyle = INK;
      ctx.fillRect(px, s.y - ph, pw, ph);          // body
      ctx.fillStyle = PAPER;
      ctx.fillRect(px + 6, s.y - ph + 5, 4, 4);     // a small "window" so it reads as a figure
      // pedestals
      ctx.fillStyle = INK;
      s.obstacles.forEach((o) => ctx.fillRect(o.x, GROUND - o.h, o.w, o.h));

      setScore(Math.floor(s.dist / 30));
      if (s.dead) { setOver(true); return; }
      s.raf = requestAnimationFrame(loop);
    }

    function onKey(e) { if (e.code === "Space") { e.preventDefault(); jump(); } }
    canvas.addEventListener("pointerdown", jump);
    window.addEventListener("keydown", onKey);
    loop();
    return () => {
      cancelAnimationFrame(stateRef.current?.raf);
      canvas.removeEventListener("pointerdown", jump);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  return (
    <div className="game">
      <canvas ref={canvasRef} className="game-canvas" />
      <p className="game-hint">
        {over ? "Tap to play again" : "Tap or press space to hop"} · {score}
      </p>
    </div>
  );
}

export default function Curating({ ready, onEnter }) {
  return (
    <div className="curating screen">
      <p className="eyebrow">{ready ? "Your walk is ready" : "Composing your route"}</p>
      <h2 className="serif line">
        {ready ? "Step inside whenever you're ready." : "Reading the collection, and finding your path through it."}
      </h2>

      <RunnerGame />

      <button className="cta enter" disabled={!ready} onClick={onEnter}>
        {ready ? "Enter the museum →" : "Composing…"}
      </button>
    </div>
  );
}
