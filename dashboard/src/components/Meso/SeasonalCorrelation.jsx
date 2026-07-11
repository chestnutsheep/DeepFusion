/**
 * 季节性相关性分析 — 交互式面板
 * 选择2+行业 → industry_seasonal_corr MCP → 热力图 + 排行表 + 剖面折线图
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useMCP } from '../../hooks/useMCP';
import { mcp } from '../../services/mcp.js';
import CardWrapper from '../common/CardWrapper';
import ErrorBoundary from '../common/ErrorBoundary';
import UpdateTimestamp from '../common/UpdateTimestamp.jsx';
import * as echarts from 'echarts';

const MONTH_NAMES = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

const PRESETS = [
  { label: '地产链', names: ['房地产', '建筑材料', '建筑装饰', '银行'] },
  { label: '消费链', names: ['食品饮料', '医药生物', '汽车', '家用电器'] },
  { label: '周期链', names: ['钢铁', '采掘', '有色金属', '化工'] },
  { label: '科技链', names: ['电子', '计算机', '通信', '电气设备'] },
];

// ── 行业选择器 ──
function SeasonalIndustryPicker({ allIndustries, selected, onToggle }) {
  const [search, setSearch] = useState('');
  const filtered = search
    ? allIndustries.filter(i => i.name.includes(search) || (i.code || '').includes(search))
    : allIndustries;

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 8,
      padding: '12px 14px', background: 'var(--bg-panel)',
      border: '1px solid var(--border-subtle)', borderRadius: 8,
      maxHeight: 340, overflow: 'hidden',
    }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder="搜索行业..."
          style={{ flex: 1, padding: '5px 10px', borderRadius: 5, fontSize: 'var(--fs-sm)',
            background: 'var(--bg-primary)', color: 'var(--text-primary)',
            border: '1px solid var(--border-subtle)', outline: 'none' }}
        />
        <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>
          已选 {selected.length}/{filtered.length}
        </span>
      </div>

      {/* 预设快捷 */}
      <div style={{ display: 'flex', gap: 4 }}>
        {PRESETS.map(p => (
          <button key={p.label} onClick={() => onToggle(null, null, p.names)} style={{
            padding: '2px 8px', borderRadius: 4, fontSize: 'var(--fs-xs)',
            background: 'rgba(123,94,123,0.08)', border: '1px solid rgba(123,94,123,0.2)',
            color: 'var(--accent-rose)', cursor: 'pointer',
          }}>{p.label}</button>
        ))}
        <button onClick={() => onToggle(null, null, [])} style={{
          padding: '2px 8px', borderRadius: 4, fontSize: 'var(--fs-xs)',
          background: 'transparent', border: '1px solid var(--border-subtle)',
          color: 'var(--text-muted)', cursor: 'pointer',
        }}>清空</button>
      </div>

      <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexWrap: 'wrap', gap: 4, alignContent: 'flex-start' }}>
        {filtered.map(i => {
          const checked = selected.includes(i.name);
          return (
            <label key={i.name} style={{
              display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px',
              borderRadius: 5, fontSize: 'var(--fs-xs)', cursor: 'pointer',
              background: checked ? 'rgba(212,168,83,0.18)' : 'transparent',
              border: `1px solid ${checked ? 'rgba(212,168,83,0.44)' : 'var(--border-subtle)'}`,
              color: checked ? 'var(--accent-gold)' : 'var(--text-secondary)',
              transition: 'all 0.15s',
            }}>
              <input type="checkbox" checked={checked}
                onChange={() => onToggle(i.name, !checked)}
                style={{ display: 'none' }} />
              {i.name}
              {i.change != null && (
                <span style={{ fontSize: 10, color: i.change >= 0 ? 'var(--accent-red)' : 'var(--accent-green)' }}>
                  {i.change >= 0 ? '+' : ''}{i.change.toFixed(1)}
                </span>
              )}
            </label>
          );
        })}
      </div>
    </div>
  );
}

// ── 季节性热力图 ──
function SeasonalHeatmap({ heatmapData, pairLabels }) {
  const chartRef = useRef(null);

  useEffect(() => {
    if (!chartRef.current || !heatmapData.length) return;
    const chart = echarts.init(chartRef.current, 'df-dark');

    const data = heatmapData.map(d => [d.month - 1, pairLabels.indexOf(d.pair), d.corr]);

    chart.setOption({
      tooltip: {
        formatter: p => {
          if (!p.data) return '';
          const pair = pairLabels[p.data[1]];
          const corr = p.data[2];
          const strength = Math.abs(corr) > 0.7 ? '强联动' : Math.abs(corr) > 0.4 ? '中等' : '弱联动';
          return `<b>${pair}</b><br/>${MONTH_NAMES[p.data[0]]}: ${corr >= 0 ? '+' : ''}${corr.toFixed(4)}<br/><span style="color:${corr >= 0 ? '#E85050' : '#3DBB6E'}">${strength}</span>`;
        },
        backgroundColor: 'rgba(26,47,42,0.95)', borderColor: 'rgba(212,168,83,0.2)',
        textStyle: { color: '#CBC0B0' }, extraCssText: 'border-radius:8px;padding:10px 14px;',
      },
      grid: { left: 160, right: 50, top: 30, bottom: 50 },
      xAxis: { type: 'category', data: MONTH_NAMES, axisLabel: { fontSize: 12, color: '#CBC0B0' } },
      yAxis: { type: 'category', data: pairLabels, axisLabel: { fontSize: 11, color: '#CBC0B0', width: 150, overflow: 'truncate' } },
      visualMap: {
        min: -0.8, max: 0.8, calculable: true, orient: 'vertical', right: 4, bottom: 30,
        inRange: { color: ['#3DBB6E', '#5B8FA8', '#D4D4D4', '#D4A853', '#E85050'] },
        textStyle: { color: '#CBC0B0', fontSize: 11 },
      },
      series: [{
        type: 'heatmap', data,
        label: { show: true, formatter: p => p.data[2] != null ? p.data[2].toFixed(2) : '', fontSize: 10, color: '#fff' },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgb(0,0,0/0.8)' } },
      }],
    }, { notMerge: true });
    return () => chart.dispose();
  }, [heatmapData, pairLabels]);

  const h = Math.max(300, pairLabels.length * 36 + 80);

  if (!heatmapData.length) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
      选择行业后点击「开始分析」查看季节性联动热力图
    </div>;
  }
  return <div ref={chartRef} style={{ width: '100%', height: h }} />;
}

// ── 排行表 ──
function StrengthRankingTable({ ranking, peakMonths, valleyMonths }) {
  if (!ranking.length) return null;
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--fs-sm)' }}>
        <thead>
          <tr>
            {['排名','行业对','波幅','峰值月','谷值月','峰值联动','谷值联动'].map(h => (
              <th key={h} style={{ textAlign: h === '排名' || h === '行业对' ? 'left' : 'right',
                padding: '6px 8px', fontSize: 'var(--fs-xs)', color: 'var(--text-muted)',
                borderBottom: '1px solid var(--border-subtle)' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ranking.slice(0, 10).map((item, idx) => {
            const peak = peakMonths[item.pair] || {};
            const valley = valleyMonths[item.pair] || {};
            return (
              <tr key={item.pair} style={idx === 0 ? { background: 'var(--shadow-glow)' } : {}}>
                <td style={{ padding: '6px 8px', fontWeight: 700 }}>{idx + 1}</td>
                <td style={{ padding: '6px 8px', fontWeight: 600 }}>{item.pair}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700, color: 'var(--accent-gold)' }}>{item.amplitude.toFixed(4)}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}><span style={{ padding: '2px 6px', borderRadius: 4, background: 'rgba(232,80,80,0.12)', color: '#E85050', fontSize: 'var(--fs-xs)' }}>{peak.month_name || '—'}</span></td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}><span style={{ padding: '2px 6px', borderRadius: 4, background: 'rgba(61,187,110,0.12)', color: '#3DBB6E', fontSize: 'var(--fs-xs)' }}>{valley.month_name || '—'}</span></td>
                <td style={{ padding: '6px 8px', textAlign: 'right', color: '#E85050', fontWeight: 600 }}>{peak.corr != null ? `+${peak.corr.toFixed(4)}` : '—'}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right' }}>{valley.corr != null ? (valley.corr >= 0 ? '+' : '') + valley.corr.toFixed(4) : '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── 剖面折线图 ──
function PairProfileChart({ profile, peakMonths, valleyMonths }) {
  const chartRef = useRef(null);
  const pairs = Object.keys(profile);
  const [activePair, setActivePair] = useState(pairs[0] || null);
  const [multiPairs, setMultiPairs] = useState(pairs.slice(0, 3));

  useEffect(() => {
    if (!chartRef.current || !multiPairs.length) return;
    const chart = echarts.init(chartRef.current, 'df-dark');
    const colors = ['#D4A853','#C47B7B','#7BAAC4','#7BC47B','#9B7EC8','#C4A87B','#A87BC4','#7BC4B8'];

    const series = multiPairs.map((pair, idx) => {
      const data = profile[pair] || {};
      const values = [];
      for (let m = 1; m <= 12; m++) {
        values.push(data[String(m)] ?? null);
      }
      const displayName = pair.replace('(,', '').replace(', ', ' ↔ ').replace(')', '');
      return {
        type: 'line', name: displayName, data: values, smooth: true,
        lineStyle: { color: colors[idx % colors.length], width: 2 },
        itemStyle: { color: colors[idx % colors.length] },
        symbol: 'circle', symbolSize: 5, connectNulls: true,
      };
    });

    chart.setOption({
      tooltip: { trigger: 'axis',
        backgroundColor: 'rgba(26,47,42,0.95)', borderColor: 'rgba(212,168,83,0.2)',
        textStyle: { color: '#CBC0B0' }, extraCssText: 'border-radius:8px;padding:10px 14px;' },
      legend: { top: 4, textStyle: { color: '#CBC0B0', fontSize: 11 }, itemWidth: 16, itemHeight: 8 },
      grid: { left: 50, right: 20, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: MONTH_NAMES, axisLabel: { fontSize: 12 } },
      yAxis: { type: 'value', axisLabel: { fontSize: 11, formatter: v => v.toFixed(2) },
        splitLine: { lineStyle: { color: 'rgba(212,168,83,0.06)' } } },
      series,
    }, { notMerge: true });
    return () => chart.dispose();
  }, [profile, multiPairs]);

  if (!pairs.length) return null;

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
        {pairs.slice(0, 15).map(pair => {
          const checked = multiPairs.includes(pair);
          const shortName = pair.replace('(,', '').replace(', ', ' ↔ ').replace(')', '');
          return (
            <label key={pair} style={{
              display: 'inline-flex', alignItems: 'center', gap: 3, padding: '2px 6px',
              borderRadius: 4, fontSize: 'var(--fs-xs)', cursor: 'pointer',
              background: checked ? 'rgba(212,168,83,0.18)' : 'transparent',
              border: `1px solid ${checked ? 'rgba(212,168,83,0.4)' : 'var(--border-subtle)'}`,
              color: checked ? 'var(--accent-gold)' : 'var(--text-secondary)',
              transition: 'all 0.15s',
            }}>
              <input type="checkbox" checked={checked}
                onChange={() => setMultiPairs(checked ? multiPairs.filter(p => p !== pair) : [...multiPairs, pair].slice(0, 6))}
                style={{ display: 'none' }} />
              {shortName}
            </label>
          );
        })}
      </div>
      <div ref={chartRef} style={{ width: '100%', height: 280 }} />
    </div>
  );
}

// ── 主组件 ──
export default function SeasonalCorrelation({ industries: allIndustries }) {
  const [selectedIndustries, setSelectedIndustries] = useState([]);
  const [resultData, setResultData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);

  const handleToggle = useCallback((name, checked, presetNames) => {
    if (presetNames) {
      setSelectedIndustries(presetNames.filter(n => allIndustries.some(i => i.name === n)));
      setResultData(null);
      return;
    }
    setSelectedIndustries(prev => {
      const next = checked ? [...prev, name] : prev.filter(n => n !== name);
      setResultData(null);
      return next;
    });
  }, [allIndustries]);

  const handleAnalyze = useCallback(async () => {
    if (selectedIndustries.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const { data: raw, updatedAt: ts } = await mcp.callWithMeta('industry_seasonal_corr', {
        industries: selectedIndustries.join(','), corr_method: 'pearson', min_years: 3,
      });
      setUpdatedAt(ts);
      const parsed = JSON.parse(raw);
      if (parsed.error) { setError(parsed.error); setResultData(null); }
      else { setResultData(parsed); }
    } catch (e) { setError(e.message); setResultData(null); }
    setLoading(false);
  }, [selectedIndustries]);

  const heatmapData = resultData?.heatmap_data || [];
  const pairLabels = useMemo(() => {
    const seen = new Set();
    return heatmapData.filter(d => { if (seen.has(d.pair)) return false; seen.add(d.pair); return true; }).map(d => d.pair);
  }, [heatmapData]);

  const profile = resultData?.seasonal_profile || {};
  const peakMonths = resultData?.peak_months || {};
  const valleyMonths = resultData?.valley_months || {};
  const ranking = resultData?.strength_ranking || [];
  const meta = resultData?.meta || {};

  return (
    <div>
      {/* 标题 */}
      <div style={{ marginBottom: 16 }}>
        <span style={{
          display: 'inline-flex', padding: '4px 12px',
          background: 'rgba(212,168,83,0.08)', border: '1px solid rgba(212,168,83,0.2)',
          borderRadius: 16, fontSize: 'var(--fs-sm)', fontWeight: 600, color: 'var(--accent-gold)', marginBottom: 6,
        }}>🌿 季节性联动</span>
        <h2 style={{ fontSize: 'var(--fs-lg)', fontWeight: 700 }}>
          行业间 <span style={{ color: 'var(--accent-gold)' }}>季节性相关性</span> 分析
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-sm)', marginTop: 2 }}>
          选择2+行业 → 按年度区分月度切片 → 横向比较识别季节性联动规律
        </p>
      </div>

      {/* 选择器 + 按钮 */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 16, alignItems: 'flex-start' }}>
        <div style={{ flex: 1, maxWidth: 420 }}>
          <SeasonalIndustryPicker allIndustries={allIndustries} selected={selectedIndustries} onToggle={handleToggle} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button onClick={handleAnalyze} disabled={selectedIndustries.length < 2 || loading} style={{
            padding: '10px 24px', borderRadius: 8, fontSize: 'var(--fs-base)', fontWeight: 700,
            background: selectedIndustries.length >= 2 && !loading ? 'rgba(212,168,83,0.2)' : 'rgba(212,168,83,0.08)',
            border: `1.5px solid ${selectedIndustries.length >= 2 && !loading ? 'rgba(212,168,83,0.4)' : 'var(--border-subtle)'}`,
            color: selectedIndustries.length >= 2 && !loading ? 'var(--accent-gold)' : 'var(--text-muted)',
            cursor: selectedIndustries.length >= 2 && !loading ? 'pointer' : 'not-allowed',
            transition: 'all 0.2s', minWidth: 120,
          }}>{loading ? '⏳ 计算中...' : '🔍 开始分析'}</button>
          <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>
            {selectedIndustries.length < 2
              ? `还需选择 ${2 - selectedIndustries.length} 个行业`
              : `${selectedIndustries.length} 行业 · ${Math.floor(selectedIndustries.length * (selectedIndustries.length - 1) / 2)} 对组合`}
          </span>
          {error && <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--accent-red)' }}>{error}</span>}
        </div>
      </div>

      {/* 结果 */}
      {resultData && (
        <div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 12, fontSize: 'var(--fs-xs)', color: 'var(--text-secondary)', alignItems: 'center' }}>
            <span>{meta.n_years}年({meta.year_range?.[0]}~{meta.year_range?.[1]})</span>
            <span>· {meta.industries?.length}行业</span>
            <span>· {meta.n_pairs}行业对</span>
            <span>· {meta.method}</span>
            {meta.elapsed_seconds && <span>· {meta.elapsed_seconds}s</span>}
            <UpdateTimestamp updatedAt={updatedAt} />
          </div>

          <CardWrapper style={{ padding: 'var(--sp-xl)', marginBottom: 20 }}>
            <h3 style={{ fontSize: 'var(--fs-base)', fontWeight: 600, marginBottom: 10 }}>
              🗓️ 月度联动热力图 <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>
                · 横轴月份 · 纵轴行业对 · 颜色=联动强度
              </span>
            </h3>
            <ErrorBoundary><SeasonalHeatmap heatmapData={heatmapData} pairLabels={pairLabels} /></ErrorBoundary>
          </CardWrapper>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 20 }}>
            <CardWrapper style={{ padding: 'var(--sp-lg)' }}>
              <h3 style={{ fontSize: 'var(--fs-base)', fontWeight: 600, marginBottom: 10 }}>
                📊 季节性联动强度排行 <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>
                  · 峰谷波幅 = 峰值月相关 - 谷值月相关
                </span>
              </h3>
              <StrengthRankingTable ranking={ranking} peakMonths={peakMonths} valleyMonths={valleyMonths} />
            </CardWrapper>

            <CardWrapper style={{ padding: 'var(--sp-lg)' }}>
              <h3 style={{ fontSize: 'var(--fs-base)', fontWeight: 600, marginBottom: 10 }}>
                📈 联动剖面折线图 <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>
                  · 勾选行业对查看月度联动曲线
                </span>
              </h3>
              <PairProfileChart profile={profile} peakMonths={peakMonths} valleyMonths={valleyMonths} />
            </CardWrapper>
          </div>
        </div>
      )}
    </div>
  );
}
