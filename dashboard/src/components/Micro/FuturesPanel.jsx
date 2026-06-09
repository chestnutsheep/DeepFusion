import {useState} from 'react';
import {useMCP} from '../../hooks/useMCP.js';
import DataChart from '../common/DataChart.jsx';

function parsePrice(csv) {
  if (!csv) return [];
  const lines = csv.trim().split('\n');
  if (lines.length < 2) return [];
  const closeIdx = lines[0].split(',').findIndex(h => h === 'close' || h === '收盘价');
  if (closeIdx === -1) return [];
  return lines.slice(1).map(l => {
    const parts = l.split(',');
    return { period: parts[0]?.slice(5) || '', close: parseFloat(parts[closeIdx]) };
  }).filter(d => !isNaN(d.close)).slice(-60);
}

export default function FuturesPanel() {
  const [symbol, setSymbol] = useState('');
  const [inputVal, setInputVal] = useState('');
  const { data: priceRaw } = useMCP('futures_prices', symbol ? { symbol, limit: 60 } : null);
  const priceData = parsePrice(priceRaw);
  const chartSeries = [{ key: 'close', name: symbol ? `${symbol}主力合约` : '请选择品种', color: '#d2991d', type: 'line' }];
  const commonSymbols = ['螺纹钢', '铁矿石', '沪铜', '原油', '豆粕', '沪金'];
  return (
    <div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        <input value={inputVal} onChange={e => setInputVal(e.target.value)} onKeyDown={e => e.key === 'Enter' && setSymbol(inputVal)} style={{ padding: '8px 14px', borderRadius: 12, border: '1px solid var(--border-subtle)', background: 'var(--bg-panel)', color: 'var(--text-primary)', width: 200 }} />
        <button onClick={() => setSymbol(inputVal)} style={{ padding: '8px 22px', borderRadius: 20, background: 'var(--accent-gold)', color: '#000', border: 'none', cursor: 'pointer' }}>查询</button>
        {commonSymbols.map(s => (
          <span key={s} onClick={() => { setSymbol(s); setInputVal(s); }} style={{ padding: '4px 12px', borderRadius: 16, cursor: 'pointer', background: symbol === s ? 'rgba(212,168,83,0.2)' : 'rgba(0,0,0,0.2)', fontSize: 12 }}>{s}</span>
        ))}
      </div>
      <DataChart data={priceData} series={chartSeries} height={300} />
    </div>
  );
}