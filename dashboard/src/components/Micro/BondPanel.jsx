import {useMemo} from 'react';
import {useMCP} from '../../hooks/useMCP.js';
import DataChart from '../common/DataChart.jsx';
import DataCard from '../common/DataCard.jsx';
import CardWrapper from '../common/CardWrapper.jsx';

function parseYieldsCsv(csv) {
  if (!csv) return [];
  const lines = csv.trim().split('\n');
  if (lines.length < 2) return [];
  const header = lines[0].split(',').map(h => h.trim());
  // 查找日期列和收益率列
  const dateIdx = 0;
  const yieldIdx = header.findIndex(h => h.includes('收益率') || h.includes('yield') || h === 'close') || 3;
  return lines.slice(1).map(l => {
    const p = l.split(',');
    return { period: (p[dateIdx] || '').slice(5), value: parseFloat(p[yieldIdx]) || 0 };
  }).filter(d => !isNaN(d.value) && d.period).slice(-120);
}

export default function BondPanel() {
  const { data: yieldsRaw } = useMCP('bond_yields', { limit: 120 });
  const { data: collectRaw } = useMCP('bond_collect');

  const yieldsData = useMemo(() => parseYieldsCsv(yieldsRaw), [yieldsRaw]);

  const latestYield = yieldsData[yieldsData.length - 1]?.value;
  const prevYield = yieldsData[yieldsData.length - 2]?.value;
  const yieldChange = latestYield != null && prevYield != null ? (latestYield - prevYield) : null;

  return (
    <div>
      {/* 指标卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginBottom: 16 }}>
        <DataCard label="10年期国债收益率" value={latestYield} unit="%" decimals={3} higherBetter={null} detail="中债估值" />
        <DataCard label="日变动" value={yieldChange} unit="bp" decimals={1} higherBetter={null}
          format={v => v != null ? (v * 100).toFixed(1) : null} />
      </div>

      {/* 走势图 */}
      <CardWrapper style={{ padding: 16, marginBottom: 16 }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📈 国债收益率走势 <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 400 }}>· 10年期</span></h3>
        <DataChart data={yieldsData} series={[{ key: 'value', name: '10Y国债', color: '#5B8FA8', type: 'line' }]} dateKey="period" height={300} />
      </CardWrapper>

      {/* 债券市场概览 */}
      {collectRaw && (
        <CardWrapper style={{ padding: 14, borderLeft: '3px solid var(--accent-blue)' }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>📋 债券市场概览</h3>
          <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6, maxHeight: 280, overflow: 'auto' }}>{collectRaw}</pre>
        </CardWrapper>
      )}
    </div>
  );
}
