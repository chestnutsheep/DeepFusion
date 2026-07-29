import { useMCP } from '../../hooks/useMCP.js';
import UpdateTimestamp from '../common/UpdateTimestamp.jsx';

const TYPE_LABEL = { industry: '申万行业', concept: '概念板块', sector: '行业板块', auto: '自动识别' };

function parse(raw) {
  if (!raw) return null;
  if (typeof raw !== 'string') return raw;
  try { return JSON.parse(raw); } catch { return null; }
}

function chgColor(pct) {
  if (pct == null) return 'var(--text-muted)';
  if (pct > 0) return '#E25C5C';
  if (pct < 0) return '#4FA86A';
  return 'var(--text-secondary)';
}

/**
 * 关联领域成分股弹窗（卡片内嵌）。
 * 盘中取腾讯实时快照、收盘取最近交易日收盘；刷新按钮 re-fetch 实时数据。
 */
export default function DomainConstituentsPopup({ domain, type, onClose }) {
  const { data, isLoading, refetch, updatedAt } = useMCP('domain_constituents', { domain, type: type || 'auto', limit: 30 });
  const d = parse(data);

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(8,6,14,0.62)',
        backdropFilter: 'blur(3px)', zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(720px, 94vw)', maxHeight: '86vh', overflow: 'auto',
          background: 'var(--bg-elevated, #1a1726)', border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md, 12px)', boxShadow: '0 18px 60px rgba(0,0,0,0.5)',
          padding: 'var(--sp-lg, 18px)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
          <div>
            <div style={{ fontSize: 'var(--fs-md)', fontWeight: 700, color: 'var(--text-primary)' }}>
              {domain} <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--accent-gold)' }}>· {TYPE_LABEL[type] || '关联领域'}</span>
            </div>
            <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', marginTop: 4, display: 'flex', gap: 8, alignItems: 'center' }}>
              {d?.mode && <span style={{ color: d.mode === '盘中实时' ? '#8FD6FF' : 'var(--text-secondary)' }}>{d.mode}</span>}
              {updatedAt && <UpdateTimestamp updatedAt={updatedAt} />}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={() => refetch()}
              style={{ fontSize: 'var(--fs-xs)', padding: '5px 12px', borderRadius: 6, cursor: 'pointer',
                background: 'rgba(201,168,97,0.15)', border: '1px solid rgba(201,168,97,0.5)', color: 'var(--accent-gold)' }}
            >刷新行情</button>
            <button
              onClick={onClose}
              style={{ fontSize: 'var(--fs-xs)', padding: '5px 12px', borderRadius: 6, cursor: 'pointer',
                background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}
            >关闭</button>
          </div>
        </div>

        {isLoading && <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', padding: '20px 0' }}>加载成分股…</div>}
        {!isLoading && d && d.ok === false && (
          <div style={{ fontSize: 'var(--fs-sm)', color: '#C07C7C', padding: '20px 0' }}>{d.error || '未解析到成分股'}</div>
        )}
        {!isLoading && d?.ok && (
          <>
            <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', marginBottom: 8 }}>
              共 {d.count} 只成分股 · 点击刷新按钮获取盘中实时快照
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 0.9fr 0.8fr 0.8fr 0.6fr 0.6fr', gap: '6px 10px', fontSize: 'var(--fs-xs)' }}>
              <div style={th()}>名称 / 代码</div>
              <div style={th('right')}>最新价</div>
              <div style={th('right')}>涨跌幅</div>
              <div style={th('right')}>换手%</div>
              <div style={th('right')}>PE</div>
              <div style={th('right')}>PB</div>
              {(d.constituents || []).map((c) => (
                <FragmentRow key={c.code} c={c} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function th(align = 'left') {
  return {
    fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', fontWeight: 600,
    textAlign: align, paddingBottom: 4, borderBottom: '1px solid var(--border-subtle)',
  };
}

function FragmentRow({ c }) {
  return (
    <>
      <div style={{ color: 'var(--text-primary)', padding: '5px 0' }}>
        {c.name} <span style={{ color: 'var(--text-muted)', fontSize: 'var(--fs-2xs)' }}>{c.code}</span>
      </div>
      <div style={{ textAlign: 'right', color: 'var(--text-secondary)', padding: '5px 0', fontVariantNumeric: 'tabular-nums' }}>{c.price ?? '—'}</div>
      <div style={{ textAlign: 'right', color: chgColor(c.change_pct), padding: '5px 0', fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
        {c.change_pct == null ? '—' : `${c.change_pct > 0 ? '+' : ''}${c.change_pct.toFixed(2)}%`}
      </div>
      <div style={{ textAlign: 'right', color: 'var(--text-secondary)', padding: '5px 0', fontVariantNumeric: 'tabular-nums' }}>{c.turnover ?? '—'}</div>
      <div style={{ textAlign: 'right', color: 'var(--text-secondary)', padding: '5px 0', fontVariantNumeric: 'tabular-nums' }}>{c.pe ?? '—'}</div>
      <div style={{ textAlign: 'right', color: 'var(--text-secondary)', padding: '5px 0', fontVariantNumeric: 'tabular-nums' }}>{c.pb ?? '—'}</div>
    </>
  );
}
