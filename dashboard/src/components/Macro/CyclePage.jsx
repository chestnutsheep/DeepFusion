import {useMemo} from 'react';
import {useMCP} from '../../hooks/useMCP.js';
import DataChart from '../common/DataChart.jsx';
import DataGrid from '../common/DataGrid.jsx';
import StatusBar from '../common/StatusBar.jsx';
import PhaseWheel from '../common/PhaseWheel.jsx';
import CardWrapper from '../common/CardWrapper.jsx';

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

/** 从 NBS 行数组中，对每个 key 找最近的非 null 值（最多回扫 12 行） */
function fillLatestMetrics(rows, keys) {
  if (!rows.length) return {};
  const result = {};
  for (const key of keys) {
    // 从最后一行开始往前找
    for (let i = rows.length - 1; i >= Math.max(0, rows.length - 12); i--) {
      const v = rows[i]?.[key];
      if (v != null && !isNaN(v)) {
        result[key] = v;
        break;
      }
    }
  }
  return result;
}

export default function CyclePage({ config, showTitle, tableIndex }) {
  const { data: rawData, isLoading } = useMCP(config.queryKey, config.params || {});
  // 三个小周期额外拉 FRED 扩展数据（百年序列）；传 null args 则不发请求
  const extResult = useMCP(config.extQueryKey, config.extQueryKey ? {} : null);

  // 优先使用扩展数据（更长历史），回退到 NBS 数据
  const rows = useMemo(() => {
    const extRows = extResult.data ? _parseJSON(extResult.data) : [];
    const nbsRows = rawData ? _parseJSON(rawData) : [];
    return extRows.length > 0 ? extRows : nbsRows;
  }, [rawData, extResult.data]);

  // NBS 全量数据用于指标卡（回扫填充缺失值）
  const nbsRows = useMemo(() => rawData ? _parseJSON(rawData) : [], [rawData]);

  // 对指标卡的 key 做回扫填充
  const metricKeys = (config.metrics || []).map(m => m.key);
  const filledLatest = useMemo(() => {
    if (!nbsRows.length) return {};
    const last = nbsRows[nbsRows.length - 1] || {};
    const filled = fillLatestMetrics(nbsRows, metricKeys);
    // 已有的值优先用原始值
    const result = { ...filled };
    for (const k of metricKeys) {
      if (last[k] != null && !isNaN(last[k])) result[k] = last[k];
    }
    return result;
  }, [nbsRows, metricKeys.join(',')]);

  const latest = rows[rows.length - 1] || {};
  const prev = rows[rows.length - 2] || {};
  // 指标卡优先使用 NBS 填充值（解决 PMI/M2/产能利用率为 null 的问题）
  const metricsLatest = Object.keys(filledLatest).length > 0 ? filledLatest : latest;

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

  const metrics = config.metrics || [];
  const chartHeight = Math.round(320 * 1.2); // 1.2x 放大

  // 根据数据源动态选择绘图系列
  const isUsingExtData = extResult.data && _parseJSON(extResult.data).length > 0;
  const activeChartSeries = isUsingExtData
    ? (config.chartSeries || [])
    : (config.nbsChartSeries || config.chartSeries || []);

  // 表编号和数据来源
  const tableLabel = tableIndex != null ? `表${tableIndex}：` : '';
  const chartTitle = `${tableLabel}${config.title || showTitle || '周期走势'}`;
  const dataSource = config.dataSource || 'NBS / FRED; 手动计算';

  return (
    <div>
      {showTitle && <h2 style={{ fontSize: 'var(--fs-xl)', fontWeight: 700, marginBottom: 'var(--sp-lg)', marginTop: 'var(--sp-md)' }}>{showTitle}</h2>}

      {/* 相位概览：PhaseWheel + 关键指标 */}
      <CardWrapper style={{ padding: 'var(--sp-lg) var(--sp-xl)', marginBottom: 'var(--sp-lg)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-xl)', flexWrap: 'wrap' }}>
          <PhaseWheel phase={phaseValue} phaseName={phaseName} cycleName={config.title} size={160} />
          <div style={{ flex: 1, minWidth: 200 }}>
            <StatusBar phase={phaseName} period={latest.period} />
            {/* 相位详情行 */}
            {phaseValue > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8, flexWrap: 'wrap' }}>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  background: badge.bg, border: `1.5px solid ${badge.border}`, borderRadius: 'var(--radius-sm)',
                  padding: '4px 14px', fontSize: 'var(--fs-md)', fontWeight: 700, color: badge.color,
                  letterSpacing: 0.5,
                }}>
                  {badge.icon} {phaseName}
                </span>
                {latest.confidence != null && (
                  <span style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)' }}>
                    置信度 <b style={{ color: 'var(--accent-gold)' }}>{(latest.confidence * 100).toFixed(0)}%</b>
                  </span>
                )}
                {latest.dominant_period != null && (
                  <span style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)' }}>
                    主周期 <b style={{ color: 'var(--text-primary)' }}>{latest.dominant_period.toFixed(1)}年</b>
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </CardWrapper>

      {/* 主内容区：图表全宽 + 指标卡下方横排 */}
      {(() => {
        const N = metrics.length;
        // 公共图表内容
        const chartContent = (
          <CardWrapper hoverable style={{
            padding: 'var(--sp-xl)',
            transition: 'all 0.25s ease',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 'var(--sp-md)' }}>
              <h3 style={{ fontSize: 'var(--fs-lg)', fontWeight: 700, color: 'var(--accent-gold)', fontFamily: "'Microsoft YaHei', sans-serif" }}>
                {chartTitle}
              </h3>
              <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>
                数据来源：{dataSource}
              </span>
            </div>
            <DataChart
              data={rows}
              series={activeChartSeries}
              dateKey="period"
              height={chartHeight}
              zoomStart={DEFAULT_WINDOW.start}
              zoomEnd={DEFAULT_WINDOW.end}
              annotations={config.turningPoints}
              enableReturnMode={false}
            />
          </CardWrapper>
        );

        if (N === 0) {
          return <div style={{ marginBottom: 'var(--sp-2xl)' }}>{chartContent}</div>;
        }

        // 统一布局：图表全宽 + 指标卡下方网格
        // 列数：≤6张用6列，>6张用4列（卡片已调大，6个一行更紧凑）
        const gridCols = N <= 6 ? N : 4;

        return (
          <div style={{ marginBottom: 'var(--sp-2xl)' }}>
            {chartContent}
            <div style={{ marginTop: 'var(--sp-lg)' }}>
              <DataGrid config={metrics} data={metricsLatest} prevData={prev} columns={gridCols} gap="var(--sp-md)" />
            </div>
          </div>
        );
      })()}

      {/* 周期解读说明 */}
      {config.explanation && (
        <div style={{ marginTop: 'var(--sp-2xl)', padding: 'var(--sp-lg) var(--sp-xl)', background: 'rgba(212,168,83,0.04)', border: '1px solid rgba(212,168,83,0.1)', borderRadius: 'var(--radius)' }}>
          <div style={{ fontSize: 'var(--fs-base)', fontWeight: 700, color: 'var(--accent-gold)', marginBottom: 'var(--sp-md)' }}>
            ⓘ {config.explanation.title} — 指标解读
          </div>
          <div style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
            <p style={{ margin: `0 0 var(--sp-xs)` }}><b style={{ color: 'var(--text-primary)' }}>周期定义：</b>{config.explanation.summary}</p>
            <p style={{ margin: `0 0 var(--sp-xs)` }}><b style={{ color: 'var(--text-primary)' }}>合成Z值：</b>{config.explanation.compositeZ}</p>
            <p style={{ margin: `0 0 var(--sp-xs)` }}><b style={{ color: 'var(--text-primary)' }}>周期分量：</b>{config.explanation.cycleComponent}</p>
            <p style={{ margin: 0 }}><b style={{ color: 'var(--text-primary)' }}>可靠性：</b>{config.explanation.reliability}</p>
          </div>
          {/* 当前相位配置建议 */}
          {phaseValue > 0 && (
            <div style={{ marginTop: 'var(--sp-md)', padding: 'var(--sp-md)', background: badge.bg, border: `1px solid ${badge.border}30`, borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: 'var(--fs-sm)', fontWeight: 700, color: badge.color, marginBottom: 6 }}>
                当前{phaseName}阶段的配置参考
              </div>
              <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {phaseValue === 1 && '复苏期：经济从谷底回升，先行指标转正但滞后指标仍弱。配置倾向：逐步加仓权益类资产，债券仍可持有但需警惕收益率上行。'}
                {phaseValue === 2 && '繁荣期：经济全面扩张，多数指标强势。配置倾向：权益类资产为主，商品受益于需求旺盛，债券承压。注意繁荣末期拐点信号。'}
                {phaseValue === 3 && '衰退期：经济从顶峰回落，先行指标转弱但滞后指标仍高。配置倾向：减仓权益，增配防御性资产（债券、黄金），规避周期性商品。'}
                {phaseValue === 4 && '萧条期：经济深度收缩，多数指标低迷。配置倾向：债券+黄金为主，等待复苏信号。先行指标触底回升是拐点前兆。'}
              </div>
              {latest.confidence != null && (
                <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', marginTop: 4 }}>
                  置信度 {(latest.confidence * 100).toFixed(0)}% — {latest.confidence >= 0.7 ? '信号较强，可参考配置' : latest.confidence >= 0.5 ? '信号中等，谨慎参考' : '信号偏弱，建议等待确认'}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
