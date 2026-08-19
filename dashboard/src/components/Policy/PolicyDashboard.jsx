import React, {useEffect, useMemo, useState} from 'react';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {useNavigate} from 'react-router-dom';
import {useMCP} from '../../hooks/useMCP.js';
import {useAppStore} from '../../store/index.js';
import {mcp} from '../../services/mcp.js';
import CardWrapper from '../common/CardWrapper.jsx';
import UpdateTimestamp from '../common/UpdateTimestamp.jsx';
import SectionHeader from '../common/SectionHeader.jsx';
import DataCard from '../common/DataCard.jsx';
import '../../styles/policy-dashboard.css';

// ── 月份名称 ──
const MONTH_NAMES = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

// ── 从 timeline JSON 解析 ──
function parseTimeline(raw) {
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}
const safeParse = parseTimeline;

// 板块配色（与 deep_fusion/shared/policy_sectors.py 的 SECTOR_COLORS 保持一致，纯展示）
const SECTOR_COLORS = {
  '宏观金融': '#D4A853',
  '房地产基建': '#C49BA5',
  '绿色能源': '#5BAE7A',
  '科技数字': '#5B8FA8',
  '消费升级': '#C77DA0',
  '制造产业链': '#B5895B',
  '改革制度': '#8F7BD6',
  '其他': '#7A7266',
};
function sectorColor(s) { return SECTOR_COLORS[s] || SECTOR_COLORS['其他']; }

export default function PolicyDashboard() {
  const [favorites, setFavorites] = useState(() => {
    const saved = localStorage.getItem('policyFavorites');
    return saved ? new Set(JSON.parse(saved)) : new Set();
  });
  const [hoverCard, setHoverCard] = useState({ show: false, x: 0, y: 0, policy: null, keywords: [] });
  const [selected, setSelected] = useState(null); // 点击卡片弹出的"收录的政策卡片"
  const [selectedSector, setSelectedSector] = useState(null); // 点击板块头展开的该板块列表
  const [timelineYear, setTimelineYear] = useState(new Date().getFullYear());
  // ── 列表筛选（本地，基于已加载的 timeline.latest，三维度互动筛选）──
  const [filterKw, setFilterKw] = useState('');
  const [filterSector, setFilterSector] = useState('');
  const [filterSentiment, setFilterSentiment] = useState('');
  const activePolicySub = useAppStore((s) => s.activePolicySub);

  // ── 动态数据源 ──
  const stats = useMCP('policy_stats');
  const timeline = useMCP('policy_timeline', { year: timelineYear });
  // ── 现成轮子接入：每日要闻(新闻摘要) + 舆情热度(热点数据采集) ──
  const dailyBrief = useMCP('policy_daily_brief', { days: 7 });
  const hotSignals = useMCP('policy_hot_signals', { platform: 'douyin', keyword: '政策,规划,会议,发布,条例,发展', top_n: 8 });

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

  // ── 列表三维度过滤（本地，基于 timeline.latest）──
  const latestAll = (tl && tl.latest) || [];
  const filteredLatest = latestAll.filter((p) => {
    const seps = (p.sector || []).filter(Boolean);
    const kws = (p.keywords || []).filter(Boolean);
    if (filterSector && !seps.includes(filterSector)) return false;
    if (filterSentiment && (p.sentiment || '中性') !== filterSentiment) return false;
    if (filterKw) {
      const hay = ((p.title || '') + ' ' + kws.join(' ') + ' ' + seps.join(' ') + ' ' + (p.org || '')).toLowerCase();
      if (!hay.includes(filterKw.trim().toLowerCase())) return false;
    }
    return true;
  });

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

  // ── 派生指标：情绪分布 / 板块热度 / 月度分布（对齐 Meso 三分法 + Macro 快照条）──
  const latestAllForStats = (tl && tl.latest) || [];
  const sentimentAgg = useMemo(() => {
    const cnt = {利好: 0, 中性: 0, 利空: 0};
    latestAllForStats.forEach((p) => { cnt[p.sentiment || '中性'] = (cnt[p.sentiment || '中性'] || 0) + 1; });
    const sum = cnt.利好 + cnt.中性 + cnt.利空 || 1;
    return {
      ...cnt,
      goodPct: Math.round((cnt.利好 / sum) * 100),
      badPct: Math.round((cnt.利空 / sum) * 100),
    };
  }, [latestAllForStats]);

  const sectorHeatAgg = useMemo(() => {
    const map = {};
    latestAllForStats.forEach((p) => {
      (p.sector || []).forEach((s) => {
        if (!s) return;
        map[s] = map[s] || {name: s, total: 0, good: 0};
        map[s].total += 1;
        if (p.sentiment === '利好') map[s].good += 1;
      });
    });
    return Object.values(map)
      .map((m) => ({...m, goodRatio: m.total ? m.good / m.total : 0}))
      .sort((a, b) => b.total - a.total)
      .slice(0, 6);
  }, [latestAllForStats]);

  return (
    <div className="policy-dashboard-container" onMouseMove={moveHover}>
      {activePolicySub === 'stats' && (
      <>
        {/* ── Hero 总览区（对齐 MesoLayout Hero + MacroSnapshot 快照条）── */}
        <div className="policy-hero">
          <div className="ph-left">
            <span className="ph-eyebrow">REGULATORY RADAR</span>
            <h1 className="ph-title">政策雷达</h1>
            <p className="ph-desc">监管动态 · 政策解读 · 与行业 / 个股的市场联动穿透</p>
          </div>
          <div className="ph-right">
            <UpdateTimestamp updatedAt={stats.updatedAt} />
            <div className="ph-total">
              <span className="ph-total-num">{realStats.match(/\d+/)?.[0] || '—'}</span>
              <span className="ph-total-label">历史累计政策</span>
            </div>
          </div>
        </div>

        {/* ── 关键指标快照条（对齐 MacroSnapshot DataGrid）── */}
        <div className="policy-snapshot">
          <DataCard
            label="利好信号" value={sentimentAgg.利好} unit="条" higherBetter={null}
            source="同步" tooltip="近期政策中偏向积极（利好）的条目数"
          />
          <DataCard
            label="中性观察" value={sentimentAgg.中性} unit="条" higherBetter={null}
            source="同步" tooltip="近期政策中表述中性、需持续跟踪的条目数"
          />
          <DataCard
            label="谨慎信号" value={sentimentAgg.利空} unit="条" higherBetter={null}
            source="同步" tooltip="近期政策中偏向收紧（利空）的条目数"
          />
          <DataCard
            label="利好占比" value={sentimentAgg.goodPct} unit="%" higherBetter={null}
            source="综合" tooltip="利好 ÷ (利好+中性+利空) 的比例，反映政策风向"
          />
        </div>

        {/* ── 政策结构：情绪分布条 + 板块热度 TOP（对齐 Meso 三分法 / RankingTable）── */}
        <SectionHeader badge="STRUCTURE" title="政策结构" highlight="近期画像" desc="最新一日政策的情绪倾向与板块关注热度" />
        <div className="policy-structure">
          <CardWrapper className="ps-sentiment" hoverable={false}>
            <div className="pss-head">
              <span className="pss-label">情绪分布</span>
              <span className="pss-goodpct">利好占比 {sentimentAgg.goodPct}%</span>
            </div>
            <div className="pss-bar">
              <span className="pss-seg seg-good" style={{ width: `${sentimentAgg.goodPct}%` }} />
              <span className="pss-seg seg-neutral" style={{ width: `${100 - sentimentAgg.goodPct - sentimentAgg.badPct}%` }} />
              <span className="pss-seg seg-bad" style={{ width: `${sentimentAgg.badPct}%` }} />
            </div>
            <div className="pss-legend">
              <span><i className="dot dot-good" />利好 {sentimentAgg.利好}</span>
              <span><i className="dot dot-neutral" />中性 {sentimentAgg.中性}</span>
              <span><i className="dot dot-bad" />利空 {sentimentAgg.利空}</span>
            </div>
          </CardWrapper>

          <CardWrapper className="ps-heat" hoverable={false}>
            <div className="psh-head"><span className="psh-label">板块热度 TOP</span></div>
            <div className="psh-list">
              {sectorHeatAgg.map((s, i) => (
                <div
                  key={s.name}
                  className="psh-row"
                  onClick={() => { setFilterSector(s.name); setActivePolicySub('list'); }}
                  title="点击查看该板块全部政策"
                >
                  <span className="psh-rank">{i + 1}</span>
                  <span className="psh-name">{s.name}</span>
                  <span className="psh-count">{s.total}</span>
                  <span className={`psh-ratio ${s.goodRatio >= 0.5 ? 'r-good' : 'r-mid'}`}>
                    {Math.round(s.goodRatio * 100)}%
                  </span>
                </div>
              ))}
              {sectorHeatAgg.length === 0 && <div className="psh-empty">暂无板块数据</div>}
            </div>
          </CardWrapper>
        </div>
      </>
      )}

      {/* ── 现成轮子：每日要闻 + 舆情热度 ── */}
      {activePolicySub === 'stats' && (
      <div className="policy-extra-grid">
        {/* 每日要闻（新闻摘要轮子，政策语境化） */}
        <CardWrapper className="policy-brief" hoverable={false}>
          <SectionHeader badge="DAILY" title="每日要闻" highlight="政策播报" desc={dailyBrief.data ? `近 7 天 · ${dailyBrief.data.total} 条` : '聚合入库政策'} />
          {dailyBrief.isLoading && <div className="pe-loading">加载中…</div>}
          {dailyBrief.data && (
            <div className="pb-body">
              <div className="pb-summary">{dailyBrief.data.summary}</div>
              <div className="pb-topics">
                {dailyBrief.data.top_topics.slice(0, 6).map((t) => (
                  <span key={t.topic} className="pb-topic-pill">{t.topic}<i>{t.count}</i></span>
                ))}
              </div>
              {dailyBrief.data.blow_signals.length > 0 && (
                <div className="pb-blow">
                  <span className="pb-blow-label">🌬 吹风信号</span>
                  {dailyBrief.data.blow_signals.slice(0, 3).map((b, i) => (
                    <a key={i} href={b.url} target="_blank" rel="noreferrer" className="pb-blow-item">{b.title}</a>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardWrapper>

        {/* 舆情热度（热点数据采集轮子：实时热搜） */}
        <CardWrapper className="policy-hot" hoverable={false}>
          <SectionHeader badge="HOT" title="舆情热度" highlight="实时热搜" desc="抖音热搜中含政策/产业关键词" />
          {hotSignals.isLoading && <div className="pe-loading">加载中…</div>}
          {hotSignals.data && hotSignals.data.status === 'ok' && (
            <div className="ph-list">
              {hotSignals.data.items.map((it, i) => (
                <div key={i} className="ph-row">
                  <span className="ph-rank">{i + 1}</span>
                  <span className="ph-title">{it.title}</span>
                  {it.hot ? <span className="ph-heat">{(Number(it.hot) / 10000).toFixed(0)}w</span> : null}
                </div>
              ))}
              {hotSignals.data.items.length === 0 && <div className="pe-empty">当前无政策相关热搜</div>}
            </div>
          )}
          {hotSignals.data && hotSignals.data.status !== 'ok' && (
            <div className="pe-empty">热搜源暂不可用（{hotSignals.data.message || '接口变动'}）</div>
          )}
        </CardWrapper>
      </div>
      )}

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
                <div key={`${node.date}-${node.label}`} className="long-cycle-node">
                  <div className={cls}><span>{node.is_major ? '◆' : '▲'}</span></div>
                  <div className="long-cycle-label">{node.label}</div>
                  {node.date && <div className="long-cycle-date">{node.date}</div>}
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

      {/* ── 政策文件列表 — 最新时间线 + 按板块分类叠放 ── */}
      {activePolicySub === 'list' && (
      <div className="timeline-section">
        {/* ── 未来政策日程 ── */}
        <h2 className="section-title">🔔 未来政策日程</h2>
        <CardWrapper style={{ maxWidth: '60%', padding: 12, marginBottom: 24 }}>
          {((tl && tl.upcoming_schedule) || []).slice(0, 12).map((s, i, arr) => (
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
          {((tl && tl.upcoming_schedule) || []).length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>暂无未来政策节点（需先运行 calendar_seed_routine）</div>
          )}
        </CardWrapper>

        {/* ── 列表筛选栏（互动性：搜索 + 板块 + 情绪三维度过滤）── */}
        <div className="policy-filter-bar">
          <input
            className="policy-filter-input"
            placeholder="🔍 搜索标题 / 关键词…"
            value={filterKw}
            onChange={(e) => setFilterKw(e.target.value)}
          />
          <select className="policy-filter-select" value={filterSector} onChange={(e) => setFilterSector(e.target.value)}>
            <option value="">全部板块</option>
            {((tl?.sector_groups || []).map((g) => g.sector)).filter((v, i, a) => a.indexOf(v) === i).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select className="policy-filter-select" value={filterSentiment} onChange={(e) => setFilterSentiment(e.target.value)}>
            <option value="">全部情绪</option>
            <option value="利好">利好</option>
            <option value="利空">利空</option>
            <option value="中性">中性</option>
          </select>
          {(filterKw || filterSector || filterSentiment) && (
            <button className="policy-filter-clear" onClick={() => { setFilterKw(''); setFilterSector(''); setFilterSentiment(''); }}>清除</button>
          )}
        </div>

        {/* ── 最新政策（细节更多的时间线）── */}
        <h2 className="section-title">📰 最新政策动态
          {filteredLatest.length !== (tl?.latest || []).length && (
            <span className="policy-filter-count">（筛选 {filteredLatest.length} / {(tl?.latest || []).length}）</span>
          )}
        </h2>
        <div className="policy-latest-list">
          {filteredLatest.map((p, i) => (
            <PolicyListItem
              key={p.url || i}
              policy={p}
              onHover={showHover}
              onMove={moveHover}
              onLeave={hideHover}
              onClick={() => setSelected(p)}
            />
          ))}
          {filteredLatest.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {((tl && tl.latest) || []).length === 0 ? '该年暂无政策数据（请先采集）' : '无匹配筛选条件的政策'}
            </div>
          )}
        </div>

        {/* ── 按板块分类叠放 ── */}
        <h2 className="section-title" style={{ marginTop: 28 }}>🗂️ 按板块分类叠放</h2>
        <div className="policy-sector-grid">
          {((tl && tl.sector_groups) || []).map((g) => (
            <SectorStack
              key={g.sector}
              group={g}
              onHover={showHover}
              onMove={moveHover}
              onLeave={hideHover}
              onClick={setSelected}
              onSectorClick={setSelectedSector}
            />
          ))}
          {((tl && tl.sector_groups) || []).length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>暂无可按板块分类的政策</div>
          )}
        </div>
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

      {/* ── 信号源覆盖说明（吹风缺口补强）── */}
      {activePolicySub === 'stats' && (
      <div className="links-section">
        <div className="links-header"><h2>📡 信号覆盖</h2></div>
        <div className="coverage-note">
          <span className="coverage-pill coverage-official">官方源</span>
          <span>国务院 · 统计局 · 央行 · 财政部 · 发改委 · 外管局 · 证监会 · 央行 · 实时快讯</span>
          <span className="coverage-pill coverage-blow">吹风源</span>
          <span>新华网（规划/会议吹风）+ 券商中国（券商平台吹风）—— 覆盖「十五五文件 / 开会强调 xxxx 发展」类高价值信号</span>
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

      {/* ── 点击弹出"收录的政策卡片"（密集信息）── */}
      <PolicyDetailModal policy={selected} onClose={() => setSelected(null)} />
      <SectorListModal group={selectedSector} onClose={() => setSelectedSector(null)} onPick={(p) => { setSelectedSector(null); setSelected(p); }} />

    </div>
  );
}

/* ───────────────────────── 子组件 ───────────────────────── */

function sentimentTag(sent) {
  if (!sent || sent === '中性') return null;
  const color = sent === '利好' ? '#5BAE7A' : '#C0584F';
  return (
    <span style={{
      fontSize: 10, padding: '1px 6px', borderRadius: 3, marginLeft: 6,
      color, background: sent === '利好' ? 'rgba(91,174,122,0.15)' : 'rgba(192,88,79,0.15)',
      border: `1px solid ${sent === '利好' ? 'rgba(91,174,122,0.5)' : 'rgba(192,88,79,0.5)'}`,
    }}>{sent}</span>
  );
}

function PolicyListItem({ policy, onHover, onMove, onLeave, onClick }) {
  const seps = (policy.sector || []).filter(Boolean);
  const kws = (policy.keywords || []).filter(Boolean);
  // 吹风类信号源（券商平台/官方吹风，覆盖十五五/会议强调缺口）
  const BLOW_SOURCE = new Set(["新华网", "券商中国"]);
  const isBlow = BLOW_SOURCE.has(policy.org);
  return (
    <div
      className="policy-list-item"
      onClick={() => onClick(policy)}
      onMouseEnter={(e) => onHover(e, {
        title: policy.title, tag: (seps[0] || '政策'), time: policy.time || policy.date, dept: policy.dept || policy.org,
        content: (policy.content ? policy.content + '。' : '') + (kws.length ? '关键词：' + kws.join('、') + '。' : '') + (policy.org ? '发布机构：' + policy.org : ''),
      }, seps)}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
    >
      <div className="policy-list-main">
        <span className="policy-list-date">{policy.date}</span>
        <span
          className="policy-list-title"
          onDoubleClick={(e) => { e.stopPropagation(); if (policy.url) window.open(policy.url, '_blank', 'noopener'); }}
          title="双击标题跳转原发布网页"
        >{policy.title}</span>
        {sentimentTag(policy.sentiment)}
      </div>
      <div className="policy-list-tags">
        {seps.map((s) => <span key={s} className="policy-sector-chip">{s}</span>)}
        {kws.slice(0, 5).map((k) => <span key={k} className="policy-kw-chip">{k}</span>)}
        {kws.length > 0 && <span className="policy-link-hint">📈 含市场联动</span>}
        {isBlow && <span className="policy-blow-hint">🌬 吹风/{policy.org}</span>}
        {policy.url && <span className="policy-link-hint">双击标题↗</span>}
      </div>
    </div>
  );
}

function SectorStack({ group, onHover, onMove, onLeave, onClick, onSectorClick }) {
  const items = group.items || [];
  const shown = items.slice(0, 6);
  return (
    <div className="policy-sector-block" style={{ '--sector-color': group.color }}>
      <div className="policy-sector-head" title="点击展开该板块全部政策" style={{ cursor: 'pointer' }} onClick={() => onSectorClick(group)}>
        <span className="policy-sector-dot" />
        <span className="policy-sector-name">{group.sector}</span>
        <span className="policy-sector-count">{group.count} 篇</span>
      </div>
      <div className="policy-stack">
        {shown.map((p, i) => {
          const kws = (p.keywords || []).filter(Boolean);
          return (
            <div
              key={p.url || i}
              className="policy-stack-card"
              style={{ top: i * 6, zIndex: shown.length - i }}
              onClick={() => onClick(p)}
              onMouseEnter={(e) => onHover(e, {
                title: p.title, tag: group.sector, time: p.time || p.date, dept: p.dept || p.org,
                content: (p.content ? p.content + '。' : '') + (kws.length ? '关键词：' + kws.join('、') + '。' : '') + (p.org ? '发布机构：' + p.org : ''),
              }, (p.sector || []).filter(Boolean))}
              onMouseMove={onMove}
              onMouseLeave={onLeave}
            >
              <div className="policy-stack-row">
                <span className="policy-stack-date">{p.date}</span>
                <span
                  className="policy-stack-title"
                  onDoubleClick={(e) => { e.stopPropagation(); if (p.url) window.open(p.url, '_blank', 'noopener'); }}
                  title="双击标题跳转原发布网页"
                >{p.title}</span>
                {sentimentTag(p.sentiment)}
              </div>
            </div>
          );
        })}
        {items.length > shown.length && (
          <div className="policy-stack-more" onClick={() => onClick(items[shown.length])}>
            +{items.length - shown.length} 篇，点击查看更多
          </div>
        )}
      </div>
    </div>
  );
}

function SectorListModal({ group, onClose, onPick }) {
  if (!group) return null;
  return (
    <div className="policy-modal-overlay" onClick={onClose}>
      <div className="policy-modal policy-modal-wide" onClick={(e) => e.stopPropagation()} style={{ '--sector-color': group.color || '#C9A861' }}>
        <button className="policy-modal-close" onClick={onClose}>×</button>
        <div className="policy-modal-tags">
          <span className="policy-sector-chip" style={{ background: (group.color || '#C9A861') + '22', borderColor: group.color || '#C9A861' }}>{group.sector}</span>
        </div>
        <h2 className="policy-modal-title">该板块共收录 {group.count} 篇政策</h2>
        <div className="policy-modal-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
          {(group.items || []).map((p, i) => {
            const seps = (p.sector || []).filter(Boolean);
            const kws = (p.keywords || []).filter(Boolean);
            return (
              <div
                key={p.url || i}
                className="policy-list-item policy-list-item--compact"
                title="单击查看收录卡片 · 双击标题跳转原文"
                onClick={() => onPick(p)}
                onDoubleClick={(e) => { e.stopPropagation(); if (p.url) window.open(p.url, '_blank', 'noopener'); }}
              >
                <div className="policy-list-main">
                  <span className="policy-list-date">{p.time || p.date}</span>
                  <span className="policy-list-title" onDoubleClick={(e) => { e.stopPropagation(); if (p.url) window.open(p.url, '_blank', 'noopener'); }}>{p.title}</span>
                  {sentimentTag(p.sentiment)}
                </div>
                <div className="policy-list-tags">
                  {seps.map((s) => <span key={s} className="policy-sector-chip">{s}</span>)}
                  {kws.slice(0, 5).map((k) => <span key={k} className="policy-kw-chip">{k}</span>)}
                  {p.url && <span className="policy-link-hint">双击标题↗</span>}
                </div>
                {p.content && <div className="policy-list-content">{p.content}</div>}
              </div>
            );
          })}
        </div>
        <div className="policy-modal-hint">提示：单击某条可查看收录卡片，双击标题跳转原文</div>
      </div>
    </div>
  );
}

function PolicyDetailModal({ policy, onClose }) {
  // hooks 必须在任何 early return 之前调用，保证顺序稳定
  const detail = useMCP('policy_detail', policy && policy.url ? { url: policy.url } : null);
  // ── 市场联动：政策 → 行业/个股 桥接（关键词为主 + 板块映射兜底）──
  const linkKw = (policy && (policy.keywords || []).filter(Boolean).join(',')) || '';
  const linkSec = (policy && (policy.sector || []).filter(Boolean).join(',')) || '';
  const marketLink = useMCP('policy_market_link',
    (policy && (linkKw || linkSec)) ? { keywords: linkKw, sector: linkSec, top_n: 8 } : null);
  const navigate = useNavigate();
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const setActiveMesoSub = useAppStore((s) => s.setActiveMesoSub);
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  if (!policy) return null;
  const parsed = safeParse(detail.data);
  const body = parsed && parsed.body ? parsed.body : '';
  const seps = (policy.sector || []).filter(Boolean);
  const kws = (policy.keywords || []).filter(Boolean);
  const link = marketLink.data ? safeParse(marketLink.data) : null;
  const matchedIndustries = (link && link.matched_industries) || [];
  const repStocks = (link && link.representative_stocks) || [];
  // 跳转中观/个股：切 store + 路由到对应 tab
  const gotoMeso = () => { setActiveTab('meso'); onClose(); };
  const gotoMicro = () => { setActiveTab('micro'); onClose(); };
  return (
    <div className="policy-modal-overlay" onClick={onClose}>
      <div className="policy-modal" onClick={(e) => e.stopPropagation()} style={{ '--sector-color': (seps[0] && sectorColor(seps[0])) || '#C9A861' }}>
        <button className="policy-modal-close" onClick={onClose}>×</button>
        <div className="policy-modal-tags">
          {seps.map((s) => <span key={s} className="policy-sector-chip">{s}</span>)}
          {sentimentTag(policy.sentiment)}
        </div>
        <h2 className="policy-modal-title"
          onDoubleClick={() => { if (policy.url) window.open(policy.url, '_blank', 'noopener'); }}
          title="双击标题跳转原发布网页">{policy.title}</h2>
        <div className="policy-modal-meta">
          <span>发布：{(policy.date || '').slice(0, 10)}</span>
          <span>机构：{policy.org || '—'}</span>
        </div>
        {kws.length > 0 && (
          <div className="policy-modal-kw">
            {kws.map((k) => <span key={k} className="policy-kw-chip">{k}</span>)}
          </div>
        )}

        {/* ── 市场联动面板（政策 → 行业/个股）── */}
        <div className="policy-link-panel">
          <div className="policy-link-head">
            <span>📈 市场联动</span>
            <span className="policy-link-method">
              {link ? (link.link_method === 'keyword' ? '关键词桥接' : link.link_method === 'sector_map' ? '板块映射' : '关键词+板块') : ''}
            </span>
          </div>
          {marketLink.loading && <div className="policy-link-loading">正在桥接相关行业与个股…</div>}
          {!marketLink.loading && matchedIndustries.length > 0 && (
            <>
              <div className="policy-link-sub">相关行业（近期涨跌 / 主力净流入 / 龙头股）</div>
              <div className="policy-link-industries">
                {matchedIndustries.map((ind) => (
                  <div key={ind.industry_code} className="policy-link-industry">
                    <span className="pli-name">{ind.industry_name}</span>
                    <span className={'pli-chg ' + ((ind.pct_change ?? 0) >= 0 ? 'up' : 'down')}>
                      {ind.pct_change != null ? (ind.pct_change >= 0 ? '+' : '') + ind.pct_change + '%' : '—'}
                    </span>
                    <span className={'pli-flow ' + ((ind.net_inflow_yi ?? 0) >= 0 ? 'up' : 'down')}>
                      {ind.net_inflow_yi != null ? (ind.net_inflow_yi >= 0 ? '+' : '') + ind.net_inflow_yi + '亿' : '—'}
                    </span>
                    {ind.leader_stock && (
                      <span className="pli-leader" title="龙头股">{ind.leader_stock}{ind.leader_pct_change != null ? `(${ind.leader_pct_change >= 0 ? '+' : ''}${ind.leader_pct_change}%)` : ''}</span>
                    )}
                  </div>
                ))}
              </div>
              {repStocks.length > 0 && (
                <>
                  <div className="policy-link-sub">代表个股（来自相关行业龙头）</div>
                  <div className="policy-link-stocks">
                    {repStocks.map((s) => (
                      <span key={s.stock_name} className="policy-link-stock" title={`来自 ${s.from_industry}`}>
                        {s.stock_name}{s.pct_change != null ? ` ${s.pct_change >= 0 ? '+' : ''}${s.pct_change}%` : ''}
                      </span>
                    ))}
                  </div>
                </>
              )}
              <div className="policy-link-actions">
                <button className="policy-modal-btn" onClick={gotoMeso}>看中观行业 →</button>
                <button className="policy-modal-btn" onClick={gotoMicro}>看个股微观 →</button>
              </div>
            </>
          )}
          {!marketLink.loading && matchedIndustries.length === 0 && (
            <div className="policy-link-note">该政策暂无可桥接的行业关键词（无匹配行业板块）</div>
          )}
        </div>

        <div className="policy-modal-body">
          {detail.loading && <div className="policy-modal-loading">正在拉取原文摘要…</div>}
          {!detail.loading && body && <p>{body.length > 1800 ? body.slice(0, 1800) + '…' : body}</p>}
          {!detail.loading && !body && <p className="policy-modal-note">（该条目暂无正文快照，请点击右下方按钮跳转原文查看）</p>}
        </div>
        <div className="policy-modal-actions">
          <button className="policy-modal-btn" onClick={onClose}>关闭</button>
          {policy.url && <button className="policy-modal-btn primary" onClick={() => window.open(policy.url, '_blank', 'noopener')}>打开原发布网页 ↗</button>}
        </div>
        <div className="policy-modal-hint">提示：双击标题或点击右上按钮均可跳转原文</div>
      </div>
    </div>
  );
}
