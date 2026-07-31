import React, {useEffect, useState} from 'react';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {useMCP} from '../../hooks/useMCP.js';
import {useAppStore} from '../../store/index.js';
import {mcp} from '../../services/mcp.js';
import CardWrapper from '../common/CardWrapper.jsx';
import UpdateTimestamp from '../common/UpdateTimestamp.jsx';
import '../../styles/policy-dashboard.css';

// ── 月份名称 ──
const MONTH_NAMES = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

// ── 从 timeline JSON 解析 ──
function parseTimeline(raw) {
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export default function PolicyDashboard() {
  const [favorites, setFavorites] = useState(() => {
    const saved = localStorage.getItem('policyFavorites');
    return saved ? new Set(JSON.parse(saved)) : new Set();
  });
  const [hoverCard, setHoverCard] = useState({ show: false, x: 0, y: 0, policy: null, keywords: [] });
  const [timelineYear, setTimelineYear] = useState(new Date().getFullYear());
  const activePolicySub = useAppStore((s) => s.activePolicySub);

  // ── 动态数据源 ──
  const stats = useMCP('policy_stats');
  const timeline = useMCP('policy_timeline', { year: timelineYear });
  const search = useMCP('policy_search', { limit: 30, year: timelineYear });

  // ── 刷新（触发后端采集） ──
  const queryClient = useQueryClient();
  const collectMutation = useMutation({
    mutationFn: () => mcp.policy.collect(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['policy_stats'] });
      queryClient.invalidateQueries({ queryKey: ['policy_timeline'] });
      queryClient.invalidateQueries({ queryKey: ['policy_search'] });
    },
  });

  const tl = parseTimeline(timeline.data);
  const realStats = stats.data || '';
  const realDocs = (search.data || '').split('\n').slice(1).filter(Boolean);

  // ── 十五五进度 ──
  const now = new Date();
  const planStart = tl ? new Date(tl.five_year.start, 0, 1) : new Date(2026, 0, 1);
  const planEnd = tl ? new Date(tl.five_year.end, 11, 31) : new Date(2030, 11, 31);
  const totalDays = (planEnd - planStart) / (1000 * 60 * 60 * 24);
  const elapsedDays = (now - planStart) / (1000 * 60 * 60 * 24);
  const progress = Math.max(0, Math.min(100, (elapsedDays / totalDays) * 100));
  const remainingMs = planEnd - now;
  const rDays = Math.floor(remainingMs / (1000 * 60 * 60 * 24));
  const rYears = Math.floor(rDays / 365);
  const rMonths = Math.floor((rDays % 365) / 30);
  const rFinalDays = rDays % 30;

  const stageName = tl?.five_year?.stage || '';

  // ── 距离下个重要政策发布日的倒数 ──
  // 从当前月份及未来月份（同一年内）找有政策文件的第一个月份
  const upcomingPolicy = (() => {
    if (!tl?.months) return null;
    const curMonth = now.getMonth();
    const curYear = now.getFullYear();
    for (let mIdx = curMonth; mIdx < 12; mIdx++) {
      const monthData = tl.months[mIdx];
      if (monthData && monthData.count > 0 && monthData.items && monthData.items.length > 0) {
        const item = monthData.items[0];
        const targetDate = new Date(curYear, mIdx, 15); // 月中作为预计发布日
        const diffDays = Math.ceil((targetDate - now) / (1000 * 60 * 60 * 24));
        return {
          title: item.title,
          dept: item.org,
          date: targetDate,
          diffDays: Math.max(0, diffDays),
          monthIdx: mIdx,
        };
      }
    }
    return null;
  })();

  useEffect(() => {
    localStorage.setItem('policyFavorites', JSON.stringify([...favorites]));
  }, [favorites]);

  const toggleFav = (e, key) => {
    e.stopPropagation();
    setFavorites(prev => {
      const n = new Set(prev);
      n.has(key) ? n.delete(key) : n.add(key);
      return n;
    });
  };

  // ── 悬浮卡片 ──
  const showHover = (e, policy, keywords) => {
    setHoverCard({ show: true, x: e.clientX + 12, y: e.clientY - 16, policy, keywords: keywords || [] });
  };
  const moveHover = (e) => { if (hoverCard.show) setHoverCard(p => ({ ...p, x: e.clientX + 12, y: e.clientY - 16 })); };
  const hideHover = () => setHoverCard(p => ({ ...p, show: false }));

  // ── 月度节点渲染（从真实数据动态生成） ──
  const renderMonthNode = (monthIdx) => {
    const monthData = tl?.months?.[monthIdx];
    const isQuarter = [2, 5, 8, 11].includes(monthIdx);
    const hasData = monthData && monthData.count > 0;

    // 无数据月份 — 小刻度
    if (!hasData) {
      return (
        <div key={`e-${monthIdx}`} className="timeline-node" style={{ left: `${(monthIdx / 11) * 100}%` }}>
          {isQuarter ? (
            <div className="node-dot" style={{ width: 10, height: 10, borderStyle: 'dashed' }} />
          ) : (
            <div style={{ width: 3, height: 3, borderRadius: '50%', background: 'var(--text-muted)', opacity: 0.3 }} />
          )}
        </div>
      );
    }

    // 计算重要度：基于文件数量 + 关键词丰富度
    const topKeywords = monthData.items?.[0]?.keywords || [];
    const importance = monthData.count >= 5 ? 5 : monthData.count >= 3 ? 4 : 3;
    const isCompleted = monthIdx < now.getMonth();
    const isCurrent = monthIdx === now.getMonth();
    const favKey = `m${monthIdx}`;
    const isFav = favorites.has(favKey);

    let cls = `node-dot importance-${importance}`;
    if (isCompleted) cls += ' completed';
    if (isCurrent) cls += ' current';
    if (isFav) cls += ' favorite';

    // 悬浮信息
    const hoverPolicy = {
      tag: `${monthData.count}篇政策`,
      title: monthData.items?.[0]?.title || MONTH_NAMES[monthIdx],
      time: MONTH_NAMES[monthIdx],
      dept: monthData.items?.[0]?.org || '',
      content: monthData.items?.map(i => i.title).join('；'),
      impact: topKeywords.join(' · '),
    };

    // 非季度月份 — 只有圆
    if (!isQuarter) {
      return (
        <div key={favKey} className="timeline-node" style={{ left: `${(monthIdx / 11) * 100}%` }}
          onMouseEnter={(e) => showHover(e, hoverPolicy, topKeywords)} onMouseMove={moveHover} onMouseLeave={hideHover}>
          <div className={cls} onClick={(e) => toggleFav(e, favKey)}>
            {isFav && <span className="favorite-star">★</span>}
          </div>
        </div>
      );
    }

    // 季度点 — 大圆 + 月份标签
    return (
      <div key={favKey} className="timeline-node" style={{ left: `${(monthIdx / 11) * 100}%` }}
        onMouseEnter={(e) => showHover(e, hoverPolicy, topKeywords)} onMouseMove={moveHover} onMouseLeave={hideHover}>
        <div className={cls} onClick={(e) => toggleFav(e, favKey)}>
          {isFav && <span className="favorite-star">★</span>}
        </div>
        <div className="node-label" style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)' }}>
          {String(monthIdx + 1).padStart(2, '0')}
        </div>
      </div>
    );
  };

  return (
    <div className="policy-dashboard-container" onMouseMove={moveHover}>
      {/* ── 顶部卡片 ── */}
      {activePolicySub === 'stats' && (
      <div className="top-cards">
        {/* 合并卡：十五五规划进度（百分比 + 进度条） — 加宽 */}
        <div className="card progress-card" style={{ flex: '1.6', minWidth: 320 }}>
          <h3>📊 十五五规划{stageName ? ` · ${stageName}` : ''}</h3>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 44, fontWeight: 800, color: 'var(--primary)', lineHeight: 1 }}>{progress.toFixed(1)}%</span>
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              剩余 <span className="highlight-text" style={{ fontWeight: 700 }}>{rYears}年{rMonths}月{rFinalDays}天</span>
            </span>
          </div>
          <div className="progress-bar"><div className="progress-fill" style={{ width: `${progress}%` }}></div></div>
          <div className="progress-info">
            <span>{tl?.five_year?.start || '2026'} → {tl?.five_year?.end || '2030'}</span>
            <span>已过 {elapsedDays.toFixed(0)}天 / 共 {totalDays.toFixed(0)}天</span>
          </div>
        </div>

        {/* 新增卡：距离下个重要政策发布日倒数 */}
        <div className="card countdown-card" style={{ flex: 1, minWidth: 240 }}>
          <h3>⏰ 下个政策发布</h3>
          {upcomingPolicy ? (
            <>
              <div className="countdown-days" style={{ fontSize: 56, fontWeight: 800, color: 'var(--secondary)', lineHeight: 1, margin: '4px 0 8px' }}>
                {upcomingPolicy.diffDays}<span style={{ fontSize: 18, marginLeft: 4, color: 'var(--text-muted)' }}>天</span>
              </div>
              <div className="card-subtitle" style={{ marginBottom: 6, fontWeight: 600, color: 'var(--text)' }}>
                {upcomingPolicy.title.length > 28 ? upcomingPolicy.title.slice(0, 28) + '…' : upcomingPolicy.title}
              </div>
              <div className="card-desc" style={{ fontStyle: 'normal' }}>
                {upcomingPolicy.date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })}
                {upcomingPolicy.dept ? ` · ${upcomingPolicy.dept}` : ''}
              </div>
            </>
          ) : (
            <>
              <div className="countdown-days" style={{ fontSize: 32, color: 'var(--text-muted)', margin: '12px 0' }}>—</div>
              <div className="card-subtitle">暂无即将发布的政策</div>
            </>
          )}
        </div>

        {/* 政策文件库 */}
        <div className="card" style={{ flex: 1, minWidth: 240 }}>
          <h3 style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>📂 政策文件库</span>
            <button
              onClick={() => collectMutation.mutate()}
              disabled={collectMutation.isPending}
              style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 4, cursor: 'pointer',
                background: 'var(--primary)', color: '#fff', border: 'none', opacity: collectMutation.isPending ? 0.6 : 1,
              }}
            >
              {collectMutation.isPending ? '采集中…' : '🔄 刷新'}
            </button>
          </h3>
          <div className="favorites-count">{realStats.match(/\d+/)?.[0] || '—'}</div>
          <div className="card-subtitle">篇 · 已收藏 {favorites.size} 篇</div>
          {realStats.split('\n').slice(1, 3).map((l, i) => <div key={i} className="card-desc">{l}</div>)}
          <div className="card-desc" style={{ marginTop: 4 }}>
            <UpdateTimestamp updatedAt={stats.updatedAt} compact />
          </div>
          {collectMutation.isError && (
            <div className="card-desc" style={{ color: 'var(--secondary)' }}>采集失败</div>
          )}
        </div>
      </div>
      )}

      {/* ── 年度政策时间线 — 数据驱动 ── */}
      {activePolicySub === 'stats' && (
      <div className="timeline-section">
        <div className="year-label">📋 {timelineYear} 年政策时间线</div>
        <div className="annual-timeline">
          <button className="year-arrow left" onClick={() => setTimelineYear(y => y - 1)}>◀</button>
          <div className="timeline-track">
            <div className="timeline-line"></div>
            <div className="timeline-nodes">
              {MONTH_NAMES.map((_, i) => renderMonthNode(i))}
            </div>
          </div>
          <button className="year-arrow right" onClick={() => setTimelineYear(y => y + 1)}>▶</button>
        </div>
        <div className="importance-legend">
          <div className="legend-item"><div className="legend-dot importance-5"></div><span>≥5篇</span></div>
          <div className="legend-item"><div className="legend-dot importance-4"></div><span>3-4篇</span></div>
          <div className="legend-item"><div className="legend-dot importance-3"></div><span>1-2篇</span></div>
          <div className="legend-item"><div className="legend-dot favorite"></div><span>★ 收藏</span></div>
        </div>
      </div>
      )}

      {/* ── 长周期战略节点 — 从后端配置读取 ── */}
      {activePolicySub === 'stats' && (
      <div className="timeline-section">
        <h2 className="section-title">🔭 长周期战略节点（2025-2030）</h2>
        <div className="long-cycle-timeline">
          <div className="long-cycle-line"></div>
          <div className="long-cycle-nodes">
            {(tl?.long_cycle || []).map((node) => {
              const cls = 'long-cycle-dot' + (node.is_major ? ' major' : ' minor');
              return (
                <div key={node.year} className="long-cycle-node">
                  <div className={cls}><span>{node.is_major ? '◆' : '▲'}</span></div>
                  <div className="long-cycle-label">{node.label}</div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="long-cycle-legend">
          <div className="legend-item"><div className="legend-dot major"></div><span>■ 重大战略节点</span></div>
          <div className="legend-item"><div className="legend-dot minor"></div><span>▲ 专题白皮书</span></div>
        </div>
      </div>
      )}

      {/* ── 最新政策文件 — 从 policy_search 动态获取 ── */}
      {activePolicySub === 'list' && (
      <div className="timeline-section">
        {/* ── 未来政策日程（统一从日历 Routine/政策会议种子读取）── */}
        <h2 className="section-title">🔔 未来政策日程</h2>
        <CardWrapper style={{ maxWidth: '50%', padding: 12, marginBottom: 16 }}>
          {((timeline.data && timeline.data.upcoming_schedule) || []).slice(0, 12).map((s, i, arr) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, padding: '3px 0',
              borderBottom: i < Math.min(arr.length, 12) - 1 ? '1px solid var(--border-subtle)' : 'none',
            }}>
              <span style={{ color: 'var(--text-muted)', fontSize: 11, width: 80, flexShrink: 0 }}>{s.date}</span>
              <span style={{ flex: 1, color: 'var(--text-secondary)' }}>{s.name}</span>
              <span style={{
                fontSize: 10, padding: '1px 5px', borderRadius: 3, flexShrink: 0,
                color: s.category === '政策会议' ? '#8FD6FF' : '#C9A861',
                background: s.category === '政策会议' ? 'rgba(143,214,255,0.13)' : 'rgba(201,168,97,0.13)',
              }}>{s.category}</span>
            </div>
          ))}
          {((timeline.data && timeline.data.upcoming_schedule) || []).length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>暂无未来政策节点（需先运行 calendar_seed_routine）</div>
          )}
        </CardWrapper>

        <h2 className="section-title">📄 {timelineYear} 年政策文件</h2>
        <CardWrapper style={{ maxWidth: '50%', display: 'flex', flexDirection: 'column', gap: 0, padding: 0 }}>
          <div style={{ padding: 12 }}>
            {realDocs.length > 0 ? realDocs.slice(0, 10).map((doc, i) => {
              const kw = (doc.match(/\[(.+?)\]/)?.[1] || '').split(',').map(s => s.trim()).filter(Boolean);
              const date = doc.match(/\d{4}-\d{2}-\d{2}/)?.[0] || '';
              const filename = doc.replace(/^\s*\d{4}-\d{2}-\d{2}\s*/, '');
              const url = (() => {
                const parts = doc.trim().split(/\s+/);
                const last = parts[parts.length - 1];
                return (last && (last.startsWith('http://') || last.startsWith('https://'))) ? last : '';
              })();
              const sent = doc.match(/〈(利好|利空|中性)〉/)?.[1] || '';
              return (
              <CardWrapper key={i} as="a" href={url || undefined} target={url ? '_blank' : undefined} rel="noopener noreferrer" truncate hoverable={false}
                style={{ display: 'block', padding: '6px 0', borderBottom: i < Math.min(realDocs.length, 10) - 1 ? '1px solid var(--border-subtle)' : 'none', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, textDecoration: 'none', cursor: url ? 'pointer' : 'default', background: 'transparent', backdropFilter: 'none', border: 'none', borderRadius: 0, margin: 0 }}
                onMouseEnter={(e) => {
                  setHoverCard({ show: true, x: e.clientX + 12, y: e.clientY - 16, policy: { title: doc.substring(0, 40), tag: '政策文件', content: doc, impact: kw.slice(0, 5).join('、') }, keywords: kw });
                }} onMouseMove={moveHover} onMouseLeave={hideHover}>
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{date}</span>
                {sent && sent !== '中性' && (
                  <span style={{
                    marginLeft: 6, fontSize: 10, padding: '1px 5px', borderRadius: 3,
                    color: sent === '利好' ? '#5BAE7A' : '#C0584F',
                    background: sent === '利好' ? 'rgba(91,174,122,0.15)' : 'rgba(192,88,79,0.15)',
                    border: `1px solid ${sent === '利好' ? 'rgba(91,174,122,0.5)' : 'rgba(192,88,79,0.5)'}`,
                  }}>{sent}</span>
                )}
                {kw.length > 0 && (
                  <span style={{ marginLeft: 6, fontSize: 10, color: 'var(--accent-gold)' }}>
                    [{kw.slice(0, 3).join(', ')}{kw.length > 3 ? '…' : ''}]
                  </span>
                )}
                <span style={{ marginLeft: 6 }}>{filename}</span>
              </CardWrapper>
              );
            }) : <div style={{ padding: 12, fontSize: 12, color: 'var(--text-muted)' }}>该年暂无政策数据</div>}
          </div>
        </CardWrapper>
      </div>
      )}

      {/* ── 官方链接 — 从后端配置读取 ── */}
      {activePolicySub === 'stats' && (
      <div className="links-section">
        <div className="links-header"><h2>🔗 官方直达</h2></div>
        <div className="links-container">
          {(tl?.official_links || []).map((link) => (
            <a key={link.url} href={link.url} target="_blank" rel="noopener noreferrer">{link.name}</a>
          ))}
        </div>
      </div>
      )}

      {/* ── 采集管理 ── */}
      {activePolicySub === 'collect' && (
      <div className="links-section">
        <div className="links-header"><h2>🔄 采集管理</h2></div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 4 }}>
          <div className="card" style={{ padding: 20 }}>
            <h3 style={{ margin: '0 0 10px 0' }}>📥 政策数据采集</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, margin: '0 0 14px 0' }}>
              点击下方按钮触发后端采集：遍历国务院 / 财政部 / 发改委等官方源，抓取最新政策文件并入库。
              采集完成后「政策统计」「文件列表」将自动刷新。
            </p>
            <button
              onClick={() => collectMutation.mutate()}
              disabled={collectMutation.isPending}
              style={{
                fontSize: 14, padding: '8px 20px', borderRadius: 8, cursor: 'pointer',
                background: 'var(--primary)', color: '#fff', border: 'none',
                opacity: collectMutation.isPending ? 0.6 : 1, fontWeight: 700,
              }}
            >
              {collectMutation.isPending ? '⏳ 采集中…' : '🔄 立即采集'}
            </button>
            {collectMutation.isError && (
              <div style={{ marginTop: 10, fontSize: 13, color: 'var(--secondary)' }}>采集失败，请稍后重试</div>
            )}
            <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>
              上次更新：<UpdateTimestamp updatedAt={stats.updatedAt} compact />
            </div>
          </div>
        </div>
      </div>
      )}

      {/* ── 悬浮卡片 ── */}
      <div className="policy-hover-card" style={{ left: hoverCard.x, top: hoverCard.y, display: hoverCard.show ? 'block' : 'none' }}>
        {hoverCard.policy && (
          <>
            <span className="policy-tag">{hoverCard.policy.tag || '政策文件'}</span>
            <h3 className="policy-title">{hoverCard.policy.title}</h3>
            {hoverCard.policy.time && <div className="policy-meta">发布时间：{hoverCard.policy.time} · {hoverCard.policy.dept}</div>}
            <div className="policy-content">{hoverCard.policy.content && hoverCard.policy.content.length > 100 ? hoverCard.policy.content.substring(0, 100) + '…' : hoverCard.policy.content}</div>
            {hoverCard.keywords.length > 0 && <div className="policy-impact">影响板块：{hoverCard.keywords.join(' · ')}</div>}
            {hoverCard.policy.impact && !hoverCard.keywords.length && <div className="policy-impact">影响领域：{hoverCard.policy.impact}</div>}
          </>
        )}
      </div>
    </div>
  );
}
