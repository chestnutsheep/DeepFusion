import {useMemo} from 'react';
import {useMCP} from '../../hooks/useMCP.js';
import DataChart from '../common/DataChart.jsx';
import DataCard from '../common/DataCard.jsx';
import CardWrapper from '../common/CardWrapper.jsx';

function parseQvixCsv(csv) {
  if (!csv) return [];
  const lines = csv.trim().split('\n');
  if (lines.length < 2) return [];
  const header = lines[0].split(',').map(h => h.trim());
  // 查找日期列和VIX列
  const closeIdx = header.findIndex(h => h.includes('close') || h.includes('qvix') || h.includes('ivix')) || 4;
  return lines.slice(1).map(l => {
    const p = l.split(',');
    return { period: (p[0] || '').slice(5), value: parseFloat(p[closeIdx]) || 0 };
  }).filter(d => !isNaN(d.value) && d.period).slice(-120);
}

function parseGenericCsv(csv, dateCol = 0, valCol = 1, slicePeriod = 10) {
  if (!csv) return [];
  return csv.trim().split('\n').slice(1).map(l => {
    const p = l.split(',');
    return { period: (p[dateCol] || '').slice(0, slicePeriod), value: parseFloat(p[valCol]) || 0 };
  }).filter(d => !isNaN(d.value)).slice(-60);
}

export default function OptionPanel() {
  const { data: qvixRaw } = useMCP('option_ivix', { limit: 120 });

  const qvixData = useMemo(() => parseQvixCsv(qvixRaw), [qvixRaw]);

  const latestQvix = qvixData[qvixData.length - 1]?.value;
  const prevQvix = qvixData[qvixData.length - 2]?.value;
  const qvixChange = latestQvix != null && prevQvix != null ? ((latestQvix - prevQvix) / prevQvix * 100) : null;

  // 波动率状态判定
  const volStatus = latestQvix != null
    ? (latestQvix > 30 ? '高波动' : latestQvix > 20 ? '中等波动' : '低波动')
    : '—';

  return (
    <div>
      {/* 指标卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
        <DataCard label="QVIX 恐慌指数" value={latestQvix} unit="" decimals={2} higherBetter={null} detail="中国版VIX" />
        <DataCard label="日变化" value={qvixChange} unit="%" decimals={2} higherBetter={null} />
        <CardWrapper style={{ padding: 12 }}>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>波动率状态</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: latestQvix > 30 ? 'var(--accent-red)' : latestQvix > 20 ? 'var(--accent-gold)' : 'var(--accent-green)' }}>
            {volStatus}
          </div>
        </CardWrapper>
      </div>

      {/* QVIX走势图 */}
      <CardWrapper style={{ padding: 16 }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📈 QVIX 波动率走势 <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 400 }}>· 50ETF期权</span></h3>
        <DataChart data={qvixData} series={[{ key: 'value', name: 'QVIX', color: '#f85149', type: 'line' }]} dateKey="period" height={300} />
      </CardWrapper>
    </div>
  );
}
