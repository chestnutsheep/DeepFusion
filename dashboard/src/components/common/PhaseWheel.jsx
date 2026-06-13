export default function PhaseWheel({ phase = 0, phaseName = '', phaseField, cycleName, size = 120 }) {
  const phases = [
    { id: 1, label: '回升', color: '#D4A853' },
    { id: 2, label: '繁荣', color: '#3fb950' },
    { id: 3, label: '衰退', color: '#f85149' },
    { id: 4, label: '萧条', color: '#58a6ff' },
  ];

  const cx = size / 2, cy = size / 2, r = size / 2 - 12;
  const angles = phases.map((_, i) => ({ start: i * 90 - 45, end: (i + 1) * 90 - 45 }));
  const toRad = (deg) => (deg * Math.PI) / 180;

  function polar(cx, cy, radius, deg) {
    const rad = toRad(deg);
    return { x: cx + radius * Math.cos(rad), y: cy + radius * Math.sin(rad) };
  }

  function describeSector(startAngle, endAngle) {
    const s = polar(cx, cy, r, startAngle);
    const e = polar(cx, cy, r, endAngle);
    const midAngle = startAngle + (endAngle - startAngle) / 2;
    const m = polar(cx, cy, r - r * 0.25, midAngle);
    const label = phases[Math.floor(midAngle / 90)];
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;
    return {
      path: `M ${cx} ${cy} L ${s.x} ${s.y} A ${r} ${r} 0 ${largeArc} 1 ${e.x} ${e.y} Z`,
      labelX: m.x,
      labelY: m.y + 3,
      label: label.label,
      color: label.color,
    };
  }

  const sectors = phases.map((p, i) => describeSector(angles[i].start, angles[i].end));

  // 当前相位指示器 — 三角标记
  const indicatorAngle = -45 + (phase - 1) * 90 - 45;
  const ind = polar(cx, cy, r + 10, indicatorAngle + 45);

  const fontSize = size < 100 ? 9 : size < 140 ? 10 : 11;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flexShrink: 0 }}>
      {sectors.map((s, i) => (
        <g key={i}>
          <path d={s.path} fill={s.color} opacity={phase === i + 1 ? 0.95 : 0.2} stroke="rgba(212,168,83,0.15)" strokeWidth="0.5" />
          <text x={s.labelX} y={s.labelY} textAnchor="middle" fill="#fff" fontSize={fontSize} fontWeight={700} opacity={phase === i + 1 ? 1 : 0.4}>
            {s.label}
          </text>
        </g>
      ))}
      {/* 外环 */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(212,168,83,0.2)" strokeWidth="1" />
      {/* 当前相位箭头 */}
      {phase >= 1 && phase <= 4 && (
        <polygon
          points={`${ind.x},${ind.y - 5} ${ind.x - 4},${ind.y + 3} ${ind.x + 4},${ind.y + 3}`}
          fill="var(--accent-gold)"
          stroke="var(--accent-gold)"
          strokeWidth="0.8"
        />
      )}
      <circle cx={cx} cy={cy} r={2.5} fill="var(--accent-gold)" />
    </svg>
  );
}
