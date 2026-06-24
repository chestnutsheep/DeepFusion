/**
 * 中观产业面板 — 趋势与信号模块
 *
 * 数据驱动设计：行业名称从 MCP 接口动态获取，不硬编码。
 * 阈值参数从 mesoConfig.js 读取。
 */
import {useCallback, useEffect, useMemo, useState} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {useMCP} from '../../hooks/useMCP';
import CardWrapper from '../common/CardWrapper';
import {
  BAROMETER_CARDS,
  CAUSAL_ROLE,
  CHECKPOINT_CONFIG,
  CONDUCTION_STATUS,
  INTERPRETATION_RULES,
  LINKAGE_TYPE,
  THRESHOLDS,
} from './mesoConfig';

// ═══════════════════════════════════════════════════════
//  工具函数
// ═══════════════════════════════════════════════════════

/** 安全解析浮点数 */
const safeFloat = (v) => { const n = parseFloat(v); return isNaN(n) ? null : n; };

/** 通用：解析 CSV 表头 → 列名→索引映射 */
function buildColMap(headerLine) {
  const headers = headerLine.split(',').map(h => h.trim());
  const m = {};
  headers.forEach((h, i) => { m[h] = i; });
  return m;
}

/**
 * 解析 industry_sw_daily 返回的 CSV
 * 返回 { industries: 按行业名索引的最新快照, dates: 所有日期, matrix: 行业×日期涨跌幅矩阵 }
 */
function parseSWDaily(csv) {
  if (!csv) return { industries: [], dates: [], matrix: {} };
  const lines = csv.trim().split('\n');
  if (lines.length < 2) return { industries: [], dates: [], matrix: {} };

  const col = buildColMap(lines[0]);
  const iCode   = col['指数代码'] ?? 0;
  const iName   = col['指数名称'] ?? 1;
  const iDate   = col['发布日期'] ?? 2;
  const iClose  = col['收盘指数'] ?? 3;
  const iVol    = col['成交量'] ?? 4;
  const iChange = col['涨跌幅'] ?? 5;

  const rows = lines.slice(1).map(l => l.split(','));

  const dateSet = new Set();
  rows.forEach(r => { const d = r[iDate]?.trim(); if (d) dateSet.add(d); });
  const dates = [...dateSet].sort();

  const byName = {};
  rows.forEach(r => {
    const name = r[iName]?.trim();
    if (!name) return;
    if (!byName[name]) byName[name] = [];
    byName[name].push({
      name,
      date: r[iDate]?.trim(),
      close: safeFloat(r[iClose]),
      change: safeFloat(r[iChange]),
      code: r[iCode]?.trim(),
    });
  });

  const industries = [];
  const matrix = {};
  for (const [name, recs] of Object.entries(byName)) {
    recs.sort((a, b) => b.date.localeCompare(a.date));
    industries.push(recs[0]);
    matrix[name] = {};
    recs.forEach(r => { if (r.change != null) matrix[name][r.date] = r.change; });
  }

  return { industries, dates, matrix };
}

/** 解析 Granger 因果检验 JSON 结果 */
function parseCausality(raw) {
  if (!raw) return null;
  try {
    return typeof raw === 'string' ? JSON.parse(raw) : raw;
  } catch { return null; }
}

/** 解析 industry_themes JSON 结果 */
function parseThemes(raw) {
  if (!raw) return null;
  try {
    return typeof raw === 'string' ? JSON.parse(raw) : raw;
  } catch { return null; }
}

/** 解析 DCC-GARCH JSON 结果 */
function parseDCC(raw) {
  if (!raw) return null;
  try {
    return typeof raw === 'string' ? JSON.parse(raw) : raw;
  } catch { return null; }
}

/** 滚动分位数计算（返回 Q_p 值） */
function rollingQuantile(values, quantile) {
  if (!values || values.length < 5) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.floor(sorted.length * quantile);
  return sorted[Math.min(idx, sorted.length - 1)];
}

/** 模糊匹配 THS 行业名 → SW 行业数据（因因果检验用 THS 分类，行情用 SW 分类） */
function fuzzyMatchIndustry(thName, swIndustries) {
  if (!thName || !swIndustries.length) return null;
  // 1. 精确匹配
  let m = swIndustries.find(i => i.name === thName);
  if (m) return m;
  // 2. THS 名包含 SW 名（如 "石油加工贸易" 包含 "石油加工"）
  m = swIndustries.find(i => thName.includes(i.name) || i.name.includes(thName));
  if (m) return m;
  // 3. 前缀匹配（如 "港口航运" → "港口"）
  const prefix2 = thName.slice(0, 2);
  m = swIndustries.find(i => i.name.startsWith(prefix2) || prefix2.startsWith(i.name.slice(0, 2)));
  if (m) return m;
  return null;
}

// ═══════════════════════════════════════════════════════
//  晴雨表卡片
// ═══════════════════════════════════════════════════════

/** 单张晴雨表卡片 */
function BarometerCard({ name, thName, role, close, change, prevChange, score, date }) {
  const isPositive = change != null && change >= 0;
  const arrow = change != null ? (isPositive ? '▲' : '▼') : '';
  const changeColor = isPositive ? 'var(--accent-red)' : 'var(--accent-green)';

  // 右上角角色标签颜色
  const roleColor = role === '先行' ? '#5bba57' : '#f85149';
  const roleBg = role === '先行' ? 'rgba(91,186,87,0.12)' : 'rgba(248,81,73,0.12)';
  const nameMismatch = thName && thName !== name;

  // 主显示值：优先涨跌幅，其次收盘价，不显示得分
  const mainDisplay = change != null
    ? `${isPositive ? '+' : ''}${change.toFixed(2)}%`
    : close != null
      ? close.toFixed(2)
      : '—';

  return (
    <CardWrapper style={{ padding: '16px 20px', minWidth: 0, flex: '1 1 0' }}>
      {/* 第一行：行业名称 + 右侧角色标签 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {name}
          {nameMismatch && <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', lineHeight: 1.2 }}>({thName})</span>}
        </span>
        <span style={{
          fontSize: 12, fontWeight: 700, color: roleColor,
          background: roleBg, padding: '3px 10px', borderRadius: 10,
          border: `1px solid ${roleColor}33`, flexShrink: 0, marginLeft: 6,
        }}>
          {role}
        </span>
      </div>
      {/* 第二行：主数值(22px加粗) + 箭头 */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontSize: 22, fontWeight: 800, color: change != null ? changeColor : 'var(--text-primary)' }}>
          {mainDisplay}
        </span>
        {change != null && close != null && (
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)' }}>
            {close.toFixed(2)}
          </span>
        )}
      </div>
      {/* 第三行：日期 */}
      {date && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{date}</div>
      )}
    </CardWrapper>
  );
}

// ═══════════════════════════════════════════════════════
//  验证球（Checkpoint）
// ═══════════════════════════════════════════════════════

/** 种植业方向验证球 */
function CheckpointIndicator({ name, dates, matrix }) {
  const latestDate = dates.length > 0 ? [...dates].sort()[dates.length - 1] : null;
  const result = useMemo(() => {
    if (!dates.length || !matrix[name]) return { status: 'nodata', desc: '无数据' };
    const sortedDates = [...dates].sort();
    const recent = sortedDates.slice(-3); // 最近3个交易日
    if (recent.length < 3) return { status: 'nodata', desc: '数据不足' };

    const changes = recent.map(d => matrix[name]?.[d]);
    if (changes.some(c => c == null)) return { status: 'nodata', desc: '数据缺失' };

    const dirToday = changes[2] >= 0 ? 'up' : 'down';
    const dirYesterday = changes[1] >= 0 ? 'up' : 'down';
    const dirDayBefore = changes[0] >= 0 ? 'up' : 'down';

    const match1 = dirToday === dirYesterday;
    const match2 = dirYesterday === dirDayBefore;

    if (match1 && match2) {
      return { status: 'continuation', desc: '趋势延续', color: '#3fb950' };
    } else if (!match1 && !match2) {
      return { status: 'reversal', desc: '趋势反转', color: '#f85149' };
    } else if (match1 && !match2) {
      return { status: 'recovery', desc: '趋势恢复', color: '#D4A853' };
    } else {
      return { status: 'pause', desc: '趋势停顿', color: '#5B8FA8' };
    }
  }, [name, dates, matrix]);

  const dotColor = result.color || '#888';
  const glowSize = 12;

  return (
    <CardWrapper style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minWidth: 100, gap: 4 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textAlign: 'center', lineHeight: 1.2 }}>
        {name}
      </div>
      <div style={{
        width: 36, height: 36, borderRadius: '50%',
        background: `radial-gradient(circle, ${dotColor}cc, ${dotColor}44)`,
        border: `2px solid ${dotColor}`,
        boxShadow: `0 0 ${glowSize}px ${dotColor}66`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: 14, fontWeight: 800, color: '#fff' }}>
          {result.status === 'continuation' ? '→' : result.status === 'reversal' ? '↺' : result.status === 'recovery' ? '↑' : result.status === 'pause' ? '⏸' : '?'}
        </span>
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, color: dotColor, textAlign: 'center' }}>
        {result.desc}
      </span>
      {latestDate && (
        <span style={{ fontSize: 10, color: 'var(--text-muted)', textAlign: 'center' }}>{latestDate}</span>
      )}
    </CardWrapper>
  );
}

// ═══════════════════════════════════════════════════════
//  因果传导链 + 传导状态灯
// ═══════════════════════════════════════════════════════

function CausalTransmissionSection({ causalityData, l1Industries, l1Matrix, l1Dates }) {
  const parsed = useMemo(() => parseCausality(causalityData), [causalityData]);

  // 数据日期
  const causalDate = parsed?.meta?.date_range?.[1] || (l1Dates.length > 0 ? [...l1Dates].sort()[l1Dates.length - 1] : null);

  // 计算传导状态
  const conductionStatus = useMemo(() => {
    if (!parsed || !l1Industries.length || !l1Dates.length) return CONDUCTION_STATUS.normal;

    const leading = parsed.leading_industries || [];
    const lagging = parsed.lagging_industries || [];

    if (leading.length < 3 || lagging.length < 3) return CONDUCTION_STATUS.normal;

    // 构建领先/滞后指数（5日累计收益）
    const sortedDates = [...l1Dates].sort();
    const recent = sortedDates.slice(-5);
    if (recent.length < 5) return CONDUCTION_STATUS.normal;

    const leadNames = leading.slice(0, THRESHOLDS.leadingLaggingTopK).map(i => i.industry);
    const lagNames = lagging.slice(0, THRESHOLDS.leadingLaggingTopK).map(i => i.industry);

    // 计算领先/滞后组5日累计收益
    const calcGroup5d = (names) => {
      let sum = 0, count = 0;
      names.forEach(n => {
        recent.forEach(d => {
          const v = l1Matrix[n]?.[d];
          if (v != null) { sum += v; count++; }
        });
      });
      return count > 0 ? sum / count * recent.length : 0;
    };

    const leadRet5d = calcGroup5d(leadNames);
    const lagRet5d = calcGroup5d(lagNames);

    // 使用 fallback 阈值（滚动分位数需要历史数据，此处简化）
    if (leadRet5d > THRESHOLDS.fallbackLeadRetBull && lagRet5d < THRESHOLDS.fallbackLagRetBear) {
      return CONDUCTION_STATUS.blocked;
    }
    if (leadRet5d > THRESHOLDS.fallbackLeadRetBull && lagRet5d > THRESHOLDS.fallbackLagRetBull) {
      return CONDUCTION_STATUS.smooth;
    }
    return CONDUCTION_STATUS.normal;
  }, [parsed, l1Industries, l1Matrix, l1Dates]);

  const topPairs = parsed?.top_causal_pairs || [];
  const leading = parsed?.leading_industries || [];
  const lagging = parsed?.lagging_industries || [];

  return (
    <div style={{ marginTop: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 700, color: 'var(--accent-gold)' }}>⛓️ 因果传导链</span>
        {/* 传导状态灯 */}
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          padding: '3px 10px', borderRadius: 12, fontSize: 13, fontWeight: 700,
          background: `${conductionStatus.color}18`, color: conductionStatus.color,
          border: `1px solid ${conductionStatus.color}33`,
        }}>
          {conductionStatus.icon} {conductionStatus.label}
        </span>
        {/* 数据日期 */}
        {causalDate && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 'auto' }}>
            数据截至 {causalDate}
          </span>
        )}
      </div>

      {/* 传导链列表 */}
      {topPairs.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {topPairs.slice(0, 5).map((pair, idx) => (
            <div key={idx} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '6px 12px', borderRadius: 6, fontSize: 'var(--fs-sm)',
              background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-subtle)',
            }}>
              <span style={{ fontWeight: 700, color: '#5bba57', fontSize: 14 }}>
                {CAUSAL_ROLE.leading.icon} {pair.source}
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                ──({pair.lag}日)──→
              </span>
              <span style={{ fontWeight: 700, color: '#f85149', fontSize: 14 }}>
                {pair.target} {CAUSAL_ROLE.lagging.icon}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', padding: '8px 0' }}>
          暂无因果传导数据，请运行 industry_themes_causality
        </div>
      )}

      {/* 领先/滞后行业摘要 */}
      {leading.length > 0 && (
        <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div style={{ padding: '10px 12px', borderRadius: 6, background: 'rgba(91,186,87,0.06)', border: '1px solid rgba(91,186,87,0.15)' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#5bba57', marginBottom: 4 }}>
              {CAUSAL_ROLE.leading.icon} 领先行业
            </div>
            {leading.slice(0, 5).map((i, idx) => (
              <div key={idx} style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
                <span>{i.industry}</span>
                <span style={{ fontWeight: 700, color: '#5bba57' }}>+{i.score}</span>
              </div>
            ))}
          </div>
          <div style={{ padding: '10px 12px', borderRadius: 6, background: 'rgba(248,81,73,0.06)', border: '1px solid rgba(248,81,73,0.15)' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#f85149', marginBottom: 4 }}>
              {CAUSAL_ROLE.lagging.icon} 滞后行业
            </div>
            {lagging.slice(0, 5).map((i, idx) => (
              <div key={idx} style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
                <span>{i.industry}</span>
                <span style={{ fontWeight: 700, color: '#f85149' }}>{i.score}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════
//  阵营对比
// ═══════════════════════════════════════════════════════

function CommunityComparisonSection({ themesData }) {
  const parsed = useMemo(() => parseThemes(themesData), [themesData]);
  const themesDate = parsed?.meta?.date_range?.[1] || null;

  const communities = useMemo(() => {
    if (!parsed?.themes) return [];
    return parsed.themes.slice(0, 2).map(theme => ({
      label: theme.label || theme.representative,
      representative: theme.representative,
      members: theme.members || [],
      nMembers: theme.n_members || 0,
      avgCorr: theme.avg_intra_corr,
      score: theme.score,
      trend: theme.trend,
      momentum: theme.momentum,
      fundFlow: theme.fund_flow,
    }));
  }, [parsed]);

  if (communities.length < 2) return null;

  // 判断主导方
  const [a, b] = communities;
  const avgA = a.momentum?.avg_5d || 0;
  const avgB = b.momentum?.avg_5d || 0;
  a.dominant = avgA >= avgB;
  b.dominant = avgA < avgB;

  return (
    <div style={{ marginTop: 18 }}>
      <div style={{ fontSize: 'var(--fs-sm)', fontWeight: 700, color: 'var(--accent-gold)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
        ⚔️ 阵营对比
        {themesDate && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 8 }}>
            数据截至 {themesDate}
          </span>
        )}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {communities.map((c, idx) => (
          <CardWrapper key={idx} style={{ padding: '14px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 700, color: c.dominant ? '#D4A853' : 'var(--text-secondary)' }}>
                {c.representative} 等{c.nMembers}行业
              </span>
              <span style={{
                fontSize: 11, fontWeight: 700,
                padding: '3px 10px', borderRadius: 10,
                background: c.dominant ? 'rgba(212,168,83,0.15)' : 'rgba(91,139,168,0.15)',
                color: c.dominant ? '#D4A853' : '#5B8FA8',
                border: `1px solid ${c.dominant ? 'rgba(212,168,83,0.3)' : 'rgba(91,139,168,0.3)'}`,
              }}>
                {c.dominant ? '🔥主导' : '跟随'}
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 13, color: 'var(--text-secondary)' }}>
              <div>内聚 <b style={{ color: 'var(--text-primary)' }}>{c.avgCorr?.toFixed(3) ?? '—'}</b></div>
              <div>5日动量 <b style={{ color: (c.momentum?.avg_5d || 0) >= 0 ? 'var(--accent-red)' : 'var(--accent-green)' }}>
                {c.momentum?.avg_5d != null ? `${c.momentum.avg_5d >= 0 ? '+' : ''}${(c.momentum.avg_5d * 100).toFixed(2)}%` : '—'}
              </b></div>
              <div>趋势 <b style={{ color: c.trend === 'strengthening' ? '#5bba57' : c.trend === 'weakening' ? '#f85149' : '#D4A853' }}>
                {c.trend === 'strengthening' ? '强化' : c.trend === 'weakening' ? '弱化' : '稳定'}
              </b></div>
              <div>评分 <b style={{ color: 'var(--accent-gold)' }}>{c.score?.toFixed(1) ?? '—'}</b></div>
            </div>
          </CardWrapper>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════
//  联动变化监控
// ═══════════════════════════════════════════════════════

function LinkageMonitorSection({ dccData }) {
  const parsed = useMemo(() => parseDCC(dccData), [dccData]);
  const dccDate = parsed?.meta?.date_range?.[1] || null;

  const changes = parsed?.corr_change_top || [];
  const increased = changes.filter(c => c.direction === 'up').slice(0, THRESHOLDS.linkageChangeTopK);
  const decreased = changes.filter(c => c.direction === 'down').slice(0, THRESHOLDS.linkageChangeTopK);

  if (changes.length === 0) return null;

  /** 自动解读 */
  const interpret = (pair, delta) => {
    for (const rule of INTERPRETATION_RULES) {
      if (rule.match(pair, delta)) return rule.text;
    }
    return null;
  };

  return (
    <div style={{ marginTop: 18 }}>
      <div style={{ fontSize: 'var(--fs-sm)', fontWeight: 700, color: 'var(--accent-gold)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
        🔗 联动关系变化
        {dccDate && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 8 }}>
            数据截至 {dccDate}
          </span>
        )}
      </div>

      {increased.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#5bba57', marginBottom: 4 }}>
            {LINKAGE_TYPE.increase.icon} 增强
          </div>
          {increased.map((item, idx) => {
            const pair = item.pair || [];
            const interp = interpret(pair, item.change || 0);
            return (
              <div key={idx} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '6px 10px', marginBottom: 3, borderRadius: 4,
                fontSize: 13, background: 'rgba(91,186,87,0.06)',
              }}>
                <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{pair.join(' ↔ ')}</span>
                <span style={{ color: '#5bba57', fontWeight: 700 }}>+{(item.change || 0).toFixed(4)}</span>
                {interp && <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>({interp})</span>}
              </div>
            );
          })}
        </div>
      )}

      {decreased.length > 0 && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#f85149', marginBottom: 4 }}>
            {LINKAGE_TYPE.decrease.icon} 减弱
          </div>
          {decreased.map((item, idx) => {
            const pair = item.pair || [];
            const interp = interpret(pair, item.change || 0);
            return (
              <div key={idx} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '6px 10px', marginBottom: 3, borderRadius: 4,
                fontSize: 13, background: 'rgba(248,81,73,0.06)',
              }}>
                <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{pair.join(' ↔ ')}</span>
                <span style={{ color: '#f85149', fontWeight: 700 }}>{(item.change || 0).toFixed(4)}</span>
                {interp && <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>({interp})</span>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════
//  流动性陷阱
// ═══════════════════════════════════════════════════════

function LiquidityTrapSection({ themesData }) {
  const parsed = useMemo(() => parseThemes(themesData), [themesData]);

  const traps = useMemo(() => {
    if (!parsed?.themes) return [];
    return parsed.themes.filter(theme => {
      const corr = theme.avg_intra_corr || 0;
      const mom5 = theme.momentum?.avg_5d || 0;
      const mom10 = theme.momentum?.avg_10d || 0;
      const mom20 = theme.momentum?.avg_20d || 0;
      const flow = theme.fund_flow?.net_amount_total || 0;

      return corr > THRESHOLDS.highIntraCorrThreshold
        && mom5 < 0 && mom10 < 0 && mom20 < 0
        && flow < 0;
    });
  }, [parsed]);

  if (traps.length === 0) return null;

  return (
    <div style={{ marginTop: 18 }}>
      <div style={{ fontSize: 'var(--fs-sm)', fontWeight: 700, color: '#f85149', marginBottom: 10 }}>
        ⚠️ 流动性陷阱
      </div>
      {traps.map((trap, idx) => (
        <div key={idx} style={{
          padding: '8px 12px', borderRadius: 6, marginBottom: 6,
          background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.2)',
          fontSize: 'var(--fs-xs)', color: 'var(--text-secondary)',
        }}>
          <b style={{ color: '#f85149' }}>{trap.representative}</b> 等{trap.n_members}行业
          — 高内聚({(trap.avg_intra_corr || 0).toFixed(2)})低动量，不宜抄底
        </div>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════
//  动态警告条
// ═══════════════════════════════════════════════════════

export function WarningBar({ l1Industries, l1Matrix, l1Dates }) {
  const { data: causalityRaw } = useMCP('industry_themes_causality', { window: 120, max_lag: 5 });
  const { data: themesRaw } = useMCP('industry_themes', { window: 120, n_clusters: 5, corr_method: 'pearson' });
  const { data: dccRaw } = useMCP('industry_themes_dcc', { window: 120 });

  const warnings = useMemo(() => {
    const result = [];

    // 1. 传导受阻
    const parsed = parseCausality(causalityRaw);
    if (parsed) {
      const leading = parsed.leading_industries || [];
      const lagging = parsed.lagging_industries || [];
      if (leading.length >= 3 && lagging.length >= 3 && l1Dates.length >= 5) {
        const sortedDates = [...l1Dates].sort();
        const recent = sortedDates.slice(-5);
        const leadNames = leading.slice(0, THRESHOLDS.leadingLaggingTopK).map(i => i.industry);
        const lagNames = lagging.slice(0, THRESHOLDS.leadingLaggingTopK).map(i => i.industry);

        const calcGroup5d = (names) => {
          let sum = 0, count = 0;
          names.forEach(n => {
            recent.forEach(d => {
              const v = l1Matrix[n]?.[d];
              if (v != null) { sum += v; count++; }
            });
          });
          return count > 0 ? sum / count * recent.length : 0;
        };

        const leadRet5d = calcGroup5d(leadNames);
        const lagRet5d = calcGroup5d(lagNames);

        if (leadRet5d > THRESHOLDS.fallbackLeadRetBull && lagRet5d < THRESHOLDS.fallbackLagRetBear) {
          result.push({ level: 'danger', text: '上游大涨但下游不跟，传导受阻，警惕上游板块回调' });
        }
      }
    }

    // 2. 流动性陷阱
    const themesParsed = parseThemes(themesRaw);
    if (themesParsed?.themes) {
      const hasTrap = themesParsed.themes.some(t =>
        (t.avg_intra_corr || 0) > THRESHOLDS.highIntraCorrThreshold
        && (t.momentum?.avg_5d || 0) < 0
        && (t.momentum?.avg_10d || 0) < 0
        && (t.fund_flow?.net_amount_total || 0) < 0
      );
      if (hasTrap) {
        result.push({ level: 'warning', text: '部分板块高内聚低动量，抄底风险较高' });
      }
    }

    // 3. 旧逻辑瓦解
    const dccParsed = parseDCC(dccRaw);
    if (dccParsed?.corr_change_top) {
      const hasDecouple = dccParsed.corr_change_top.some(c =>
        c.direction === 'down'
        && (c.change || 0) < THRESHOLDS.deltaCorrWarningThreshold
        && c.pair?.includes('煤炭') && c.pair?.includes('港口')
      );
      if (hasDecouple) {
        result.push({ level: 'warning', text: '煤炭-港口联动显著减弱，港口逻辑已切换至科技' });
      }
    }

    return result;
  }, [causalityRaw, themesRaw, dccRaw, l1Industries, l1Matrix, l1Dates]);

  if (warnings.length === 0) return null;

  return (
    <div style={{ marginBottom: 16 }}>
      {warnings.map((w, idx) => (
        <div key={idx} style={{
          padding: '8px 14px', borderRadius: 6, marginBottom: 6,
          background: w.level === 'danger' ? 'rgba(248,81,73,0.12)' : 'rgba(212,168,83,0.12)',
          border: `1px solid ${w.level === 'danger' ? 'rgba(248,81,73,0.3)' : 'rgba(212,168,83,0.3)'}`,
          fontSize: 'var(--fs-sm)', fontWeight: 600,
          color: w.level === 'danger' ? '#f85149' : '#D4A853',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span>{w.level === 'danger' ? '⚠️' : '⚡'}</span>
          {w.text}
        </div>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════
//  主模块：趋势与信号
// ═══════════════════════════════════════════════════════

export default function TrendsAndSignals({ l1Industries, l2Industries, l1Dates, l2Dates, l1Matrix, l2Matrix }) {
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);

  // 请求因果检验数据
  const { data: causalityRaw, isFetching: causalityFetching } = useMCP('industry_themes_causality', { window: 120, max_lag: 5 });
  // 请求主题聚类数据
  const { data: themesRaw, isFetching: themesFetching } = useMCP('industry_themes', { window: 120, n_clusters: 5, corr_method: 'pearson' });
  // 请求 DCC-GARCH 数据
  const { data: dccRaw, isFetching: dccFetching } = useMCP('industry_themes_dcc', { window: 120 });

  // 刷新分析：invalidate 三个工具的缓存，触发重新请求
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['industry_themes_causality'] }),
        queryClient.invalidateQueries({ queryKey: ['industry_themes'] }),
        queryClient.invalidateQueries({ queryKey: ['industry_themes_dcc'] }),
      ]);
    } catch (e) {
      console.error('刷新分析数据失败:', e);
    }
    // 等 isFetching 结束后清除 refreshing 状态
  }, [queryClient]);

  // 任一正在加载时显示加载状态
  const anyFetching = causalityFetching || themesFetching || dccFetching;
  // 当刷新触发且数据仍在加载时显示 refreshing
  const showRefreshing = refreshing && anyFetching;
  // 加载完成后清除 refreshing 状态（用 useEffect 避免渲染期间 setState）
  useEffect(() => {
    if (refreshing && !anyFetching) setRefreshing(false);
  }, [refreshing, anyFetching]);

  // ── 晴雨表卡片数据（数据驱动：从因果检验动态获取领先/滞后行业） ──
  const barometerData = useMemo(() => {
    const parsed = parseCausality(causalityRaw);
    const leading = parsed?.leading_industries || [];
    const lagging = parsed?.lagging_industries || [];
    const nLeading = BAROMETER_CARDS.leadingCount || 3;
    const nLagging = BAROMETER_CARDS.laggingCount || 3;

    const buildCard = (ind, role) => {
      const thName = ind.industry;
      // 模糊匹配 THS 行业名 → SW 行情数据
      const match = fuzzyMatchIndustry(thName, l1Industries) || fuzzyMatchIndustry(thName, l2Industries);

      let close = null, change = null, prevChange = null, matchedName = thName, date = null;
      if (match) {
        const useL1 = l1Industries.some(i => i.name === match.name);
        const srcDates = useL1 ? l1Dates : l2Dates;
        const srcMatrix = useL1 ? l1Matrix : l2Matrix;
        close = match.close;
        change = match.change;
        matchedName = match.name;
        date = match.date;
        const sortedDates = [...srcDates].sort();
        const lastIdx = sortedDates.indexOf(match.date);
        const prevDate = lastIdx > 0 ? sortedDates[lastIdx - 1] : null;
        prevChange = prevDate ? srcMatrix[match.name]?.[prevDate] : null;
      }

      return { name: matchedName, thName, role, close, change, prevChange, score: ind.score, date };
    };

    return {
      leadingCards: leading.slice(0, nLeading).map(i => buildCard(i, '先行')),
      laggingCards: lagging.slice(0, nLagging).map(i => buildCard(i, '滞后')),
    };
  }, [causalityRaw, l1Industries, l2Industries, l1Matrix, l2Matrix, l1Dates, l2Dates]);

  // ── 渲染 ──
  return (
    <div>
      {/* 关联性分析刷新按钮 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <button
          onClick={handleRefresh}
          disabled={anyFetching}
          style={{
            padding: '6px 16px', borderRadius: 8, fontSize: 'var(--fs-sm)', fontWeight: 700,
            background: anyFetching ? 'rgba(212,168,83,0.08)' : 'rgba(212,168,83,0.15)',
            border: `1.5px solid ${anyFetching ? 'var(--border-subtle)' : 'rgba(212,168,83,0.4)'}`,
            color: anyFetching ? 'var(--text-muted)' : 'var(--accent-gold)',
            cursor: anyFetching ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
            display: 'inline-flex', alignItems: 'center', gap: 6,
          }}
        >
          {anyFetching ? '⏳ 分析中...' : '🔄 刷新关联性分析'}
        </button>
        {showRefreshing && (
          <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>
            正在重新计算因果检验、主题聚类、DCC-GARCH...
          </span>
        )}
      </div>

      {/* 晴雨表卡片行 */}
      <div style={{
        display: 'flex', gap: 14, alignItems: 'stretch',
        marginBottom: 20,
      }}>
        {/* 先行组 */}
        {barometerData.leadingCards.map(card => (
          <BarometerCard key={card.thName} {...card} />
        ))}

        {/* 验证球 */}
        <CheckpointIndicator
          name={CHECKPOINT_CONFIG.industry}
          dates={l2Dates}
          matrix={l2Matrix}
        />

        {/* 滞后组 */}
        {barometerData.laggingCards.map(card => (
          <BarometerCard key={card.thName} {...card} />
        ))}
      </div>

      {/* 因果传导链 + 传导状态灯 */}
      <CausalTransmissionSection
        causalityData={causalityRaw}
        l1Industries={l1Industries}
        l1Matrix={l1Matrix}
        l1Dates={l1Dates}
      />

      {/* 阵营对比 */}
      <CommunityComparisonSection themesData={themesRaw} />

      {/* 联动变化监控 */}
      <LinkageMonitorSection dccData={dccRaw} />

      {/* 流动性陷阱 */}
      <LiquidityTrapSection themesData={themesRaw} />
    </div>
  );
}
