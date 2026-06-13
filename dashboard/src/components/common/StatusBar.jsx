export default function StatusBar({ phase, period, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
      <span style={{
        fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--text-muted)',
        textTransform: 'uppercase', letterSpacing: 1,
      }}>当前状态</span>
      {phase && (
        <>
          <span style={{
            background: color || 'var(--accent-gold)',
            padding: '3px 14px', borderRadius: 14, fontSize: 'var(--fs-sm)', fontWeight: 700,
            color: '#0d0d0d', letterSpacing: 0.5, boxShadow: `0 0 12px ${color || 'var(--accent-gold)'}33`,
          }}>
            {phase}
          </span>
          <span style={{
            fontSize: 'var(--fs-xs)', color: 'var(--text-muted)',
            display: 'flex', alignItems: 'center', gap: 4,
          }}>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#5bba57', display: 'inline-block' }} />
            截至 {period}
          </span>
        </>
      )}
    </div>
  );
}