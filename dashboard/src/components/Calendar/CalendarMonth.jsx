import { useState, useMemo } from 'react';
import { useMCP } from '../../hooks/useMCP.js';
import EventCard from './EventCard.jsx';
import DomainConstituentsPopup from './DomainConstituentsPopup.jsx';

function parse(raw) {
  if (!raw) return null;
  if (typeof raw !== 'string') return raw;
  try { return JSON.parse(raw); } catch { return null; }
}

const WEEK = ['一', '二', '三', '四', '五', '六', '日'];

/**
 * 大事日历月历：
 * - 月历网格，点击某天展开当日事件卡
 * - 事件卡关联领域标签 → 内嵌成分股弹窗（实时/收盘）
 * - 抢跑进度条（蓝/绿/橙/红）
 * - 刷新采集按钮 → 触发 scripts/calendar_collect.py 自动采集
 */
export default function CalendarMonth() {
  const now = new Date();
  const [ym, setYm] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 });
  const [selected, setSelected] = useState(now.getDate());
  const [popup, setPopup] = useState(null); // {name, type}
  const [view, setView] = useState('month'); // month | gantt

  const month = useMCP('calendar_month', { year: ym.year, month: ym.month });
  const collect = useMCP('calendar_refresh_collect', null); // 禁用自动，仅手动刷新
  const md = parse(month.data);
  const events = md?.events || [];
  const updatedAt = month.updatedAt;

  // 筛选：利空/利好方向 + 事件类型
  const [sentFilter, setSentFilter] = useState('全部');
  const [catFilter, setCatFilter] = useState('全部');

  const categories = useMemo(() => {
    const s = new Set();
    for (const e of events) if (e.category) s.add(e.category);
    return ['全部', ...Array.from(s).sort()];
  }, [events]);

  const sentCounts = useMemo(() => {
    const c = { 利好: 0, 利空: 0, 中性: 0 };
    for (const e of events) c[e.sentiment || '中性'] = (c[e.sentiment || '中性'] || 0) + 1;
    return c;
  }, [events]);

  const displayEvents = useMemo(() => {
    return events.filter((e) => {
      if (sentFilter !== '全部' && (e.sentiment || '中性') !== sentFilter) return false;
      if (catFilter !== '全部' && (e.category || '') !== catFilter) return false;
      return true;
    });
  }, [events, sentFilter, catFilter]);

  // 按日期分组
  const byDate = useMemo(() => {
    const m = {};
    for (const e of displayEvents) {
      const day = e.date ? parseInt(e.date.slice(8, 10), 10) : 0;
      (m[day] = m[day] || []).push(e);
    }
    return m;
  }, [displayEvents]);

  const daysInMonth = new Date(ym.year, ym.month, 0).getDate();
  const firstJsDay = new Date(ym.year, ym.month - 1, 1).getDay(); // 0=Sun
  const lead = (firstJsDay + 6) % 7; // Mon-first offset
  const cells = [];
  for (let i = 0; i < lead; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const selectedEvents = byDate[selected] || [];
  const todayStr = `${ym.year}-${String(ym.month).padStart(2, '0')}-${String(selected).padStart(2, '0')}`;

  const prev = () => setYm((p) => p.month === 1 ? { year: p.year - 1, month: 12 } : { ...p, month: p.month - 1 });
  const next = () => setYm((p) => p.month === 12 ? { year: p.year + 1, month: 1 } : { ...p, month: p.month + 1 });

  const onRefresh = async () => {
    await collect.refetch();
    month.refetch();
  };

  return (
    <div>
      {/* 头部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button onClick={prev} style={navBtn()}>‹</button>
          <span style={{ fontSize: 'var(--fs-md)', fontWeight: 700, color: 'var(--text-primary)', minWidth: 120, textAlign: 'center' }}>
            {ym.year}年{ym.month}月
          </span>
          <button onClick={next} style={navBtn()}>›</button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* 月历 / 甘特 滑动切换 */}
          <div style={{ display: 'inline-flex', background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border-subtle)', borderRadius: 999, padding: 2 }}>
            {[['month', '月历'], ['gantt', '甘特图']].map(([k, label]) => (
              <button key={k} onClick={() => setView(k)} style={{
                fontSize: 'var(--fs-xs)', padding: '5px 14px', borderRadius: 999, cursor: 'pointer', border: 'none',
                background: view === k ? 'var(--accent-gold)' : 'transparent',
                color: view === k ? '#0b0b0f' : 'var(--text-secondary)', fontWeight: view === k ? 700 : 400,
                transition: 'all .18s',
              }}>{label}</button>
            ))}
          </div>
          <button
            onClick={onRefresh}
            disabled={collect.isFetching}
            style={{ fontSize: 'var(--fs-xs)', padding: '6px 14px', borderRadius: 6, cursor: 'pointer',
              background: 'rgba(201,168,97,0.15)', border: '1px solid rgba(201,168,97,0.5)', color: 'var(--accent-gold)',
              opacity: collect.isFetching ? 0.6 : 1 }}
          >
            {collect.isFetching ? '采集中…' : '↻ 刷新采集'}
          </button>
        </div>
      </div>
      {collect.data && collect.isFetched && (
        <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', marginBottom: 8 }}>
          采集结果：{collect.isSuccess ? '已完成（见下方日志）' : '失败'} {collect.data ? '' : ''}
          {(() => { const c = parse(collect.data); return c?.log ? ` · ${String(c.log).slice(-120)}` : ''; })()}
        </div>
      )}

      {/* 筛选：利空/利好方向 + 事件类型 */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>方向</span>
        {['全部', '利好', '利空', '中性'].map((s) => (
          <FilterChip key={s} label={s} active={sentFilter === s} onClick={() => setSentFilter(s)}
            color={s === '利好' ? '#5BAE7A' : s === '利空' ? '#C0584F' : undefined} />
        ))}
        <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', marginLeft: 4 }}>类型</span>
        <select value={catFilter} onChange={(e) => setCatFilter(e.target.value)} style={selectStyle()}>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <span style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', marginLeft: 'auto' }}>
          全月 {sentCounts.利好} 利好 · {sentCounts.利空} 利空 · {sentCounts.中性} 中性
        </span>
      </div>

      {view === 'month' ? (
        <>
      {/* 月历网格 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
        {WEEK.map((w) => (
          <div key={w} style={{ textAlign: 'center', fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', padding: '4px 0' }}>{w}</div>
        ))}
        {cells.map((d, i) => {
          if (d == null) return <div key={`b${i}`} />;
          const evs = byDate[d] || [];
          const isSel = d === selected;
          const hasHigh = evs.some((e) => (e.rating || 0) >= 4);
          return (
            <div
              key={d}
              onClick={() => setSelected(d)}
              style={{
                minHeight: 76, borderRadius: 6, padding: 6, cursor: evs.length ? 'pointer' : 'default',
                background: isSel ? 'rgba(201,168,97,0.14)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${isSel ? 'rgba(201,168,97,0.6)' : 'var(--border-subtle)'}`,
                display: 'flex', flexDirection: 'column', gap: 4,
              }}
            >
              <div style={{ fontSize: 'var(--fs-sm)', color: evs.length ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: isSel ? 700 : 400 }}>{d}</div>
              {evs.slice(0, 2).map((e, k) => {
                const sentColor = e.sentiment === '利好' ? '#5BAE7A'
                  : e.sentiment === '利空' ? '#C0584F' : '#C9A861';
                return (
                <div key={k} style={{
                  fontSize: 'var(--fs-xs)', lineHeight: 1.25, color: 'var(--text-secondary)',
                  background: 'rgba(255,255,255,0.05)', borderRadius: 3, padding: '2px 5px',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  borderLeft: `2px solid ${sentColor}`,
                }}>{e.name}</div>
                );
              })}
              {evs.length > 2 && <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>+{evs.length - 2}</div>}
            </div>
          );
        })}
      </div>

      {/* 选中日事件面板 */}
      <div style={{ marginTop: 14 }}>
        <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', marginBottom: 8 }}>
          {todayStr} · 共 {selectedEvents.length} 个事件
        </div>
        {month.isLoading && <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>加载中…</div>}
        {!month.isLoading && selectedEvents.length === 0 && (
          <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', padding: '12px 0' }}>
            {sentFilter !== '全部' || catFilter !== '全部' ? '当前筛选下当日无匹配事件。' : '当日暂无催化事件。'}
          </div>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 'var(--sp-md)', alignItems: 'start' }}>
          {selectedEvents.map((e) => (
            <EventCard key={e.id || e.date + e.name} e={e} updatedAt={updatedAt} onOpenDomain={setPopup} />
          ))}
        </div>
      </div>
        </>
      ) : (
        <GanttView events={displayEvents} ym={ym} daysInMonth={daysInMonth} />
      )}

      {popup && <DomainConstituentsPopup domain={popup.name} type={popup.type} onClose={() => setPopup(null)} />}
    </div>
  );
}

/**
 * 甘特图视图：纵轴=事件（按类型分组），横轴=当月日期。
 * 事件条按其 date 定位到对应日列；有 summary/theme 拆解的标注亮色。
 */
function GanttView({ events, ym, daysInMonth }) {
  const months = ['全部', ...Array.from(new Set(events.map((e) => e.category).filter(Boolean))).sort()];
  const [cat, setCat] = useState('全部');
  const filtered = cat === '全部' ? events : events.filter((e) => e.category === cat);
  const sentColor = (s) => s === '利好' ? '#5BAE7A' : s === '利空' ? '#C0584F' : '#C9A861';

  // 按周行渲染：每 7 天一行，便于横向定位
  const weeks = Math.ceil(daysInMonth / 7);
  const today = new Date();
  const isCurMonth = today.getFullYear() === ym.year && (today.getMonth() + 1) === ym.month;

  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>类型</span>
        {months.slice(0, 12).map((c) => (
          <button key={c} onClick={() => setCat(c)} style={{
            fontSize: 'var(--fs-xs)', padding: '4px 11px', borderRadius: 999, cursor: 'pointer', border: '1px solid var(--border-subtle)',
            background: cat === c ? 'var(--accent-gold)' : 'rgba(255,255,255,0.04)',
            color: cat === c ? '#0b0b0f' : 'var(--text-secondary)', fontWeight: cat === c ? 700 : 400,
          }}>{c}</button>
        ))}
        <span style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', marginLeft: 'auto' }}>横轴=当月日期 · 条=事件催化时点</span>
      </div>

      {/* 日期刻度 */}
      <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: 8, marginBottom: 4 }}>
        <div />
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${daysInMonth}, 1fr)`, gap: 2 }}>
          {Array.from({ length: daysInMonth }, (_, i) => i + 1).map((d) => {
            const dim = isCurMonth && d < today.getDate();
            return (
              <div key={d} style={{ fontSize: 'var(--fs-2xs)', color: dim ? 'var(--text-muted)' : 'var(--text-secondary)', textAlign: 'center' }}>{d}</div>
            );
          })}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 3, maxHeight: 460, overflowY: 'auto' }}>
        {filtered.length === 0 && <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', padding: '10px 0' }}>当前类型无事件。</div>}
        {filtered.map((e, idx) => {
          const d = e.date ? parseInt(e.date.slice(8, 10), 10) : 1;
          const col = Math.min(Math.max(d, 1), daysInMonth);
          return (
            <div key={e.id || idx} style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: 8, alignItems: 'center' }}>
              <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={e.name}>
                <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 2, background: sentColor(e.sentiment), marginRight: 6 }} />
                {e.name}
              </div>
              <div style={{ position: 'relative', height: 22, background: 'rgba(255,255,255,0.025)', borderRadius: 4 }}>
                <div
                  title={`${e.name} · ${e.date} · ${e.sentiment||'中性'}${e.summary ? ' · ' + e.summary.slice(0,40) : ''}`}
                  style={{
                    position: 'absolute', left: `calc(${(col - 1) / daysInMonth * 100}% )`,
                    width: `calc(${1 / daysInMonth * 100}% + 2px)`,
                    top: 3, height: 16, borderRadius: 4, cursor: 'pointer',
                    background: sentColor(e.sentiment),
                    boxShadow: e.summary ? '0 0 0 1px rgba(255,255,255,0.25)' : 'none',
                    opacity: e.summary ? 1 : 0.7,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function navBtn() {
  return {
    width: 30, height: 30, borderRadius: 6, cursor: 'pointer', fontSize: 18, lineHeight: 1,
    background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)',
  };
}

function FilterChip({ label, active, onClick, color }) {
  const activeStyle = color
    ? { background: color, borderColor: color, color: '#0b0b0f', fontWeight: 700 }
    : { background: 'var(--accent-gold)', borderColor: 'var(--accent-gold)', color: '#0b0b0f', fontWeight: 700 };
  return (
    <button onClick={onClick} style={{
      fontSize: 'var(--fs-xs)', padding: '4px 11px', borderRadius: 999, cursor: 'pointer',
      border: '1px solid var(--border-subtle)', transition: 'all .15s',
      ...(active ? activeStyle : { background: 'rgba(255,255,255,0.04)', color: 'var(--text-secondary)' }),
    }}>{label}</button>
  );
}

function selectStyle() {
  return { fontSize: 'var(--fs-xs)', padding: '5px 10px', borderRadius: 8, cursor: 'pointer',
    background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' };
}
