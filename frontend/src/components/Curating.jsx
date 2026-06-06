// Brief, tasteful transition while the route is composed: a hairline path
// draws between dots, then App auto-advances to the route.
export default function Curating() {
  const dots = [10, 90, 170, 250, 350];
  return (
    <div className="curating screen">
      <p className="eyebrow">Composing your route</p>
      <h2 className="serif line">Reading the collection, and finding your path through it.</h2>
      <svg className="route-draw" viewBox="0 0 360 24" preserveAspectRatio="none" aria-hidden="true">
        <path className="path" d="M10 12 H350" pathLength="1" />
        {dots.map((cx, i) => (
          <circle
            key={cx}
            className="dot"
            cx={cx}
            cy="12"
            r="3.5"
            style={{ animationDelay: `${0.3 + i * 0.28}s` }}
          />
        ))}
      </svg>
    </div>
  );
}
