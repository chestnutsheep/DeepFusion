import {useMemo} from 'react';
import {useMCP} from '../../hooks/useMCP.js';
import DataChart from '../common/DataChart.jsx';
import DataGrid from '../common/DataGrid.jsx';
import StatusBar from '../common/StatusBar.jsx';

const ZOOM_WINDOW = {
  data_kitchin:     { start: 70, end: 100 },
  data_juglar:      { start: 50, end: 100 },
  data_kuznets:     { start: 40, end: 100 },
  data_kondratiev:  { start: 20, end: 100 },
};
const DEFAULT_WINDOW = { start: 50, end: 100 };

/** 相位→醒目标签样式 */
const PHASE_BADGE = {
  1: { bg: 'rgba(91,186,87,0.18)', border: '#5bba57', color: '#5bba57', icon: '↗' },
  2: { bg: 'rgba(212,168,83,0.22)', border: '#D4A853', color: '#D4A853', icon: '↑' },
  3: { bg: 'rgba(248,81,73,0.18)', border: '#f85149', color: '#f85149', icon: '↘' },
  4: { bg: 'rgba(136,136,136,0.18)', border: '#888', color: '#999', icon: '↓' },
  0: { bg: 'rgba(136,136,136,0.08)', border: '#555', color: '#666', icon: '·' },
};

export default function CyclePage({ config, showTitle }) {
  const { data: rawData, isLoading } = useMCP(config.queryKey, config.params || {});

  // 用 useMemo 缓存解析，避免每次渲染新数组引用导致 DataChart 销毁重建
  const rows = useMemo(() => {
    if (!rawData) return [];
    try {
      const parsed = JSON.parse(rawData);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }, [rawData]);

  const latest = rows[rows.length - 1] || {};
  const prev = rows[rows.length - 2] || {};

  if (isLoading) return <div style={{ padding: 20 }}>加载中...</div>;
  if (!rows.length) return <div style={{ padding: 20 }}>暂无数据</div>;

  let phaseValue = latest[config.phaseField];
  let phaseName = phaseValue;
  if (latest.phase_name && latest.phase_name !== '未知') {
    phaseName = latest.phase_name;
  } else if (config.phaseField === 'phase') {
    const phaseNames = ['', '复苏', '繁荣', '衰退', '萧条'];
    phaseName = phaseNames[phaseValue] || phaseValue;
  }

  // 醒目的相位标签
  const badge = PHASE_BADGE[phaseValue] || PHASE_BADGE[0];

  // dataZoom 默认窗口 — 数据全量不变，只控制可视范围
  const { start: zoomStart, end: zoomEnd } = ZOOM_WINDOW[config.queryKey] || DEFAULT_WINDOW;

  const metrics = config.metrics || [];
  const chartHeight = 320;

  return (
    <div>
      {showTitle && <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 12, marginTop: 8 }}>{showTitle}</h2>}
      <StatusBar phase={phaseName} period={latest.period} />

      {/* 相位醒目标签 */}
      {phaseValue > 0 && (
        <div style={{ marginTop: 8, marginBottom: 12 }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: badge.bg, border: `1.5px solid ${badge.border}`, borderRadius: 4,
            padding: '4px 12px', fontSize: 14, fontWeight: 700, color: badge.color,
            letterSpacing: 1,
          }}>
            {badge.icon} {phaseName}
            {latest.confidence != null && (
              <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 4 }}>
                置信度 {(latest.confidence * 100).toFixed(0)}%
              </span>
            )}
          </span>
        </div>
      )}

      {/* 图表在左 60%，右侧留白 */}
      <div style={{ width: '60%', marginBottom: 20 }}>
        <DataChart
          data={rows}
          series={config.chartSeries}
          dateKey="period"
          height={chartHeight}
          zoomStart={zoomStart}
          zoomEnd={zoomEnd}
        />
      </div>

      {/* 指标卡 — 底部横排 */}
      {metrics.length > 0 && (
        <DataGrid config={metrics} data={latest} prevData={prev} columns={metrics.length} gap={12} />
      )}
    </div>
  );
}
