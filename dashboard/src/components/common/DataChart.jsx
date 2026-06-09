import {useEffect, useRef} from 'react';
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
 */
export default function DataChart({
  data, series, dateKey = 'period', height = 400,
  zoom = true, zoomStart = 80, zoomEnd = 100,
}) {
  const chartRef = useRef(null);
  useEffect(() => {
    if (!chartRef.current || !data?.length) return;
    const chart = echarts.init(chartRef.current, 'df-dark');
    const dates = data.map(r => r[dateKey]);

    // 检测是否有 yAxisIndex > 0 的系列，有则启用双Y轴
    const hasDualY = series.some(s => s.yAxisIndex === 1);

    const option = {
      tooltip: { trigger: 'axis' },
      legend: { data: series.map(s => s.name), bottom: 0 },
      grid: { left: '8%', right: hasDualY ? '8%' : '5%', top: '10%', bottom: '15%', containLabel: true },
      xAxis: { type: 'category', data: dates, axisLabel: { rotate: 45 } },
      yAxis: hasDualY
        ? [
            { type: 'value', name: '', axisLabel: { color: '#CBC0B0', fontSize: 12 },
              splitLine: { lineStyle: { color: 'rgba(212,168,83,0.10)' } } },
            { type: 'value', name: '', axisLabel: { color: '#CBC0B0', fontSize: 12 },
              splitLine: { show: false } },
          ]
        : { type: 'value' },
      series: series.map(s => ({
        name: s.name,
        type: s.type || 'line',
        data: data.map(r => r[s.key]),
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
      })),
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
  }, [data, series, dateKey, zoom, zoomStart, zoomEnd]);
  return <div ref={chartRef} style={{ width: '100%', height }} />;
}