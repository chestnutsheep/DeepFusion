import {useMemo, useState} from 'react';
import {useMCP} from '../../hooks/useMCP';
import {useAppStore} from '../../store/index.js';
import DataChart from '../common/DataChart';
import DataCard from '../common/DataCard';
import CardWrapper from '../common/CardWrapper';
import ErrorBoundary from '../common/ErrorBoundary';
import UpdateTimestamp from '../common/UpdateTimestamp.jsx';

// ── CSV 解析工具 ──

function parsePriceCsv(csv) {
  if (!csv) return [];
  return csv.trim().split('\n').slice(1).map(l => {
    const p = l.split(',');
    return { period: (p[0] || '').slice(5), close: parseFloat(p[1]) || 0, volume: parseFloat(p[5]) || 0 };
  }).filter(d => !isNaN(d.close)).slice(-120);
}

function parseFxHistory(csv) {
  if (!csv) return [];
  return csv.trim().split('\n').slice(1).map(l => {
    const p = l.split(',');
    return { period: (p[0] || '').slice(0, 7), value: parseFloat(p[1]) || 0 };
  }).filter(d => !isNaN(d.value)).slice(-60);
}

function parseGenericCsv(csv, dateCol = 0, valCol = 1, slicePeriod = 7) {
  if (!csv) return [];
  return csv.trim().split('\n').slice(1).map(l => {
    const p = l.split(',');
    return { period: (p[dateCol] || '').slice(0, slicePeriod), value: parseFloat(p[valCol]) || 0 };
  }).filter(d => !isNaN(d.value)).slice(-60);
}

function safeParseJSON(raw) {
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

// ── 压力等级颜色映射 ──

const STRESS_COLORS = {
  CRITICAL: '#f85149',
  HIGH: '#da3633',
  MODERATE_HIGH: '#d29922',
  MODERATE: '#D4A853',
  LOW: '#3fb950',
  MINIMAL: '#56d364',
  ELEVATED: '#d29922',
  INVERTED: '#f85149',
  NORMAL: '#3fb950',
};

function stressColor(level) {
  if (!level) return '#888';
  const k = level.toUpperCase().replace(' ', '_');
  return STRESS_COLORS[k] || '#888';
}

function stressBg(level) {
  const c = stressColor(level);
  return `${c}18`;
}

// ── 区块标题 ──

function SectionHeader({ badge, title, highlight, desc }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <span style={{
        display: 'inline-flex', padding: '4px 12px',
        background: 'rgba(123,94,123,0.12)', border: '1px solid rgba(123,94,123,0.2)',
        borderRadius: 16, fontSize: 'var(--fs-2xs)', fontWeight: 600,
        color: 'var(--accent-rose)', marginBottom: 6,
      }}>{badge}</span>
      <h2 style={{ fontSize: 18, fontWeight: 700 }}>
        {title} <span style={{ color: 'var(--accent-gold)' }}>{highlight}</span>
      </h2>
      {desc && <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-sm)', marginTop: 2 }}>{desc}</p>}
    </div>
  );
}

// ══════════════════════════════════════════
// 金融压力指数 — 核心仪表盘
// ══════════════════════════════════════════

function StressSection() {
  const { data: stressRaw, updatedAt } = useMCP('financial_stress_index', {});
  const stress = safeParseJSON(stressRaw);

  if (!stress) return <CardWrapper style={{ padding: 24 }}><p style={{ color: 'var(--text-muted)', fontSize: 13 }}>加载金融压力数据...</p></CardWrapper>;

  const { overall_stress_level, stress_score, components, regional_alerts, cross_border_signals } = stress;
  const yc = components?.yield_curve || {};
  const ted = components?.ted_spread || {};
  const cs = components?.credit_spread || {};
  const fx = components?.fx_pressure || {};

  return (
    <div>
      <SectionHeader badge="⚡ 金融压力" title="全球金融压力" highlight="实时指数" desc="利差 · 汇率异动 · 信用冻结 · 区域预警 — 看出谁快爆了" />
      <UpdateTimestamp updatedAt={updatedAt} />

      {/* ── 核心评分仪表盘 ── */}
      <CardWrapper style={{ padding: 24, marginBottom: 16, textAlign: 'center',
        border: `2px solid ${stressColor(overall_stress_level)}`,
        background: stressBg(overall_stress_level),
      }}>
        <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', marginBottom: 4 }}>
          全球金融压力指数 · {stress.timestamp}
        </div>
        <div style={{ fontSize: 42, fontWeight: 800, color: stressColor(overall_stress_level), lineHeight: 1 }}>
          {stress_score ?? '—'}
        </div>
        <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', marginTop: 2 }}>
          0=无压力 10=系统性危机
        </div>
        <div style={{
          display: 'inline-block', padding: '6px 20px', borderRadius: 4,
          fontSize: 16, fontWeight: 700, letterSpacing: 1,
          color: stressColor(overall_stress_level),
          background: `${stressColor(overall_stress_level)}22`,
          border: `1px solid ${stressColor(overall_stress_level)}44`,
          marginTop: 8,
        }}>
          {overall_stress_level}
        </div>
      </CardWrapper>

      {/* ── 四大压力维度卡片 ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 16 }}>
        {/* 收益率曲线 */}
        <CardWrapper style={{ padding: 14, borderLeft: `3px solid ${yc.value < 0 ? '#f85149' : '#3fb950'}` }}>
          <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>收益率曲线 10Y-2Y</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: yc.value < 0 ? '#f85149' : '#3fb950' }}>
            {yc.value ?? '—'}%
          </div>
          <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-secondary)', marginTop: 4 }}>
            状态: <span style={{ color: stressColor(yc.status), fontWeight: 600 }}>{yc.status}</span>
            {yc.duration_months > 0 && ` · 倒挂${yc.duration_months}月`}
          </div>
          {yc.signal && <div style={{ fontSize: 'var(--fs-2xs)', color: '#d29922', marginTop: 4 }}>{yc.signal}</div>}
        </CardWrapper>

        {/* TED利差 */}
        <CardWrapper style={{ padding: 14, borderLeft: `3px solid ${ted.value > 1 ? '#d29922' : '#3fb950'}` }}>
          <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>TED 利差</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: ted.value > 1 ? '#d85149' : '#D4A853' }}>
            {ted.value ?? '—'}%
          </div>
          <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-secondary)', marginTop: 4 }}>
            状态: <span style={{ color: stressColor(ted.status), fontWeight: 600 }}>{ted.status}</span>
          </div>
          {ted.signal && <div style={{ fontSize: 'var(--fs-2xs)', color: '#d29922', marginTop: 4 }}>{ted.signal}</div>}
        </CardWrapper>

        {/* BAA信用利差 */}
        <CardWrapper style={{ padding: 14, borderLeft: `3px solid ${cs.value > 2 ? '#d29922' : '#3fb950'}` }}>
          <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>BAA 信用利差</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: cs.value > 3 ? '#f85149' : '#D4A853' }}>
            {cs.value ?? '—'}%
          </div>
          <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-secondary)', marginTop: 4 }}>
            状态: <span style={{ color: stressColor(cs.status), fontWeight: 600 }}>{cs.status}</span>
            {cs.direction && ` · ${cs.direction}`}
          </div>
          {cs.signal && <div style={{ fontSize: 'var(--fs-2xs)', color: '#d29922', marginTop: 4 }}>{cs.signal}</div>}
        </CardWrapper>

        {/* 亚太汇率 */}
        <CardWrapper style={{ padding: 14, borderLeft: '3px solid var(--accent-blue)' }}>
          <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>亚太汇率 30日变动</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
            {Object.entries(fx).map(([pair, info]) => (
              <div key={pair} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 600 }}>{pair}</span>
                <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 700, color: info['30d_change_pct'] > 2 ? '#f85149' : '#D4A853' }}>
                  {info.value ?? '—'} {info['30d_change_pct'] != null ? `(${info['30d_change_pct'] > 0 ? '+' : ''}${info['30d_change_pct']}%)` : ''}
                </span>
              </div>
            ))}
          </div>
        </CardWrapper>
      </div>

      {/* ── 区域预警 ── */}
      {regional_alerts?.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12, marginBottom: 16 }}>
          {regional_alerts.map((a, i) => (
            <CardWrapper key={i} style={{ padding: 14, borderLeft: `3px solid ${stressColor(a.level)}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 15, fontWeight: 700 }}>{a.region}</span>
                <span style={{
                  padding: '3px 10px', borderRadius: 3, fontSize: 'var(--fs-xs)', fontWeight: 700,
                  color: stressColor(a.level), background: `${stressColor(a.level)}18`,
                  border: `1px solid ${stressColor(a.level)}33`,
                }}>{a.level}</span>
              </div>
              <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-secondary)', marginTop: 6 }}>{a.reason}</div>
            </CardWrapper>
          ))}
        </div>
      )}

      {/* ── 跨域传导信号 ── */}
      {cross_border_signals?.length > 0 && (
        <CardWrapper style={{ padding: 16, marginBottom: 16, borderLeft: '3px solid var(--accent-rose)' }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>⚡ 跨域传导信号</h3>
          {cross_border_signals.map((s, i) => (
            <div key={i} style={{ padding: '8px 0', borderBottom: i < cross_border_signals.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}>
              <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)' }}>{s.signal}</div>
              <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)', marginTop: 2 }}>置信度: {(s.confidence * 100).toFixed(0)}%</div>
            </div>
          ))}
        </CardWrapper>
      )}
    </div>
  );
}

// ══════════════════════════════════════════
// 债务可持续性评估
// ══════════════════════════════════════════

function DebtSection() {
  const { data: debtRaw, updatedAt } = useMCP('debt_sustainability', { countries: 'CN,JP,KR,US' });
  const debt = safeParseJSON(debtRaw);

  if (!debt) return <CardWrapper style={{ padding: 24 }}><p style={{ color: 'var(--text-muted)', fontSize: 13 }}>加载债务可持续性数据...</p></CardWrapper>;

  const { ranking, summary } = debt;

  return (
    <div>
      <SectionHeader badge="🏛️ 债务" title="债务可持续性" highlight="对比评估" desc="政府债务/GDP · 外汇储备 · 增长率 — 谁还得上债" />
      <UpdateTimestamp updatedAt={updatedAt} />

      {/* 排名总览 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 16 }}>
        {ranking?.map((r, i) => {
          const gradeColor = r.sustainability_grade === 'A' ? '#3fb950' : r.sustainability_grade === 'B' ? '#D4A853' : r.sustainability_grade === 'C' ? '#d29922' : '#f85149';
          return (
            <CardWrapper key={i} style={{ padding: 16, borderLeft: `3px solid ${gradeColor}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 15, fontWeight: 700 }}>{r.country}</span>
                <span style={{
                  padding: '4px 12px', borderRadius: 3, fontSize: 14, fontWeight: 800,
                  color: gradeColor, background: `${gradeColor}18`,
                }}>{r.sustainability_grade}</span>
              </div>
              <div style={{ fontSize: 20, fontWeight: 700, color: gradeColor, marginTop: 8 }}>
                {r.sustainability_score ?? '—'} <span style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)' }}>可持续性评分</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 8 }}>
                {r.gov_debt_gdp_pct != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--fs-xs)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>政府债务/GDP</span>
                    <span style={{ fontWeight: 600, color: r.gov_debt_gdp_pct > 120 ? '#f85149' : '#D4A853' }}>
                      {r.gov_debt_gdp_pct}% <span style={{ color: stressColor(r.debt_risk), fontSize: 'var(--fs-2xs)' }}>{r.debt_risk}</span>
                    </span>
                  </div>
                )}
                {r.fx_reserves_months_import != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--fs-xs)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>外汇储备/月进口</span>
                    <span style={{ fontWeight: 600 }}>{r.fx_reserves_months_import}月 <span style={{ fontSize: 'var(--fs-2xs)' }}>{r.reserve_sufficiency}</span></span>
                  </div>
                )}
                {r.gdp_growth_pct != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--fs-xs)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>GDP增长率</span>
                    <span style={{ fontWeight: 600 }}>{r.gdp_growth_pct}%</span>
                  </div>
                )}
                {r.inflation_pct != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--fs-xs)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>通胀率</span>
                    <span style={{ fontWeight: 600 }}>{r.inflation_pct}%</span>
                  </div>
                )}
              </div>
            </CardWrapper>
          );
        })}
      </div>

      {/* 债务警告摘要 */}
      {summary?.debt_warning?.length > 0 && (
        <CardWrapper style={{ padding: 14, marginBottom: 16, borderLeft: '3px solid #f85149' }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, color: '#f85149', marginBottom: 6 }}>⚠️ 债务高危经济体</h3>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            {summary.debt_warning.join('、')} — 政府债务/GDP超过120%
          </div>
        </CardWrapper>
      )}
    </div>
  );
}

// ══════════════════════════════════════════
// 资本流动监测
// ══════════════════════════════════════════

function CapitalSection() {
  const { data: capitalRaw, updatedAt } = useMCP('capital_flow_monitor', { focus: 'apac' });
  const capital = safeParseJSON(capitalRaw);

  if (!capital) return <CardWrapper style={{ padding: 24 }}><p style={{ color: 'var(--text-muted)', fontSize: 13 }}>加载资本流动数据...</p></CardWrapper>;

  const { indicators, flow_signals, overall_assessment } = capital;
  const fxTrends = indicators?.fx_trends_30d || [];
  const cnReserves = indicators?.china_fx_reserves || {};
  const usYield = indicators?.us_10y_yield || {};
  const fedFunds = indicators?.fed_funds_rate || {};

  const assessmentColor = overall_assessment?.includes('外流') ? '#f85149' : overall_assessment?.includes('温和') ? '#d29922' : '#3fb950';

  return (
    <div>
      <SectionHeader badge="💸 资本" title="资本流动" highlight="监测" desc="汇率趋势 · 外储变化 · 美债锚 · 资金在进还是在逃" />
      <UpdateTimestamp updatedAt={updatedAt} />

      {/* 总体判断 */}
      <CardWrapper style={{ padding: 16, marginBottom: 16, textAlign: 'center',
        border: `2px solid ${assessmentColor}`, background: `${assessmentColor}18`,
      }}>
        <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>亚太资本流动总体判断</div>
        <div style={{ fontSize: 24, fontWeight: 800, color: assessmentColor }}>{overall_assessment}</div>
      </CardWrapper>

      {/* 汇率趋势 + 外储 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 16 }}>
        <CardWrapper style={{ padding: 14, borderLeft: '3px solid var(--accent-blue)' }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>汇率30日趋势</h3>
          {fxTrends.map((f, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0',
              borderBottom: i < fxTrends.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}>
              <span style={{ fontSize: 12 }}>{f.currency} ({f.pair})</span>
              <span style={{ fontSize: 12, fontWeight: 700, color: f['30d_change_pct'] > 1 ? '#f85149' : '#3fb950' }}>
                {f['30d_change_pct'] > 0 ? '+' : ''}{f['30d_change_pct']}%
              </span>
            </div>
          ))}
        </CardWrapper>

        {cnReserves.latest && (
          <CardWrapper style={{ padding: 14, borderLeft: '3px solid #D4A853' }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>中国外汇储备</h3>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{cnReserves.latest} 亿美元</div>
            <div style={{ fontSize: 'var(--fs-xs)', color: cnReserves.direction === '↓' ? '#f85149' : '#3fb950', marginTop: 4 }}>
              {cnReserves.direction} {cnReserves.change_pct != null ? `${cnReserves.change_pct}%` : ''}
            </div>
          </CardWrapper>
        )}

        {usYield.latest && (
          <CardWrapper style={{ padding: 14, borderLeft: '3px solid #5B8FA8' }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>美债10Y收益率</h3>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{usYield.latest}%</div>
            <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-secondary)', marginTop: 4 }}>
              {usYield.direction} · {usYield.signal || ''}
            </div>
          </CardWrapper>
        )}

        {fedFunds.latest && (
          <CardWrapper style={{ padding: 14, borderLeft: '3px solid var(--accent-rose)' }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>联邦基金利率</h3>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{fedFunds.latest}%</div>
            <div style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-secondary)', marginTop: 4 }}>
              {fedFunds.direction} · {fedFunds.signal || ''}
            </div>
          </CardWrapper>
        )}
      </div>

      {/* 流动信号 */}
      {flow_signals?.length > 0 && (
        <CardWrapper style={{ padding: 14, borderLeft: '3px solid var(--accent-rose)' }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>流动信号</h3>
          {flow_signals.map((s, i) => (
            <div key={i} style={{ fontSize: 'var(--fs-sm)', color: s.includes('⚠️') ? '#d29922' : 'var(--text-secondary)', padding: '4px 0' }}>{s}</div>
          ))}
        </CardWrapper>
      )}
    </div>
  );
}

// ══════════════════════════════════════════
// 资产泡沫监视
// ══════════════════════════════════════════

function BubbleSection() {
  const { data: bubbleRaw, updatedAt } = useMCP('asset_bubble_watch', { region: 'all' });
  const bubble = safeParseJSON(bubbleRaw);

  if (!bubble) return <CardWrapper style={{ padding: 24 }}><p style={{ color: 'var(--text-muted)', fontSize: 13 }}>加载泡沫监测数据...</p></CardWrapper>;

  const { bubbles, overall_risk } = bubble;
  const overallColor = overall_risk?.includes('MULTIPLE') ? '#f85149' : overall_risk?.includes('ELEVATED') ? '#d29922' : '#D4A853';

  return (
    <div>
      <SectionHeader badge="🫧 泡沫" title="资产泡沫" highlight="监视" desc="量先跌价后跌 — 交易量萎缩=崩盘前兆" />
      <UpdateTimestamp updatedAt={updatedAt} />

      {/* 总体风险 */}
      <CardWrapper style={{ padding: 16, marginBottom: 16, textAlign: 'center',
        border: `2px solid ${overallColor}`, background: `${overallColor}18`,
      }}>
        <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>综合泡沫风险</div>
        <div style={{ fontSize: 24, fontWeight: 800, color: overallColor }}>{overall_risk}</div>
      </CardWrapper>

      {/* 各区域泡沫 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12, marginBottom: 16 }}>
        {Object.entries(bubbles).map(([key, b]) => {
          const riskColor = stressColor(b.bubble_risk);
          return (
            <CardWrapper key={key} style={{ padding: 16, borderLeft: `3px solid ${riskColor}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 14, fontWeight: 700 }}>{b.region} · {b.asset}</span>
                <span style={{
                  padding: '3px 10px', borderRadius: 3, fontSize: 'var(--fs-xs)', fontWeight: 700,
                  color: riskColor, background: `${riskColor}18`,
                }}>{b.bubble_risk}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {b.house_price_yoy != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--fs-xs)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>房价同比</span>
                    <span style={{ fontWeight: 600, color: b.house_price_yoy < 0 ? '#f85149' : '#D4A853' }}>{b.house_price_yoy}%</span>
                  </div>
                )}
                {b.price_signal && (
                  <div style={{ fontSize: 'var(--fs-2xs)', color: b.price_signal.includes('⚠️') ? '#d29922' : 'var(--text-secondary)' }}>{b.price_signal}</div>
                )}
                {b.volume_signal && (
                  <div style={{ fontSize: 'var(--fs-2xs)', color: b.volume_signal.includes('⚠️') ? '#d29922' : 'var(--text-secondary)' }}>{b.volume_signal}</div>
                )}
                {b.usdjpy_latest != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--fs-xs)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>USDJPY</span>
                    <span style={{ fontWeight: 600, color: b.usdjpy_latest > 160 ? '#f85149' : '#D4A853' }}>{b.usdjpy_latest}</span>
                  </div>
                )}
                {b.fx_signal && <div style={{ fontSize: 'var(--fs-2xs)', color: b.fx_signal.includes('⚠️') ? '#d29922' : 'var(--text-secondary)' }}>{b.fx_signal}</div>}
                {b.usdkrw_latest != null && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--fs-xs)' }}>
                    <span style={{ color: 'var(--text-muted)' }}>USDKRW</span>
                    <span style={{ fontWeight: 600, color: b.usdkrw_latest > 1400 ? '#f85149' : '#D4A853' }}>{b.usdkrw_latest}</span>
                  </div>
                )}
              </div>
            </CardWrapper>
          );
        })}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════
// 衍生品市场（原期货/贵金属/加密货币/外汇）
// ══════════════════════════════════════════

function FuturesSection() {
  const [symbol, setSymbol] = useState('原油');
  const commonSymbols = [
    { name: '原油', label: '🛢️ 原油' },
    { name: '沪金', label: '🥇 黄金' },
    { name: '沪银', label: '🥈 白银' },
    { name: '沪铜', label: '🪙 铜' },
    { name: '碳酸锂', label: '⚡ 碳酸锂' },
    { name: '多晶硅', label: '☀️ 多晶硅' },
    { name: '铁矿石', label: '🪨 铁矿石' },
  ];

  const { data: priceRaw } = useMCP('futures_prices', { symbol, limit: 60 });
  const { data: invRaw } = useMCP('futures_inventory', { symbol });
  const { data: basisRaw } = useMCP('futures_basis', { symbol });

  const priceData = useMemo(() => parsePriceCsv(priceRaw), [priceRaw]);
  const invData = useMemo(() => parseGenericCsv(invRaw, 0, 1, 10), [invRaw]);
  const latestPrice = priceData[priceData.length - 1]?.close;
  const prevPrice = priceData[priceData.length - 2]?.close;
  const priceChange = latestPrice && prevPrice ? ((latestPrice - prevPrice) / prevPrice * 100) : null;

  return (
    <div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
        {commonSymbols.map(s => (
          <button key={s.name} onClick={() => setSymbol(s.name)}
            style={{
              padding: '4px 12px', borderRadius: 2, fontSize: 'var(--fs-xs)',
              fontWeight: symbol === s.name ? 700 : 500,
              background: symbol === s.name ? 'var(--accent-gold)' : 'transparent',
              color: symbol === s.name ? '#000' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)', cursor: 'pointer',
            }}>{s.label}</button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 14 }}>
        <DataCard label={`${symbol} 最新价`} value={latestPrice} unit="元" decimals={2} higherBetter={null} detail="主力合约" />
        <DataCard label="涨跌幅" value={priceChange} unit="%" decimals={2} higherBetter={true} />
        <DataCard label="库存变化" detail="期货仓单" higherBetter={null}
          value={invData.length > 0 ? invData[invData.length - 1].value : null} unit="" decimals={1} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 14 }}>
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📈 价格走势 · {symbol} 主力</h3>
          <DataChart data={priceData} series={[{ key: 'close', name: `${symbol}`, color: '#D4A853', type: 'line' }]} dateKey="period" height={260} />
        </CardWrapper>
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📊 库存变化 · {symbol}</h3>
          <DataChart data={invData} series={[{ key: 'value', name: '库存', color: '#7B5E7B', type: 'bar' }]} dateKey="period" height={260} />
        </CardWrapper>
      </div>

      {basisRaw && (
        <CardWrapper style={{ padding: 14, marginTop: 14 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>📋 期现基差</h3>
          <pre style={{ fontSize: 'var(--fs-xs)', whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', margin: 0 }}>{basisRaw}</pre>
        </CardWrapper>
      )}
    </div>
  );
}

function MetalsSection() {
  const [showNorm, setShowNorm] = useState(false);
  const { data: goldRaw } = useMCP('pm_spot_prices', { symbol: 'Au99.99', limit: 60 });
  const { data: silverRaw } = useMCP('pm_spot_prices', { symbol: 'Ag(T+D)', limit: 60 });
  const { data: etfGoldRaw } = useMCP('pm_etf_holdings', { metal: 'gold', limit: 30 });
  const { data: comexRaw } = useMCP('pm_comex_inventory', { metal: '黄金', limit: 30 });

  const goldData = useMemo(() => parsePriceCsv(goldRaw), [goldRaw]);
  const silverData = useMemo(() => parsePriceCsv(silverRaw), [silverRaw]);
  const etfData = useMemo(() => parseGenericCsv(etfGoldRaw, 0, 1, 10), [etfGoldRaw]);
  const comexData = useMemo(() => parseGenericCsv(comexRaw, 0, 1, 10), [comexRaw]);

  const goldLatest = goldData[goldData.length - 1]?.close;
  const silverLatest = silverData[silverData.length - 1]?.close;
  const ratio = goldLatest && silverLatest ? (goldLatest / silverLatest) : null;

  // 归一化对比：合并黄金白银数据到同一时间轴
  const mergedData = useMemo(() => {
    const goldMap = new Map(goldData.map(d => [d.period, d.close]));
    const silverMap = new Map(silverData.map(d => [d.period, d.close]));
    const allDates = [...new Set([...goldMap.keys(), ...silverMap.keys()])].sort();
    return allDates.map(d => ({
      period: d,
      gold: goldMap.get(d) ?? null,
      silver: silverMap.get(d) ?? null,
    }));
  }, [goldData, silverData]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          <DataCard label="🥇 黄金 Au99.99" value={goldLatest} unit="元/克" decimals={2} higherBetter={null} detail="SGE" />
          <DataCard label="🥈 白银 Ag(T+D)" value={silverLatest} unit="元/千克" decimals={0} higherBetter={null} detail="SGE" />
          <DataCard label="金银比" value={ratio} unit="" decimals={1} higherBetter={null} />
        </div>
        <button onClick={() => setShowNorm(!showNorm)} style={{
          padding: '4px 12px', borderRadius: 4, fontSize: 'var(--fs-xs)', fontWeight: 600,
          background: showNorm ? 'var(--accent-gold)' : 'transparent',
          color: showNorm ? '#000' : 'var(--text-secondary)',
          border: '1px solid var(--border-subtle)', cursor: 'pointer',
        }}>{showNorm ? '📊 归一化对比' : '📈 绝对值'}</button>
      </div>

      {showNorm ? (
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📊 贵金属归一化走势 · 基期=100</h3>
          <DataChart data={mergedData} series={[
            { key: 'gold', name: '黄金', color: '#D4A853', type: 'line' },
            { key: 'silver', name: '白银', color: '#C49BA5', type: 'line' },
          ]} dateKey="period" height={260} normalize={true} normalizeBase="first" />
        </CardWrapper>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 14 }}>
          <CardWrapper style={{ padding: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📈 黄金现货走势 · Au99.99</h3>
            <DataChart data={goldData} series={[{ key: 'close', name: '黄金', color: '#D4A853', type: 'line' }]} dateKey="period" height={260} />
          </CardWrapper>
          <CardWrapper style={{ padding: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📈 白银现货走势 · Ag(T+D)</h3>
            <DataChart data={silverData} series={[{ key: 'close', name: '白银', color: '#C49BA5', type: 'line' }]} dateKey="period" height={260} />
          </CardWrapper>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 14, marginTop: 14 }}>
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>🏦 黄金ETF持仓量</h3>
          <DataChart data={etfData} series={[{ key: 'value', name: 'ETF持仓', color: '#D4A853', type: 'line' }]} dateKey="period" height={220} />
        </CardWrapper>
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📦 COMEX黄金库存</h3>
          <DataChart data={comexData} series={[{ key: 'value', name: '库存', color: '#C47B7B', type: 'line' }]} dateKey="period" height={220} />
        </CardWrapper>
      </div>
    </div>
  );
}

function CryptoSection() {
  const [showNorm, setShowNorm] = useState(false);
  const { data: btcRaw } = useMCP('crypto_prices', { symbol: 'BTC-USDT', period: '1D', limit: 90 });
  const { data: ethRaw } = useMCP('crypto_prices', { symbol: 'ETH-USDT', period: '1D', limit: 90 });
  const { data: sentimentRaw } = useMCP('crypto_sentiment_metrics', { symbol: 'BTC', period: '1D' });
  const { data: fundingRaw } = useMCP('crypto_funding_rate', { symbol: 'BTC' });

  const btcData = useMemo(() => parsePriceCsv(btcRaw), [btcRaw]);
  const ethData = useMemo(() => parsePriceCsv(ethRaw), [ethRaw]);

  const btcLatest = btcData[btcData.length - 1]?.close;
  const ethLatest = ethData[ethData.length - 1]?.close;

  // 归一化对比：合并 BTC ETH 数据到同一时间轴
  const mergedData = useMemo(() => {
    const btcMap = new Map(btcData.map(d => [d.period, d.close]));
    const ethMap = new Map(ethData.map(d => [d.period, d.close]));
    const allDates = [...new Set([...btcMap.keys(), ...ethMap.keys()])].sort();
    return allDates.map(d => ({
      period: d,
      btc: btcMap.get(d) ?? null,
      eth: ethMap.get(d) ?? null,
    }));
  }, [btcData, ethData]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          <DataCard label="₿ BTC" value={btcLatest} unit="USDT" decimals={0} higherBetter={null} detail="OKX" />
          <DataCard label="Ξ ETH" value={ethLatest} unit="USDT" decimals={0} higherBetter={null} detail="OKX" />
        </div>
        <button onClick={() => setShowNorm(!showNorm)} style={{
          padding: '4px 12px', borderRadius: 4, fontSize: 'var(--fs-xs)', fontWeight: 600,
          background: showNorm ? 'var(--accent-gold)' : 'transparent',
          color: showNorm ? '#000' : 'var(--text-secondary)',
          border: '1px solid var(--border-subtle)', cursor: 'pointer',
        }}>{showNorm ? '📊 归一化对比' : '📈 绝对值'}</button>
      </div>
      <CardWrapper style={{ padding: 12, marginBottom: 14 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)' }}>📊 BTC 合约</span>
        <pre style={{ fontSize: 'var(--fs-xs)', whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>{fundingRaw || '暂无'}</pre>
      </CardWrapper>

      {showNorm ? (
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📊 加密货币归一化走势 · 基期=100</h3>
          <DataChart data={mergedData} series={[
            { key: 'btc', name: 'BTC', color: '#D4A853', type: 'line' },
            { key: 'eth', name: 'ETH', color: '#5B8FA8', type: 'line' },
          ]} dateKey="period" height={280} normalize={true} normalizeBase="first" />
        </CardWrapper>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 14 }}>
          <CardWrapper style={{ padding: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📈 BTC · 日线</h3>
            <DataChart data={btcData} series={[{ key: 'close', name: 'BTC', color: '#D4A853', type: 'line' }]} dateKey="period" height={280} />
          </CardWrapper>
          <CardWrapper style={{ padding: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📈 ETH · 日线</h3>
            <DataChart data={ethData} series={[{ key: 'close', name: 'ETH', color: '#5B8FA8', type: 'line' }]} dateKey="period" height={280} />
          </CardWrapper>
        </div>
      )}
      {sentimentRaw && (
        <CardWrapper style={{ padding: 14, marginTop: 14, borderLeft: '3px solid var(--accent-red)' }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>📊 市场情绪指标</h3>
          <pre style={{ fontSize: 'var(--fs-xs)', whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', margin: 0 }}>{sentimentRaw}</pre>
        </CardWrapper>
      )}
    </div>
  );
}

function ForexSection() {
  const [showNorm, setShowNorm] = useState(false);
  const { data: usdcnyRaw } = useMCP('fx_history', { symbol: 'USDCNY', limit: 60 });
  const { data: eurusdRaw } = useMCP('fx_history', { symbol: 'EURUSD', limit: 60 });
  const { data: fredRaw } = useMCP('fred_data', { series: 'fred_gs10', limit: 60 });

  const usdcnyData = useMemo(() => parseFxHistory(usdcnyRaw), [usdcnyRaw]);
  const eurusdData = useMemo(() => parseFxHistory(eurusdRaw), [eurusdRaw]);
  const fredData = useMemo(() => parseFxHistory(fredRaw), [fredRaw]);

  // 归一化对比：合并汇率数据到同一时间轴
  const mergedFxData = useMemo(() => {
    const cnyMap = new Map(usdcnyData.map(d => [d.period, d.value]));
    const eurMap = new Map(eurusdData.map(d => [d.period, d.value]));
    const allDates = [...new Set([...cnyMap.keys(), ...eurMap.keys()])].sort();
    return allDates.map(d => ({
      period: d,
      usdcny: cnyMap.get(d) ?? null,
      eurusd: eurMap.get(d) ?? null,
    }));
  }, [usdcnyData, eurusdData]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
        <button onClick={() => setShowNorm(!showNorm)} style={{
          padding: '4px 12px', borderRadius: 4, fontSize: 'var(--fs-xs)', fontWeight: 600,
          background: showNorm ? 'var(--accent-gold)' : 'transparent',
          color: showNorm ? '#000' : 'var(--text-secondary)',
          border: '1px solid var(--border-subtle)', cursor: 'pointer',
        }}>{showNorm ? '📊 归一化对比' : '📈 绝对值'}</button>
      </div>

      {showNorm ? (
        <CardWrapper style={{ padding: 16, marginBottom: 14 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📊 汇率归一化走势 · 基期=100</h3>
          <DataChart data={mergedFxData} series={[
            { key: 'usdcny', name: 'USDCNY', color: '#D4A853', type: 'line' },
            { key: 'eurusd', name: 'EURUSD', color: '#5B8FA8', type: 'line' },
          ]} dateKey="period" height={260} normalize={true} normalizeBase="first" />
        </CardWrapper>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 14 }}>
          <CardWrapper style={{ padding: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📈 USD/CNY 走势</h3>
            <DataChart data={usdcnyData} series={[{ key: 'value', name: 'USDCNY', color: '#D4A853', type: 'line' }]} dateKey="period" height={260} />
          </CardWrapper>
          <CardWrapper style={{ padding: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📈 EUR/USD 走势</h3>
            <DataChart data={eurusdData} series={[{ key: 'value', name: 'EURUSD', color: '#5B8FA8', type: 'line' }]} dateKey="period" height={260} />
          </CardWrapper>
        </div>
      )}
      <CardWrapper style={{ padding: 16, marginTop: 14 }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>🇺🇸 美国10Y国债收益率 · FRED</h3>
        <DataChart data={fredData} series={[{ key: 'value', name: '10Y收益率', color: '#C47B7B', type: 'line' }]} dateKey="period" height={240} />
      </CardWrapper>
    </div>
  );
}

// ══════════════════════════════════════════
// 主组件 — 由 Sidebar 子导航驱动
// ══════════════════════════════════════════

const SECTIONS = {
  stress: { component: StressSection, badge: '⚡ 金融压力', title: '全球金融压力指数', desc: '利差 · 汇率 · 信用 · 区域预警' },
  debt: { component: DebtSection, badge: '🏛️ 债务', title: '债务可持续性对比', desc: 'CN/JP/KR/US 四国横向评估' },
  capital: { component: CapitalSection, badge: '💸 资本', title: '资本流动监测', desc: '汇率趋势 · 外储 · 资金流向' },
  bubble: { component: BubbleSection, badge: '🫧 泡沫', title: '资产泡沫监视', desc: '房地产 · 日元 · 韩元' },
  markets: { component: null, badge: '📊 衍生品', title: '衍生品市场', desc: '期货 · 贵金属 · 加密货币 · 外汇' },
};

export default function GlobalPanel() {
  const activeGlobalSub = useAppStore((s) => s.activeGlobalSub);
  const [marketTab, setMarketTab] = useState('futures');

  // 国际监测区块直接显示
  if (activeGlobalSub !== 'markets') {
    const section = SECTIONS[activeGlobalSub] || SECTIONS.stress;
    const Component = section.component;
    return (
      <div>
        <div style={{
          padding: '28px 0 16px', borderBottom: '1px solid var(--border-subtle)', marginBottom: 20,
        }}>
          <span style={{
            display: 'inline-block', padding: '4px 14px',
            background: 'var(--shadow-glow)', border: '1px solid var(--border-subtle)',
            borderRadius: 20, fontSize: 'var(--fs-xs)', fontWeight: 600,
            color: 'var(--accent-gold)', marginBottom: 10,
          }}>✦ DeepFusion · 国际</span>
          <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: 0.5 }}>
            {section.title}
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 620, marginTop: 4 }}>
            {section.desc} · 本国→亚太→全球三层预警
          </p>
        </div>
        <ErrorBoundary>
          <Component />
        </ErrorBoundary>
      </div>
    );
  }

  // 衍生品市场 — 内部子 tab
  const marketTabs = [
    { key: 'futures', label: '📦 期货' },
    { key: 'metals', label: '💰 贵金属' },
    { key: 'crypto', label: '₿ 加密货币' },
    { key: 'forex', label: '💱 外汇' },
  ];

  return (
    <div>
      <div style={{
        padding: '28px 0 16px', borderBottom: '1px solid var(--border-subtle)', marginBottom: 20,
      }}>
        <span style={{
          display: 'inline-block', padding: '4px 14px',
          background: 'var(--shadow-glow)', border: '1px solid var(--border-subtle)',
          borderRadius: 20, fontSize: 11, fontWeight: 600,
          color: 'var(--accent-gold)', marginBottom: 10,
        }}>✦ DeepFusion · 衍生品</span>
        <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: 0.5 }}>
          多元资产 <span style={{ color: 'var(--accent-gold)' }}>跨市场监测</span>
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 620, marginTop: 4 }}>
          期货期限结构 · 贵金属库存流 · 加密情绪 · 外汇矩阵
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {marketTabs.map(t => (
          <button key={t.key} onClick={() => setMarketTab(t.key)}
            style={{
              padding: '6px 16px', borderRadius: 2, fontSize: 'var(--fs-sm)',
              fontWeight: marketTab === t.key ? 700 : 500,
              background: marketTab === t.key ? 'var(--accent-gold)' : 'transparent',
              color: marketTab === t.key ? '#000' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)', cursor: 'pointer',
            }}>{t.label}</button>
        ))}
      </div>

      <hr className="section-divider-thin" />

      <ErrorBoundary>
        {marketTab === 'futures' && <FuturesSection />}
        {marketTab === 'metals' && <MetalsSection />}
        {marketTab === 'crypto' && <CryptoSection />}
        {marketTab === 'forex' && <ForexSection />}
      </ErrorBoundary>
    </div>
  );
}