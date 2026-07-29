import { useMCP } from '../../hooks/useMCP.js';

function parse(raw) {
  if (!raw) return null;
  if (typeof raw !== 'string') return raw;
  try { return JSON.parse(raw); } catch { return null; }
}

const LEGEND = [
  { c: '#4A78C4', t: '蓝·未被注意/低估' },
  { c: '#4FA86A', t: '绿·正常进行' },
  { c: '#E0913C', t: '橙·抢跑·尚有空间' },
  { c: '#E25C5C', t: '红·无补涨空间' },
];

// 把累计涨幅映射到条宽：区间 [-10%, +40%] → [0,100%]
function barWidth(chg) {
  if (chg == null) return 4;
  const w = ((chg + 0.1) / 0.5) * 100;
  return Math.max(3, Math.min(100, w));
}

/**
 * 抢跑进度条：事件(event-30交易日 → 今天)关联标的累计涨幅，按蓝/绿/橙/红着色。
 * 进度轴标记"事件日"与"今天"位置。
 */
export default function FrontrunBar({ eventId }) {
  const { data, isLoading } = useMCP('calendar_frontrun', { event_id: eventId });
  const d = parse(data);

  if (isLoading) {
    return <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', padding: '8px 0' }}>计算抢跑进度…</div>;
  }
  if (!d || d.ok === false) {
    return <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>{d?.error || '无法计算抢跑进度'}</div>;
  }
  if (!d.targets || d.targets.length === 0) {
    return (
      <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', padding: '6px 0', lineHeight: 1.6 }}>
        {d.note || '该事件未标注抢跑标的。'}
      </div>
    );
  }

  const tl = d.timeline || {};
  return (
    <div style={{ marginTop: 6 }}>
      {/* 进度轴 */}
      <div style={{ position: 'relative', height: 22, background: 'rgba(255,255,255,0.05)', borderRadius: 5, marginBottom: 10 }}>
        {tl.event_pos != null && (
          <div title={`事件日 ${tl.event}`} style={{ position: 'absolute', left: `${tl.event_pos * 100}%`, top: 0, bottom: 0, width: 2, background: 'var(--accent-gold)', transform: 'translateX(-1px)' }} />
        )}
        {tl.today_pos != null && (
          <div title={`今天 ${tl.as_of}`} style={{ position: 'absolute', left: `${tl.today_pos * 100}%`, top: -2, bottom: -2, width: 2, background: '#fff', opacity: 0.85 }} />
        )}
        <span style={{ position: 'absolute', left: `${ (tl.event_pos ?? 0) * 100 }%`, top: 23, transform: 'translateX(-50%)', fontSize: 9, color: 'var(--accent-gold)', whiteSpace: 'nowrap' }}>事件日</span>
        <span style={{ position: 'absolute', left: `${ (tl.today_pos ?? 0) * 100 }%`, bottom: 23, transform: 'translateX(-50%)', fontSize: 9, color: '#fff', whiteSpace: 'nowrap' }}>今天</span>
      </div>

      {/* 每标的抢跑条 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {d.targets.map((t) => (
          <div key={t.code} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 96, fontSize: 'var(--fs-xs)', color: 'var(--text-secondary)', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.name}</span>
            <div style={{ flex: 1, height: 12, background: 'rgba(255,255,255,0.05)', borderRadius: 3, position: 'relative', overflow: 'hidden' }}>
              <div style={{ width: `${barWidth(t.change_pct)}%`, height: '100%', background: t.color || '#4A78C4', borderRadius: 3, transition: 'width .4s ease' }} />
            </div>
            <span style={{ width: 64, textAlign: 'right', fontSize: 'var(--fs-xs)', color: t.color || 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>
              {t.change_pct == null ? '—' : `${(t.change_pct * 100).toFixed(1)}%`}
            </span>
          </div>
        ))}
      </div>

      {/* 图例 */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 10 }}>
        {LEGEND.map((l) => (
          <span key={l.t} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)' }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: l.c, display: 'inline-block' }} />{l.t}
          </span>
        ))}
      </div>
    </div>
  );
}
