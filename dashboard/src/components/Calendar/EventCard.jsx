import CardWrapper from '../common/CardWrapper.jsx';
import UpdateTimestamp from '../common/UpdateTimestamp.jsx';
import FrontrunBar from './FrontrunBar.jsx';

function chip(color) {
  return {
    fontSize: 'var(--fs-2xs)', padding: '2px 8px', borderRadius: 4,
    background: `${color}1A`, border: `1px solid ${color}55`, color, whiteSpace: 'nowrap', cursor: 'pointer',
  };
}

const DOMAIN_COLOR = { industry: '#9C82B4', concept: '#5AA9C9', sector: '#C9A861', auto: '#8A8AA0' };

/**
 * 单条事件卡：关联领域标签(可点击弹成分股) + 抢跑进度条 + 时间戳。
 * onOpenDomain({name, type}) → 父组件打开 DomainConstituentsPopup。
 */
export default function EventCard({ e, updatedAt, onOpenDomain }) {
  const stars = '★'.repeat(e.rating || 0);
  const dateStr = e.date ? e.date.slice(5) : '';
  const domains = e.domains || [];
  return (
    <CardWrapper hoverable style={{
      border: e.bury_window ? '1px solid rgba(192,124,124,0.6)' : '1px solid var(--border-subtle)',
      background: e.bury_window ? 'linear-gradient(160deg, rgba(192,124,124,0.12), rgba(26,23,38,0.4))' : undefined,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>{dateStr}</span>
        <span style={{ color: '#C9A861', fontSize: 'var(--fs-sm)', letterSpacing: 1 }}>{stars}</span>
      </div>
      <div style={{ fontSize: 'var(--fs-md)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6, lineHeight: 1.35 }}>
        {e.name}
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
        {e.category && <span style={chip('#6FA088')}>{e.category}</span>}
        {e.sentiment && e.sentiment !== '中性' && (
          <span style={chip(e.sentiment === '利好' ? '#5BAE7A' : '#C0584F')}>{e.sentiment}</span>
        )}
      </div>

      {e.note && (
        <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-secondary)', margin: '8px 0', lineHeight: 1.5 }}>{e.note}</div>
      )}

      {/* 关联领域标签（点击弹成分股） */}
      {domains.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', marginBottom: 4 }}>可能催化的领域（点击看成分股）</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {domains.map((dm, i) => (
              <span
                key={i}
                onClick={() => onOpenDomain({ name: dm.name, type: dm.type || 'auto' })}
                style={chip(DOMAIN_COLOR[dm.type] || '#8A8AA0')}
                title="点击查看关联领域成分股（实时/收盘）"
              >
                {dm.name} ›
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 抢跑进度条 */}
      <div style={{ marginTop: 10 }}>
        <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', marginBottom: 4 }}>抢跑进度（事件前30交易日 → 今天）</div>
        <FrontrunBar eventId={e.id} />
      </div>

      <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
        {updatedAt && <UpdateTimestamp updatedAt={updatedAt} compact />}
      </div>
    </CardWrapper>
  );
}
