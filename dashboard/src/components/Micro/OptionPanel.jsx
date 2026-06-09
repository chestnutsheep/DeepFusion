import { useMCP } from '../../hooks/useMCP.js';
import DataChart from '../common/DataChart.jsx';

function parseQvix(csv) {
  if (!csv) return [];
  const lines = csv.trim().split('\n');
  if (lines.length < 2) return [];
  return lines.slice(1).map(l => {
    const parts = l.split(',');
    return { period: parts[0]?.slice(5) || '', close: parseFloat(parts[4]) };
  }).filter(d => !isNaN(d.close)).slice(-60);
}

export default function OptionPanel() {
  const { data: qvixRaw } = useMCP('option_ivix', { limit: 60 });
  const qvixData = parseQvix(qvixRaw);
  const chartSeries = [{ key: 'close', name: 'QVIX恐慌指数', color: '#f85149', type: 'line' }];
  return <DataChart data={qvixData} series={chartSeries} height={300} />;
}