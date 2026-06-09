export default function StatusBar({ phase, period, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>当前周期状态</h2>
      {phase && (
        <>
          <span style={{ background: color || 'var(--accent-gold)', padding: '2px 12px', borderRadius: 12, fontSize: 12, fontWeight: 600, color: '#000' }}>
            {phase}
          </span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>数据截至 {period}</span>
        </>
      )}
    </div>
  );
}