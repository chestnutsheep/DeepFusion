import {useMCP} from '../hooks/useMCP.js';
import MacroSnapshot from '../components/Macro/MacroSnapshot.jsx';
import CyclePage from '../components/Macro/CyclePage.jsx';
import DataCard from '../components/common/DataCard.jsx';
import ErrorBoundary from '../components/common/ErrorBoundary.jsx';
import {KITCHIN_CONFIG} from '../configs/kitchin.js';
import {JUGLAR_CONFIG} from '../configs/juglar.js';
import {KUZNETS_CONFIG} from '../configs/kuznets.js';
import {KONDRATIEV_CONFIG} from '../configs/kondratiev.js';
import {useEffect, useMemo, useRef} from 'react';
import * as echarts from 'echarts';

const CYCLES = [
  { id: 'kitchin', label: '基钦', config: KITCHIN_CONFIG },
  { id: 'juglar', label: '朱格拉', config: JUGLAR_CONFIG },
  { id: 'kuznets', label: '库兹涅茨', config: KUZNETS_CONFIG },
  { id: 'kondratiev', label: '康波', config: KONDRATIEV_CONFIG },
];

const COVERAGE_TOOLS = [
  { tool: 'data_kitchin', extTool: 'data_kitchin_extended', key: 'kitchin', label: '基钦', color: '#5bba57' },
  { tool: 'data_juglar', extTool: 'data_juglar_extended', key: 'juglar', label: '朱格拉', color: '#D4A853' },
  { tool: 'data_kuznets', extTool: 'data_kuznets_extended', key: 'kuznets', label: '库兹涅茨', color: '#42a2dc' },
  { tool: 'data_kondratiev', extTool: null, key: 'kondratiev', label: '康波', color: '#ff9bd0' },
];

/** 相位→颜色/符号 */
const PHASE_STYLE = {
  1: { bg: 'rgba(91,186,87,0.15)', border: '#5bba57', label: '复苏', arrow: '↗' },
  2: { bg: 'rgba(212,168,83,0.18)', border: '#D4A853', label: '繁荣', arrow: '↑' },
  3: { bg: 'rgba(248,81,73,0.15)', border: '#cc4842', label: '衰退', arrow: '↘' },
  4: { bg: 'rgba(136,136,136,0.15)', border: '#888', label: '萧条', arrow: '↓' },
  0: { bg: 'rgba(136,136,136,0.08)', border: '#555', label: '未知', arrow: '·' },
};

function MethodCards() {
  const pcaResult = useMCP('data_kondratiev', { method: 'pca' });
  const waveletResult = useMCP('data_kondratiev', { method: 'wavelet' });
  const bandpassResult = useMCP('data_kondratiev', { method: 'bandpass' });

  const parseResult = (raw) => {
    if (!raw) return {};
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed[parsed.length - 1];
      return parsed;
    } catch { return {}; }
  };

  const pca = parseResult(pcaResult.data);
  const wavelet = parseResult(waveletResult.data);
  const bandpass = parseResult(bandpassResult.data);

  const methods = [
    { ...KONDRATIEV_CONFIG.methodMetrics[0], value: pca.confidence, phase: pca.phase, phaseName: pca.phase_name,
      globalPhase: pca.global_phase, globalPhaseName: pca.global_phase_name,
      chinaPhase: pca.china_phase, chinaPhaseName: pca.china_phase_name },
    { ...KONDRATIEV_CONFIG.methodMetrics[1], value: wavelet.confidence, phase: wavelet.phase, phaseName: wavelet.phase_name,
      globalPhase: wavelet.global_phase, globalPhaseName: wavelet.global_phase_name,
      chinaPhase: wavelet.china_phase, chinaPhaseName: wavelet.china_phase_name },
    { ...KONDRATIEV_CONFIG.methodMetrics[2], value: bandpass.confidence, phase: bandpass.phase, phaseName: bandpass.phase_name,
      globalPhase: bandpass.global_phase, globalPhaseName: bandpass.global_phase_name,
      chinaPhase: bandpass.china_phase, chinaPhaseName: bandpass.china_phase_name },
  ];

  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10, color: 'var(--accent-gold)' }}>
        🔬 三种计算方法对比
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {methods.map((m) => {
          const ps = PHASE_STYLE[m.phase] || PHASE_STYLE[0];
          const gps = PHASE_STYLE[m.globalPhase] || PHASE_STYLE[0];
          const cps = PHASE_STYLE[m.chinaPhase] || PHASE_STYLE[0];
          return (
            <DataCard
              key={m.method}
              label={m.label}
              value={m.value != null ? m.value * 100 : null}
              unit="%"
              higherBetter={m.higherBetter}
              decimals={1}
              detail={m.detail}
              source={
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {m.globalPhaseName && (
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 2,
                      background: gps.bg, border: `1px solid ${gps.border}`, borderRadius: 3,
                      padding: '1px 5px', fontSize: 11, fontWeight: 600, color: gps.border,
                    }}>
                      🌍{gps.arrow} {m.globalPhaseName}
                    </span>
                  )}
                  {m.chinaPhaseName && (
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 2,
                      background: cps.bg, border: `1px solid ${cps.border}`, borderRadius: 3,
                      padding: '1px 5px', fontSize: 11, fontWeight: 600, color: cps.border,
                    }}>
                      🇨🇳{cps.arrow} {m.chinaPhaseName}
                    </span>
                  )}
                </div>
              }
            />
          );
        })}
      </div>
    </div>
  );
}

function CoverageGrid() {
  const hooks = COVERAGE_TOOLS.map(c => {
    const params = c.key === 'kondratiev' ? { method: 'pca' } : {};
    return { ...c, result: useMCP(c.tool, params), extResult: c.extTool ? useMCP(c.extTool, {}) : null };
  });

  const parse = (raw) => {
    if (!raw) return {};
    if (typeof raw === 'string') {
      try { const arr = JSON.parse(raw); return arr?.[arr.length - 1] || {}; } catch {}
    }
    return {};
  };

  const getYearRange = (raw) => {
    if (!raw) return '';
    try {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr) && arr.length > 1) return `${arr[0].period}~${arr[arr.length - 1].period}`;
    } catch {}
    return '';
  };

  const rows = hooks.map(h => {
    const data = parse(h.result.data);
    const extRange = h.extResult ? getYearRange(h.extResult.data) : '';
    const nbsRange = getYearRange(h.result.data);
    // 康波显示全球+中国双线
    const isKondratiev = h.key === 'kondratiev';
    const phaseDisplay = isKondratiev
      ? (data.global_phase_name || data.china_phase_name
          ? `🌍${data.global_phase_name || '—'} / 🇨🇳${data.china_phase_name || '—'}`
          : data.phase_name || '—')
      : (data.phase_name || data.cycle_phase_name || '—');
    return {
      label: h.label, color: h.color,
      phase: phaseDisplay,
      confidence: data.confidence != null ? (data.confidence * 100).toFixed(1) + '%' : '—',
      period: data.dominant_period != null ? data.dominant_period : '—',
      nbsRange, extRange,
    };
  });

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${rows.length}, 1fr)`,
        gap: 12,
      }}
    >
      {rows.map((r, i) => (
        <div key={i}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, color: r.color }}>{r.label}</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.8 }}>
            <div>相位: <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{r.phase}</span></div>
            <div>置信度: <span style={{ color: 'var(--accent-gold)' }}>{r.confidence}</span></div>
            <div>周期: <span style={{ color: 'var(--text-primary)' }}>{r.period}</span></div>
            <div>覆盖: <span style={{ color: 'var(--text-primary)' }}>{r.nbsRange || '—'}</span></div>
            {r.extRange && <div style={{ color: '#5bba57' }}>扩展: {r.extRange}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * 四周期嵌套图：使用连续信号 [-2,+2] 替代离散哑变量，
 * 以平滑曲线直观展示周期嵌套关系与相位演进
 */
const NEST_COLORS = {
  kitchin: '#5bba57',
  juglar: '#D4A853',
  kuznets: '#8fd6ff',
  kondratiev: '#f689c4',
};
const NEST_LABELS = {
  kitchin: '基钦',
  juglar: '朱格拉',
  kuznets: '库兹涅茨',
  kondratiev: '康波',
};

function CycleNesting() {
  const { data: rawData, isLoading } = useMCP('cycle_nesting', {});

  const rows = useMemo(() => {
    if (!rawData) return [];
    try {
      const parsed = JSON.parse(rawData);
      return Array.isArray(parsed) ? parsed : [];
    } catch { return []; }
  }, [rawData]);

  const chartRef = useRef(null);

  useEffect(() => {
    if (!chartRef.current || !rows.length) return;
    const chart = echarts.init(chartRef.current, 'df-dark');
    const dates = rows.map(r => r.period);
    const cycleIds = ['kondratiev', 'kuznets', 'juglar', 'kitchin'];

    // 优先使用连续信号，回退到离散信号
    const getData = (id) => rows.map(r => r[`${id}_cont`] ?? r[`${id}_signal`] ?? 0);

    const option = {
      tooltip: {
        trigger: 'axis',
        formatter(params) {
          let s = `<b>${params[0].axisValue}</b><br/>`;
          for (const p of params) {
            const val = p.value;
            const absV = Math.abs(val);
            let label;
            if (absV > 1.5) label = val > 0 ? '繁荣' : '萧条';
            else if (absV > 0.5) label = val > 0 ? '复苏' : '衰退';
            else label = '过渡';
            s += `${p.marker} ${p.seriesName}: ${label} (${val > 0 ? '+' : ''}${val.toFixed(2)})<br/>`;
          }
          return s;
        },
      },
      legend: { data: cycleIds.map(id => NEST_LABELS[id]), bottom: 0 },
      grid: { left: '8%', right: '5%', top: '8%', bottom: '18%', containLabel: true },
      xAxis: { type: 'category', data: dates, axisLabel: { rotate: 45, fontSize: 10 } },
      yAxis: {
        type: 'value', min: -2.5, max: 2.5,
        axisLabel: {
          formatter(v) {
            if (v >= 1.5) return '繁荣';
            if (v >= 0.5) return '复苏';
            if (v > -0.5) return '—';
            if (v > -1.5) return '衰退';
            return '萧条';
          },
          fontSize: 10,
        },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 16, bottom: 24,
          borderColor: 'rgba(212,168,83,0.12)', backgroundColor: 'rgba(26,47,42,0.6)' },
      ],
      // 零线标记
      series: [
        // 零线参考
        {
          name: '零线', type: 'line', data: dates.map(() => 0),
          lineStyle: { color: 'rgba(212,168,83,0.15)', width: 1, type: 'dashed' },
          symbol: 'none', silent: true, tooltip: { show: false },
          z: 0,
        },
        // 四周期连续信号
        ...cycleIds.map(id => ({
          name: NEST_LABELS[id],
          type: 'line',
          data: getData(id),
          smooth: true,
          lineStyle: { color: NEST_COLORS[id], width: id === 'kondratiev' ? 3 : 2 },
          areaStyle: id === 'kondratiev'
            ? { opacity: 0.06, color: NEST_COLORS[id] }
            : { opacity: 0.03, color: NEST_COLORS[id] },
          symbol: 'none',
          z: id === 'kondratiev' ? 4 : 2,
        })),
      ],
    };
    chart.setOption(option);
    return () => chart.dispose();
  }, [rows]);

  if (isLoading) return <div style={{ padding: 20 }}>加载中...</div>;
  if (!rows.length) return <div style={{ padding: 20 }}>暂无数据</div>;

  return <div ref={chartRef} style={{ width: '100%', height: 400 }} />;
}

export default function MacroPage() {
  return (
    <ErrorBoundary>
    <div>
      <MacroSnapshot />
      <hr className="section-divider" />
      {CYCLES.map((c, i) => (
        <div key={c.id} id={c.id}>
          <ErrorBoundary>
            <CyclePage config={c.config} showTitle={c.label} />
          </ErrorBoundary>
          {c.id === 'kondratiev' && <ErrorBoundary><MethodCards /></ErrorBoundary>}
          {i < CYCLES.length - 1 && <hr className="section-divider-thin" />}
        </div>
      ))}

      {/* 周期覆盖 — Sidebar 子导航 "宏观覆盖" 锚点 */}
      <hr className="section-divider" />
      <div id="coverage">
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 12, marginTop: 8 }}>周期覆盖</h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
          四周期当前相位一览
        </p>
        <ErrorBoundary><CoverageGrid /></ErrorBoundary>
      </div>

      {/* 周期嵌套图 — 四周期相位哑变量对比 */}
      <hr className="section-divider" />
      <div id="nesting">
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 12, marginTop: 8 }}>周期嵌套</h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
          四周期相位信号对比：+2 繁荣 / +1 复苏 / -1 衰退 / -2 萧条
        </p>
        <ErrorBoundary><CycleNesting /></ErrorBoundary>
      </div>
    </div>
    </ErrorBoundary>
  );
}
