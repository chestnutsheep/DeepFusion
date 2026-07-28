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
import CardWrapper from '../components/common/CardWrapper.jsx';

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

/**
 * 年份坐标轴标签格式化：5 年为一个标准刻度。
 * 头尾年（首/末）用正常字号，5 年刻度上的年份用小 2 号字，其余年份仅留刻度不标文字。
 */
function yearAxisLabelFormatter(dates) {
  return (value, index) => {
    const s = String(value);
    const year = s.slice(0, 4);
    if (!/^\d{4}$/.test(year)) return s;
    const disp = s.length > 4 ? year : s;
    const total = dates.length;
    if (index === 0 || index === total - 1) return disp;
    const y = parseInt(year, 10);
    if (y % 5 === 0) return `{mid|${disp}}`;
    return '';
  };
}

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
    { ...KONDRATIEV_CONFIG.methodMetrics[0], value: pca.confidence != null ? pca.confidence : null, phase: pca.phase || 0, phaseName: pca.phase_name || '—',
      globalPhase: pca.global_phase || 0, globalPhaseName: pca.global_phase_name || '',
      chinaPhase: pca.china_phase || 0, chinaPhaseName: pca.china_phase_name || '',
      pcaVar: pca.pca_variance_ratio },
    { ...KONDRATIEV_CONFIG.methodMetrics[1], value: wavelet.confidence != null ? wavelet.confidence : null, phase: wavelet.phase || 0, phaseName: wavelet.phase_name || '—',
      globalPhase: wavelet.global_phase || 0, globalPhaseName: wavelet.global_phase_name || '',
      chinaPhase: wavelet.china_phase || 0, chinaPhaseName: wavelet.china_phase_name || '',
      pcaVar: wavelet.pca_variance_ratio },
    { ...KONDRATIEV_CONFIG.methodMetrics[2], value: bandpass.confidence != null ? bandpass.confidence : null, phase: bandpass.phase || 0, phaseName: bandpass.phase_name || '—',
      globalPhase: bandpass.global_phase || 0, globalPhaseName: bandpass.global_phase_name || '',
      chinaPhase: bandpass.china_phase || 0, chinaPhaseName: bandpass.china_phase_name || '',
      pcaVar: bandpass.pca_variance_ratio },
  ];

  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 'var(--fs-base)', fontWeight: 700, marginBottom: 'var(--sp-sm)', color: 'var(--accent-gold)' }}>
        三种计算方法对比
      </h3>
      <p style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)', marginBottom: 12, lineHeight: 1.6 }}>
        三种方法从不同数学视角提取同一组数据的40-70年长波成分，结果应互相印证。
        <b style={{ color: 'var(--text-primary)' }}>PCA频谱法</b>用主成分分析降维后做带通滤波（覆盖度=PCA第一主成分解释的方差比例）；
        <b style={{ color: 'var(--text-primary)' }}>小波分析法</b>用Morlet变换在时频域定位周期位置；
        <b style={{ color: 'var(--text-primary)' }}>带通滤波法</b>用Butterworth滤波器直接提取长波。
        三者置信度含义不同，不可直接横向比较数值大小。
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--sp-md)' }} className="data-grid-responsive">
        {methods.map((m) => {
          const ps = PHASE_STYLE[m.phase] || PHASE_STYLE[0];
          const gps = PHASE_STYLE[m.globalPhase] || PHASE_STYLE[0];
          const cps = PHASE_STYLE[m.chinaPhase] || PHASE_STYLE[0];
          const phaseTag = m.phaseName && m.phaseName !== '—'
            ? <span style={{ background: ps.bg, border: `1px solid ${ps.border}`, borderRadius: 4, padding: '2px 8px', fontSize: 'var(--fs-xs)', fontWeight: 700, color: ps.border }}>{ps.arrow} {m.phaseName}</span>
            : null;
          return (
            <DataCard
              key={m.method}
              label={m.label}
              value={m.value != null ? m.value * 100 : null}
              unit="%"
              higherBetter={m.higherBetter}
              decimals={1}
              detail={`${m.detail || ''}${m.globalPhaseName ? ` | 🌍${gps.arrow}${m.globalPhaseName}` : ''}${m.chinaPhaseName ? ` | 🇨🇳${cps.arrow}${m.chinaPhaseName}` : ''}`}
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
      if (Array.isArray(arr) && arr.length > 1) return `${arr[0].period} ~ ${arr[arr.length - 1].period}`;
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
      : (data.phase_name || data.cycle_phase_name || data.stage_name || '—');
    // 覆盖范围：优先用扩展数据（更长），回退到 NBS
    const coverageRange = extRange || nbsRange || '—';
    // 置信度：有值才显示
    const hasConfidence = data.confidence != null && !isNaN(data.confidence);
    return {
      label: h.label, color: h.color,
      phase: phaseDisplay,
      confidence: hasConfidence ? (data.confidence * 100).toFixed(1) + '%' : null,
      period: data.dominant_period != null ? data.dominant_period : '—',
      coverageRange,
    };
  });

  return (
    <div
      className="coverage-grid"
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${rows.length}, 1fr)`,
        gap: 'var(--sp-md)',
      }}
    >
      {rows.map((r, i) => (
        <div key={i}>
          <div style={{ fontSize: 'var(--fs-base)', fontWeight: 700, marginBottom: 8, color: r.color }}>{r.label}</div>
          <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', lineHeight: 1.8 }}>
            <div>相位: <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{r.phase}</span></div>
            {r.confidence != null && (
              <div>置信度: <span style={{ color: 'var(--accent-gold)' }}>{r.confidence}</span></div>
            )}
            <div>周期: <span style={{ color: 'var(--text-primary)' }}>{r.period}</span></div>
            <div>覆盖: <span style={{ color: 'var(--text-primary)' }}>{r.coverageRange}</span></div>
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * 四周期嵌套图：使用 composite_z（原始标准化 zscore）绘制平滑曲线，
 * 直观展示周期嵌套关系与波动形态。
 * 旧逻辑（phase_angle 转换为 _cont 信号）已存档，不再接入绘图。
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

// ── 存档：相位角转换绘图函数（供后续对比验证，不再接入） ──
// const _RESERVED_getContData = (id) => rows.map(r => r[`${id}_cont`] ?? r[`${id}_signal`] ?? 0);
// ── 存档结束 ──

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

    // 直接使用 composite_z（原始标准化 zscore），连续平滑
    const getData = (id) => rows.map(r => r[`${id}_z`] ?? null);

    // 自动计算 Y 轴范围
    const allVals = cycleIds.flatMap(id => getData(id).filter(v => v != null));
    const yMin = allVals.length ? Math.floor(Math.min(...allVals) * 2) / 2 - 0.5 : -3;
    const yMax = allVals.length ? Math.ceil(Math.max(...allVals) * 2) / 2 + 0.5 : 3;

    const option = {
      tooltip: {
        trigger: 'axis',
        formatter(params) {
          let s = `<b>${params[0].axisValue}</b><br/>`;
          for (const p of params) {
            if (p.seriesName === '零线') continue;
            const val = p.value;
            if (val == null) continue;
            // 从 rows 找到对应相位名
            const idx = p.dataIndex;
            const cid = Object.keys(NEST_LABELS).find(k => NEST_LABELS[k] === p.seriesName) || '';
            const phaseName = rows[idx]?.[`${cid}_name`] || '—';
            s += `${p.marker} ${p.seriesName}: ${phaseName} (z=${val > 0 ? '+' : ''}${val.toFixed(2)})<br/>`;
          }
          return s;
        },
      },
      legend: { data: cycleIds.map(id => NEST_LABELS[id]), bottom: 0 },
      grid: { left: '8%', right: '5%', top: '8%', bottom: '18%', containLabel: true },
      xAxis: {
        type: 'category', data: dates,
        axisLabel: {
          interval: 0, color: '#CBC0B0', fontSize: 12,
          formatter: yearAxisLabelFormatter(dates),
          rich: { mid: { fontSize: 10, color: 'rgba(203,192,176,0.65)' } },
        },
      },
      yAxis: {
        type: 'value', min: yMin, max: yMax,
        axisLabel: {
          formatter(v) {
            if (v >= 2) return '繁荣';
            if (v >= 0.5) return '复苏';
            if (v > -0.5) return '中性';
            if (v > -2) return '衰退';
            return '萧条';
          },
          fontSize: 'var(--fs-xs)',
        },
      },
      dataZoom: [
        { type: 'inside', start: 80, end: 100 },
        { type: 'slider', start: 80, end: 100, height: 16, bottom: 24,
          borderColor: 'rgba(212,168,83,0.12)', backgroundColor: 'rgba(26,47,42,0.6)' },
      ],
      series: [
        // 零线参考
        {
          name: '零线', type: 'line', data: dates.map(() => 0),
          lineStyle: { color: 'rgb(248 241 232 / 0.86)', width: 2, type: 'dashed' },
          symbol: 'none', silent: true, tooltip: { show: false },
          z: 0,
        },
        // 四周期 composite_z 原始曲线
        ...cycleIds.map(id => ({
          name: NEST_LABELS[id],
          type: 'line',
          data: getData(id),
          smooth: true,
          connectNulls: true,
          lineStyle: { color: NEST_COLORS[id], width: id === 'kondratiev' ? 3.5 : 2.5 },
          areaStyle: id === 'kondratiev'
            ? { opacity: 0.06, color: NEST_COLORS[id] }
            : { opacity: 0.03, color: NEST_COLORS[id] },
          symbol: 'none',
          z: id === 'kondratiev' ? 4 : 2,
        })),
      ],
    };
    chart.setOption(option);

    // ResizeObserver 监听容器尺寸变化（侧边栏展开/收起时自动 resize）
    let ro;
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => chart.resize());
      ro.observe(chartRef.current);
    }

    return () => {
      if (ro) ro.disconnect();
      chart.dispose();
    };
  }, [rows]);

  if (isLoading) return <div style={{ padding: 20 }}>加载中...</div>;
  if (!rows.length) return <div style={{ padding: 20 }}>暂无数据</div>;

  return (
    <CardWrapper hoverable style={{ padding: 'var(--sp-xl)', transition: 'all 0.25s ease' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 'var(--sp-lg)' }}>
        <h3 style={{ fontSize: 'var(--fs-lg)', fontWeight: 700, color: 'var(--accent-gold)' }}>表5：四周期合成Z值嵌套对比</h3>
        <span style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)' }}>数据来源：FRED/世界银行; 手动计算</span>
      </div>
      <div ref={chartRef} style={{ width: '100%', height: 'clamp(320px, 45vh, 500px)' }} />
    </CardWrapper>
  );
}

// ── 相位→甘特图颜色/纹理 ──
const GANTT_PHASE_STYLE = {
  1: { color: '#88c9f4', pattern: '///', label: '复苏' },   // 斜线纹理
  2: { color: '#8dd969', pattern: '===', label: '繁荣' },   // 横线纹理
  3: { color: '#e2da6f', pattern: '\\\\\\', label: '衰退' }, // 反斜线纹理
  4: { color: '#fb7888',    pattern: '...', label: '萧条' },   // 点状纹理
  0: { color: '#333',    pattern: '   ', label: '未知' },
};

/**
 * 四周期相位甘特图：水平条形图，每个周期一行。
 * 改进：
 *  1. 对缺失年份前向填充，保持相位连续性
 *  2. 合并连续相同相位为区间长条，更像甘特图
 *  3. 颜色区分相位，纹理区分周期类型
 */
function CycleGantt() {
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

    const cycleIds = ['kondratiev', 'kuznets', 'juglar', 'kitchin'];
    const years = rows.map(r => r.period);
    const yearSet = [...new Set(years)].sort();

    // ── 1. 前向填充：让各周期相位在数据起始点后保持连续 ──
    // 找到每个周期第一个非零相位年份，之后缺失的继承前一年
    const filledMap = {}; // { period: { kitchin_phase, ... } }
    const lastKnown = {}; // { cid: { phase, name } }
    for (const y of yearSet) {
      const row = rows.find(r => r.period === y);
      const entry = { period: y };
      for (const cid of cycleIds) {
        const ph = row?.[`${cid}_phase`] ?? 0;
        const nm = row?.[`${cid}_name`] || '—';
        if (ph > 0) {
          lastKnown[cid] = { phase: ph, name: nm };
          entry[`${cid}_phase`] = ph;
          entry[`${cid}_name`] = nm;
        } else if (lastKnown[cid]) {
          // 前向填充：继承最近已知相位
          entry[`${cid}_phase`] = lastKnown[cid].phase;
          entry[`${cid}_name`] = lastKnown[cid].name;
        } else {
          entry[`${cid}_phase`] = 0;
          entry[`${cid}_name`] = '—';
        }
      }
      filledMap[y] = entry;
    }

    // ── 2. 合并连续相同相位为区间 ──
    // 对每个周期，扫描年份序列，把连续相同相位合并为 [startIdx, endIdx, cycleIdx, phase, name]
    const seriesData = [];
    for (let ci = 0; ci < cycleIds.length; ci++) {
      const cid = cycleIds[ci];
      let runStart = 0;
      let runPhase = filledMap[yearSet[0]]?.[`${cid}_phase`] ?? 0;
      let runName = filledMap[yearSet[0]]?.[`${cid}_name`] || '—';

      for (let yi = 1; yi <= yearSet.length; yi++) {
        const ph = yi < yearSet.length ? (filledMap[yearSet[yi]]?.[`${cid}_phase`] ?? 0) : -1;
        const nm = yi < yearSet.length ? (filledMap[yearSet[yi]]?.[`${cid}_name`] || '—') : '';
        if (ph !== runPhase) {
          // 结束当前 run
          seriesData.push({
            value: [runStart, ci, yi - 1, runPhase],
            phase: runPhase,
            name: runName,
          });
          runStart = yi;
          runPhase = ph;
          runName = nm;
        }
      }
    }

    const option = {
      tooltip: {
        formatter(params) {
          const d = params.data;
          if (!d) return '';
          const startYear = yearSet[d.value[0]];
          const endYear = yearSet[d.value[2]];
          const yearLabel = startYear === endYear ? startYear : `${startYear} ~ ${endYear}`;
          return `<b>${yearLabel}</b><br/>${NEST_LABELS[cycleIds[d.value[1]]]}: ${d.name}`;
        },
      },
      grid: { left: '8%', right: '8%', top: '5%', bottom: '20%', containLabel: true },
      xAxis: {
        type: 'category',
        data: yearSet,
        axisLabel: {
          interval: 0, color: '#CBC0B0', fontSize: 12,
          formatter: yearAxisLabelFormatter(yearSet),
          rich: { mid: { fontSize: 10, color: 'rgba(203,192,176,0.65)' } },
        },
      },
      yAxis: {
        type: 'category',
        data: cycleIds.map(id => NEST_LABELS[id]),
        inverse: true,
        axisLabel: { fontSize: 12, fontWeight: 600 },
      },
      dataZoom: [
        { type: 'inside', start: 80, end: 100 },
        { type: 'slider', start: 80, end: 100, height: 16, bottom: 24,
          borderColor: 'rgba(212,168,83,0.12)', backgroundColor: 'rgba(26,47,42,0.6)' },
      ],
      visualMap: {
        show: true,
        orient: 'horizontal',
        bottom: 0,
        itemWidth: 18,
        itemHeight: 16,
        textStyle: { color: '#CBC0B0', fontSize: 11 },
        categories: ['复苏', '繁荣', '衰退', '萧条', '未知'],
        inRange: {
          color: ['#88c9f4', '#8dd969', '#e2da6f', '#fb7888', '#333'],
        },
        calculable: false,
        dimension: 3,
      },
      series: [{
        type: 'custom',
        data: seriesData,
        renderItem(params, api) {
          const startIdx = api.value(0);
          const yIdx = api.value(1);
          const endIdx = api.value(2);
          const phase = api.value(3);

          const start = api.coord([startIdx - 0.5, yIdx]);
          const end = api.coord([endIdx + 0.5, yIdx]);
          if (!start || !end) return;

          const style = GANTT_PHASE_STYLE[phase] || GANTT_PHASE_STYLE[0];
          const rectShape = {
            x: start[0],
            y: start[1] - 8,
            width: end[0] - start[0],
            height: 16,
          };

          // 纹理装饰：用 decal pattern 区分
          const decalPatterns = {
            1: { symbol: 'rect', symbolSize: 1, dashArrayX: [2, 3], dashArrayY: [2, 3], rotation: Math.PI / 4, color: 'rgba(255,255,255,0.12)' },
            2: { symbol: 'rect', symbolSize: 1, dashArrayX: [4, 2], dashArrayY: [1, 0], rotation: 0, color: 'rgba(255,255,255,0.15)' },
            3: { symbol: 'rect', symbolSize: 1, dashArrayX: [2, 3], dashArrayY: [2, 3], rotation: -Math.PI / 4, color: 'rgba(255,255,255,0.10)' },
            4: { symbol: 'circle', symbolSize: 1, dashArrayX: [1, 4], dashArrayY: [1, 4], rotation: 0, color: 'rgba(255,255,255,0.08)' },
            0: null,
          };

          return {
            type: 'rect',
            shape: rectShape,
            style: {
              fill: style.color,
              decal: decalPatterns[phase] || undefined,
              opacity: phase > 0 ? 0.9 : 0.25,
            },
            emphasis: {
              style: { opacity: 1, stroke: '#fff', lineWidth: 1 },
            },
          };
        },
        encode: { x: [0, 2], y: 1, tooltip: 3 },
      }],
    };
    chart.setOption(option);

    // ResizeObserver 监听容器尺寸变化（侧边栏展开/收起时自动 resize）
    let ro;
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => chart.resize());
      ro.observe(chartRef.current);
    }

    return () => {
      if (ro) ro.disconnect();
      chart.dispose();
    };
  }, [rows]);

  if (isLoading) return <div style={{ padding: 20 }}>加载中...</div>;
  if (!rows.length) return <div style={{ padding: 20 }}>暂无数据</div>;

  return (
    <CardWrapper hoverable style={{ padding: 'var(--sp-xl)', transition: 'all 0.25s ease' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 'var(--sp-lg)' }}>
        <h3 style={{ fontSize: 'var(--fs-lg)', fontWeight: 700, color: 'var(--accent-gold)' }}>表6：四周期相位演进甘特图</h3>
        <span style={{ fontSize: 'var(--fs-2xs)', color: 'var(--text-muted)' }}>数据来源：FRED/世界银行; 手动计算</span>
      </div>
      <div ref={chartRef} style={{ width: '100%', height: 'clamp(180px, 25vh, 280px)' }} />
    </CardWrapper>
  );
}

/**
 * 四周期互验互斥标签：判断当前四周期相位是否互相印证或矛盾，
 * 帮助用户理解综合结论的可信度。
 *
 * 规则：
 *   - 全部扩张(1/2) → "共振扩张" (强看多信号)
 *   - 全部收缩(3/4) → "共振收缩" (强看空信号)
 *   - 扩张+收缩混合 → "相位分歧" (信号矛盾，需谨慎)
 *   - 3同+1异 → "弱分歧" (主流方向明确但有一周期逆行)
 */
function PhaseConsistency() {
  const { data: rawData } = useMCP('cycle_nesting', {});

  const rows = useMemo(() => {
    if (!rawData) return [];
    try {
      const parsed = JSON.parse(rawData);
      return Array.isArray(parsed) ? parsed : [];
    } catch { return []; }
  }, [rawData]);

  const analysis = useMemo(() => {
    if (!rows.length) return null;
    const latest = rows[rows.length - 1];
    const cycleIds = ['kondratiev', 'kuznets', 'juglar', 'kitchin'];
    const phases = cycleIds.map(cid => latest?.[`${cid}_phase`] ?? 0);
    const names = cycleIds.map(cid => latest?.[`${cid}_name`] ?? '—');

    // 扩张相位(1,2) vs 收缩相位(3,4)
    const expanding = phases.filter(p => p === 1 || p === 2).length;
    const contracting = phases.filter(p => p === 3 || p === 4).length;
    const unknown = phases.filter(p => p === 0).length;

    let verdict, verdictColor, verdictIcon;
    if (unknown >= 2) {
      verdict = '数据不足'; verdictColor = '#888'; verdictIcon = '⚠';
    } else if (expanding === 4) {
      verdict = '共振扩张'; verdictColor = '#5bba57'; verdictIcon = '⬆';
    } else if (contracting === 4) {
      verdict = '共振收缩'; verdictColor = '#f85149'; verdictIcon = '⬇';
    } else if (expanding === 3 && contracting === 1) {
      verdict = '弱分歧(3扩1缩)'; verdictColor = '#D4A853'; verdictIcon = '↗';
    } else if (contracting === 3 && expanding === 1) {
      verdict = '弱分歧(3缩1扩)'; verdictColor = '#D4A853'; verdictIcon = '↘';
    } else {
      verdict = '相位分歧'; verdictColor = '#cc4842'; verdictIcon = '⚡';
    }

    // 各周期简要标签
    const tags = cycleIds.map((cid, i) => {
      const p = phases[i];
      const isExpand = p === 1 || p === 2;
      const style = PHASE_STYLE[p] || PHASE_STYLE[0];
      return { id: cid, label: NEST_LABELS[cid], phase: p, name: names[i], isExpand, style };
    });

    return { verdict, verdictColor, verdictIcon, expanding, contracting, unknown, tags };
  }, [rows]);

  if (!analysis) return null;

  return (
    <CardWrapper style={{ padding: 'var(--sp-lg) var(--sp-xl)', marginTop: 'var(--sp-lg)' }}>
      <div style={{ fontSize: 'var(--fs-base)', fontWeight: 700, color: 'var(--accent-gold)', marginBottom: 10 }}>
        互验互斥判断
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          background: `${analysis.verdictColor}18`, border: `1.5px solid ${analysis.verdictColor}`,
          borderRadius: 'var(--radius-sm)', padding: '6px 16px',
          fontSize: 'var(--fs-md)', fontWeight: 700, color: analysis.verdictColor,
        }}>
          {analysis.verdictIcon} {analysis.verdict}
        </span>
        <span style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)' }}>
          {analysis.expanding}个扩张 · {analysis.contracting}个收缩 · {analysis.unknown}个未知
        </span>
      </div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {analysis.tags.map(t => (
          <span key={t.id} style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            background: t.style.bg, border: `1px solid ${t.style.border}`,
            borderRadius: 4, padding: '3px 10px',
            fontSize: 'var(--fs-sm)', fontWeight: 600, color: t.style.border,
          }}>
            {t.label}: {t.style.arrow} {t.name}
          </span>
        ))}
      </div>
      <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.5 }}>
        共振扩张=四周期同处扩张半周期(复苏/繁荣)，经济上行信号最强；共振收缩=四周期同处收缩半周期(衰退/萧条)，下行风险最大；
        相位分歧=多周期方向矛盾，综合信号弱化，需等待分歧收敛后再做判断。
      </div>
    </CardWrapper>
  );
}

export default function MacroPage() {
  return (
    <ErrorBoundary>
    <div>
      <MacroSnapshot />
      <hr className="section-divider" />

      {/* 周期速览 — 一排四个周期当前相位一览（在具体图表上方） */}
      <div id="coverage" className="section-block">
        <h2 style={{ fontSize: 'var(--fs-xl)', fontWeight: 700, marginBottom: 'var(--sp-lg)', marginTop: 0 }}>周期速览</h2>
        <p style={{ fontSize: 'var(--fs-base)', color: 'var(--text-secondary)', marginBottom: 'var(--sp-lg)' }}>
          四周期当前相位一览
        </p>
        <ErrorBoundary><CoverageGrid /></ErrorBoundary>
      </div>

      <hr className="section-divider" />
      {CYCLES.map((c, i) => (
        <div key={c.id} id={c.id}>
          <ErrorBoundary>
            <CyclePage config={c.config} showTitle={c.label} tableIndex={i + 1} />
          </ErrorBoundary>
          {c.id === 'kondratiev' && <ErrorBoundary><MethodCards /></ErrorBoundary>}
          {i < CYCLES.length - 1 && <hr className="section-divider-thin" />}
        </div>
      ))}

      {/* 周期嵌套图 — 四周期 composite_z 对比 */}
      <hr className="section-divider" />
      <div id="nesting" className="section-block">
        <h2 style={{ fontSize: 'var(--fs-xl)', fontWeight: 700, marginBottom: 'var(--sp-lg)', marginTop: 0 }}>周期嵌套</h2>
        <p style={{ fontSize: 'var(--fs-base)', color: 'var(--text-secondary)', marginBottom: 'var(--sp-lg)' }}>
          四周期合成Z值（composite_z）波动对比：零线以上扩张，以下收缩
        </p>
        <ErrorBoundary><CycleNesting /></ErrorBoundary>
      </div>

      {/* 周期相位甘特图 */}
      <hr className="section-divider" />
      <div id="gantt" className="section-block">
        <h2 style={{ fontSize: 'var(--fs-xl)', fontWeight: 700, marginBottom: 'var(--sp-lg)', marginTop: 0 }}>相位分布</h2>
        <p style={{ fontSize: 'var(--fs-base)', color: 'var(--text-secondary)', marginBottom: 'var(--sp-lg)' }}>
          四周期相位演进甘特图：颜色区分相位，纹理区分周期类型
        </p>
        <ErrorBoundary><CycleGantt /></ErrorBoundary>
        <ErrorBoundary><PhaseConsistency /></ErrorBoundary>
      </div>
    </div>
    </ErrorBoundary>
  );
}
