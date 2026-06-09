export default function PhaseWheel({ phase = 0, phaseName = '', phaseField, cycleName }) {
  const phases = [
    { id: 1, label: '回升期', color: '#D4A853' },
    { id: 2, label: '繁荣期', color: '#3fb950' },
    { id: 3, label: '衰退期', color: '#f85149' },
    { id: 4, label: '萧条期', color: '#58a6ff' },
  ];

  const cx = 80, cy = 80, r = 60;
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
    const m = polar(cx, cy, r - 15, midAngle);
    const label = phases[Math.floor(midAngle / 90)];
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;
    return {
      path: `M ${cx} ${cy} L ${s.x} ${s.y} A ${r} ${r} 0 ${largeArc} 1 ${e.x} ${e.y} Z`,
      labelX: m.x,
      labelY: m.y + 4,
      label: label.label,
      color: label.color,
    };
  }

  const sectors = phases.map((p, i) => describeSector(angles[i].start, angles[i].end));

  // 当前相位指示器 — 三角标记
  const indicatorAngle = -45 + (phase - 1) * 90 - 45;
  const ind = polar(cx, cy, r + 15, indicatorAngle + 45);
  const ind2 = polar(cx, cy, r + 26, indicatorAngle + 45);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, justifyContent: 'center', margin: '12px 0' }}>
      <svg width={180} height={180} viewBox="0 0 160 160">
        {sectors.map((s, i) => (
          <g key={i}>
            <path d={s.path} fill={s.color} opacity={phase === i + 1 ? 1 : 0.3} stroke="var(--border-subtle)" strokeWidth="1" />
            <text x={s.labelX} y={s.labelY} textAnchor="middle" fill="#fff" fontSize={11} fontWeight={700} opacity={phase === i + 1 ? 1 : 0.5}>
              {s.label}
            </text>
          </g>
        ))}
        {/* 外环 */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(212,168,83,0.3)" strokeWidth="1.5" />
        {/* 当前相位箭头 */}
        {phase >= 1 && phase <= 4 && (
          <polygon
            points={`${ind.x},${ind.y - 6} ${ind.x - 5},${ind.y + 4} ${ind.x + 5},${ind.y + 4}`}
            fill="var(--accent-gold)"
            stroke="var(--accent-gold)"
            strokeWidth="1"
          />
        )}
        <circle cx={cx} cy={cy} r={3} fill="var(--accent-gold)" />
      </svg>
      <div>
        <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent-gold)' }}>{phaseName || '—'}</div>
        {cycleName && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{cycleName}</div>}
      </div>
    </div>
  );
}
