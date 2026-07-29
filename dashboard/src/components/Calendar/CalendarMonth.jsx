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

  const month = useMCP('calendar_month', { year: ym.year, month: ym.month });
  const collect = useMCP('calendar_refresh_collect', null); // 禁用自动，仅手动刷新
  const md = parse(month.data);
  const events = md?.events || [];
  const updatedAt = month.updatedAt;

  // 按日期分组
  const byDate = useMemo(() => {
    const m = {};
    for (const e of events) {
      const day = e.date ? parseInt(e.date.slice(8, 10), 10) : 0;
      (m[day] = m[day] || []).push(e);
    }
    return m;
  }, [events]);

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
      {collect.data && collect.isFetched && (
        <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', marginBottom: 8 }}>
          采集结果：{collect.isSuccess ? '已完成（见下方日志）' : '失败'} {collect.data ? '' : ''}
          {(() => { const c = parse(collect.data); return c?.log ? ` · ${String(c.log).slice(-120)}` : ''; })()}
        </div>
      )}

      {/* 月历网格 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
        {WEEK.map((w) => (
          <div key={w} style={{ textAlign: 'center', fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', padding: '4px 0' }}>{w}</div>
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
                minHeight: 64, borderRadius: 6, padding: 6, cursor: evs.length ? 'pointer' : 'default',
                background: isSel ? 'rgba(201,168,97,0.14)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${isSel ? 'rgba(201,168,97,0.6)' : 'var(--border-subtle)'}`,
                display: 'flex', flexDirection: 'column', gap: 3,
              }}
            >
              <div style={{ fontSize: 'var(--fs-xs)', color: evs.length ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: isSel ? 700 : 400 }}>{d}</div>
              {evs.slice(0, 2).map((e, k) => (
                <div key={k} style={{
                  fontSize: 9, lineHeight: 1.2, color: 'var(--text-secondary)',
                  background: 'rgba(255,255,255,0.05)', borderRadius: 3, padding: '1px 4px',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  borderLeft: `2px solid ${hasHigh ? '#C07C7C' : '#C9A861'}`,
                }}>{e.name}</div>
              ))}
              {evs.length > 2 && <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>+{evs.length - 2}</div>}
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
          <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', padding: '12px 0' }}>当日暂无催化事件。</div>
        )}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 'var(--sp-md)', alignItems: 'start' }}>
          {selectedEvents.map((e) => (
            <EventCard key={e.id || e.date + e.name} e={e} updatedAt={updatedAt} onOpenDomain={setPopup} />
          ))}
        </div>
      </div>

      {popup && <DomainConstituentsPopup domain={popup.name} type={popup.type} onClose={() => setPopup(null)} />}
    </div>
  );
}

function navBtn() {
  return {
    width: 30, height: 30, borderRadius: 6, cursor: 'pointer', fontSize: 18, lineHeight: 1,
    background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)',
  };
}
