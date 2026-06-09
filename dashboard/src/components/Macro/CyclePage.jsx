import {useMemo} from 'react';
import {useMCP} from '../../hooks/useMCP.js';
import DataChart from '../common/DataChart.jsx';
import DataGrid from '../common/DataGrid.jsx';
import StatusBar from '../common/StatusBar.jsx';

// 所有图表默认显示全量数据的后 1/5
const DEFAULT_WINDOW = { start: 80, end: 100 };

/** JSON 字符串 → 数组 */
function _parseJSON(raw) {
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

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
  // 三个小周期额外拉 FRED 扩展数据（百年序列）；传 null args 则不发请求
  const extResult = useMCP(config.extQueryKey, config.extQueryKey ? {} : null);

  // 优先使用扩展数据（更长历史），回退到 NBS 数据
  const rows = useMemo(() => {
    const extRows = extResult.data ? _parseJSON(extResult.data) : [];
    const nbsRows = rawData ? _parseJSON(rawData) : [];
    // 扩展数据有 composite_z + cycle_val，NBS 数据有原始指标
    // 图表使用扩展数据（100年+），指标卡使用 NBS 最新值
    return extRows.length > 0 ? extRows : nbsRows;
  }, [rawData, extResult.data]);

  // NBS 最新行用于指标卡
  const nbsLatest = useMemo(() => {
    const nbsRows = rawData ? _parseJSON(rawData) : [];
    return nbsRows[nbsRows.length - 1] || {};
  }, [rawData]);

  const latest = rows[rows.length - 1] || {};
  const prev = rows[rows.length - 2] || {};
  // 指标卡优先使用 NBS 数据（更细粒度），回退到扩展数据
  const metricsLatest = Object.keys(nbsLatest).length > 0 ? nbsLatest : latest;

  if (isLoading) return <div style={{ padding: 20 }}>加载中...</div>;
  if (!rows.length) return <div style={{ padding: 20 }}>暂无数据</div>;

  // 扩展数据使用 phase/phase_name，NBS 数据使用 stage_name 等
  let phaseValue = latest.phase ?? latest[config.phaseField];
  let phaseName = phaseValue;
  if (latest.phase_name && latest.phase_name !== '未知') {
    phaseName = latest.phase_name;
  } else if (latest.stage_name) {
    phaseName = latest.stage_name;
  } else if (config.phaseField === 'phase' || latest.phase != null) {
    const phaseNames = ['', '复苏', '繁荣', '衰退', '萧条'];
    phaseName = phaseNames[phaseValue] || phaseValue;
  }

  // 醒目的相位标签
  const badge = PHASE_BADGE[phaseValue] || PHASE_BADGE[0];

  // dataZoom 默认窗口 — 所有周期统一 1/5
  const { start: zoomStart, end: zoomEnd } = DEFAULT_WINDOW;

  const metrics = config.metrics || [];
  const chartHeight = 320;

  // 根据数据源动态选择绘图系列：扩展数据用 chartSeries，NBS 数据用 nbsChartSeries
  const isUsingExtData = extResult.data && _parseJSON(extResult.data).length > 0;
  const activeChartSeries = isUsingExtData
    ? (config.chartSeries || [])
    : (config.nbsChartSeries || config.chartSeries || []);

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
          series={activeChartSeries}
          dateKey="period"
          height={chartHeight}
          zoomStart={zoomStart}
          zoomEnd={zoomEnd}
        />
      </div>

      {/* 指标卡 — 底部横排 */}
      {metrics.length > 0 && (
        <DataGrid config={metrics} data={metricsLatest} prevData={prev} columns={metrics.length} gap={12} />
      )}
    </div>
  );
}
