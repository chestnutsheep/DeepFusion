import { useMCP } from '../../hooks/useMCP.js';
import DataChart from '../common/DataChart.jsx';

function parseYields(csv) {
  if (!csv) return [];
  const lines = csv.trim().split('\n');
  if (lines.length < 2) return [];
  return lines.slice(1).map(l => {
    const parts = l.split(',');
    return { period: parts[0]?.slice(5) || '', close: parseFloat(parts[3]) };
  }).filter(d => !isNaN(d.close)).slice(-60);
}

export default function BondPanel() {
  const { data: yieldsRaw } = useMCP('bond_yields', { limit: 60, china_only: true });
  const yieldsData = parseYields(yieldsRaw);
  const chartSeries = [{ key: 'close', name: '10年期国债收益率', color: '#58a6ff', type: 'line' }];
  return <DataChart data={yieldsData} series={chartSeries} height={300} />;
}