import {useEffect, useRef, useState} from 'react';
import * as echarts from 'echarts';

/* 注册一个极简暗色主题 — 只覆盖背景/文字/分割线，不碰系列色 */
echarts.registerTheme('df-dark', {
  backgroundColor: 'transparent',
  textStyle: { color: '#CBC0B0' },
  legend: { textStyle: { color: '#CBC0B0' } },
  categoryAxis: {
    axisLine: { lineStyle: { color: 'rgba(212,168,83,0.10)' } },
    axisTick: { show: false },
    axisLabel: { color: '#CBC0B0', fontSize: 11 },
    splitLine: { show: false },
  },
  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#CBC0B0', fontSize: 11 },
    splitLine: { lineStyle: { color: 'rgba(212,168,83,0.10)' } },
  },
});

/**
 * @param {object[]} data
 * @param {{ key: string, name: string, color: string, type?: string, yAxisIndex?: number }[]} series
 * @param {string} dateKey
 * @param {number} height
 * @param {boolean} zoom       是否启用滚轮缩放+拖拽
 * @param {number} zoomStart   dataZoom 初始 start 百分比
 * @param {number} zoomEnd     dataZoom 初始 end 百分比
 * @param {object[]} annotations 拐点标注 [{ year, type:'peak'|'trough', label, detail }]
 * @param {'value'|'log'} yAxisType  Y轴类型: value=线性, log=对数（初始值，可被切换按钮覆盖）
 * @param {boolean} normalize        是否归一化到基期100（多品种对比）
 * @param {'first'|'last'} normalizeBase 归一化基期: first=首个有效值, last=最后有效值
 * @param {boolean} showYAxisToggle  是否显示 Y轴 线性/对数 切换按钮
 */
export default function DataChart({
  data, series, dateKey = 'period', height = 400,
  zoom = true, zoomStart = 80, zoomEnd = 100,
  annotations,
  yAxisType = 'value',
  normalize = false,
  normalizeBase = 'first',
  showYAxisToggle = true,
}) {
  const [activeYType, setActiveYType] = useState(yAxisType);
  const chartRef = useRef(null);
  useEffect(() => {
    if (!chartRef.current || !data?.length) return;
    const chart = echarts.init(chartRef.current, 'df-dark');
    const dates = data.map(r => r[dateKey]);

    // 检测是否有 yAxisIndex > 0 的系列，有则启用双Y轴
    const hasDualY = series.some(s => s.yAxisIndex === 1);

    // 归一化处理：将每个 series 的数据归一化为基期=100
    const processedSeries = normalize
      ? series.map(s => {
          const rawVals = data.map(r => r[s.key]);
          const validIdx = normalizeBase === 'last'
            ? rawVals.findLastIndex(v => v != null && !isNaN(v) && v !== 0)
            : rawVals.findIndex(v => v != null && !isNaN(v) && v !== 0);
          const baseVal = validIdx >= 0 ? rawVals[validIdx] : null;
          const normVals = baseVal
            ? rawVals.map(v => (v != null && !isNaN(v)) ? (v / baseVal) * 100 : null)
            : rawVals;
          return { ...s, _normData: normVals };
        })
      : series;

    const option = {
      tooltip: { trigger: 'axis' },
      legend: { data: processedSeries.map(s => s.name), bottom: 0 },
      grid: { left: '8%', right: hasDualY ? '8%' : '5%', top: '10%', bottom: '15%', containLabel: true },
      xAxis: { type: 'category', data: dates, axisLabel: { rotate: 45 } },
      yAxis: hasDualY
        ? [
            { type: activeYType, name: '', axisLabel: { color: '#CBC0B0', fontSize: 12 },
              splitLine: { lineStyle: { color: 'rgba(212,168,83,0.10)' } } },
            { type: activeYType, name: '', axisLabel: { color: '#CBC0B0', fontSize: 12 },
              splitLine: { show: false } },
          ]
        : { type: activeYType },
      series: processedSeries.map((s, sIdx) => {
        const entry = {
          name: s.name,
          type: s.type || 'line',
          data: normalize ? s._normData : data.map(r => r[s.key]),
          smooth: true,
          connectNulls: true,
          lineStyle: { color: s.color, width: 2 },
          areaStyle: s.type !== 'bar'
            ? { opacity: 0.08, color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: s.color }, { offset: 1, color: 'transparent' },
              ]) }
            : undefined,
          itemStyle: s.type === 'bar' ? { color: s.color } : undefined,
          symbol: 'none',
          ...(s.yAxisIndex != null ? { yAxisIndex: s.yAxisIndex } : {}),
        };
        // 只在第一个系列上添加拐点标注
        if (sIdx === 0 && annotations?.length) {
          const dates = data.map(r => r[dateKey]);
          const markLineData = [];
          const markPointData = [];
          for (const ann of annotations) {
            const yearStr = String(ann.year);
            // 找到最匹配的 x 轴值（以年份开头的 period）
            const matchIdx = dates.findIndex(d => {
              const ds = String(d);
              return ds.startsWith(yearStr) || ds === yearStr;
            });
            if (matchIdx < 0) continue;
            const xVal = dates[matchIdx];
            const yVal = data[matchIdx]?.[s.key];
            if (yVal == null || isNaN(yVal)) continue;
            const isPeak = ann.type === 'peak';
            const color = isPeak ? '#f85149' : '#5bba57';
            // markLine：垂直虚线
            markLineData.push({
              xAxis: xVal,
              label: {
                show: true,
                formatter: `${isPeak ? '▼' : '▲'} ${ann.year} ${ann.label}`,
                color,
                fontSize: 12,
                fontWeight: 700,
                fontFamily: 'Microsoft YaHei, sans-serif',
                position: 'insideEndTop',
                rotate: 0,
              },
              lineStyle: {
                color,
                type: 'dashed',
                width: 1.2,
                opacity: 0.55,
              },
            });
            // markPoint：数据点上的标记
            markPointData.push({
              coord: [xVal, yVal],
              symbol: isPeak ? 'path://M0,0L6,-10L-6,-10Z' : 'path://M0,0L6,10L-6,10Z',
              symbolSize: 16,
              itemStyle: { color },
              label: { show: false },
              // 自定义 tooltip
              _annDetail: ann.detail,
              _annLabel: `${isPeak ? '▼' : '▲'} ${ann.year} ${ann.label}`,
            });
          }
          if (markLineData.length) {
            entry.markLine = {
              silent: false,
              animation: false,
              symbol: 'none',
              data: markLineData,
            };
          }
          if (markPointData.length) {
            entry.markPoint = {
              animation: false,
              data: markPointData,
              tooltip: {
                formatter: (params) => {
                  const d = params.data;
                  return d?._annLabel
                    ? `<div style="font-weight:700;margin-bottom:4px">${d._annLabel}</div><div style="font-size:12px;opacity:.85;max-width:240px;line-height:1.5">${d._annDetail || ''}</div>`
                    : '';
                },
              },
            };
          }
        }
        return entry;
      }),
    };
    if (zoom) {
      option.dataZoom = [
        { type: 'inside', start: zoomStart, end: zoomEnd },
        { type: 'slider', start: zoomStart, end: zoomEnd, height: 20, bottom: 28,
          borderColor: 'rgba(212,168,83,0.12)',
          backgroundColor: 'rgba(26,47,42,0.6)',
          dataBackground: {
            lineStyle: { color: 'rgba(212,168,83,0.15)' },
            areaStyle: { color: 'rgba(212,168,83,0.06)' },
          },
          selectedDataBackground: {
            lineStyle: { color: 'rgba(212,168,83,0.3)' },
            areaStyle: { color: 'rgba(212,168,83,0.12)' },
          },
          handleStyle: { color: '#CBC0B0' },
          textStyle: { color: '#CBC0B0', fontSize: 12 },
        },
      ];
    }
    chart.setOption(option);
    return () => chart.dispose();
  }, [data, series, dateKey, zoom, zoomStart, zoomEnd, annotations, activeYType, normalize, normalizeBase]);
  return (
    <div style={{ position: 'relative', width: '100%', height }}>
      {showYAxisToggle && (
        <div style={{ position: 'absolute', top: 4, right: 4, display: 'flex', gap: 4, zIndex: 10 }}>
          <button onClick={() => setActiveYType('value')} style={{
            padding: '2px 8px', fontSize: 10, borderRadius: 3, border: '1px solid rgba(212,168,83,0.2)',
            background: activeYType === 'value' ? 'rgba(212,168,83,0.35)' : 'transparent',
            color: activeYType === 'value' ? '#D4A853' : '#CBC0B0', cursor: 'pointer',
            fontWeight: activeYType === 'value' ? 700 : 400,
          }}>线性</button>
          <button onClick={() => setActiveYType('log')} style={{
            padding: '2px 8px', fontSize: 10, borderRadius: 3, border: '1px solid rgba(212,168,83,0.2)',
            background: activeYType === 'log' ? 'rgba(212,168,83,0.35)' : 'transparent',
            color: activeYType === 'log' ? '#D4A853' : '#CBC0B0', cursor: 'pointer',
            fontWeight: activeYType === 'log' ? 700 : 400,
          }}>对数</button>
        </div>
      )}
      <div ref={chartRef} style={{ width: '100%', height }} />
    </div>
  );
}