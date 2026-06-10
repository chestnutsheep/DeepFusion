import {useMemo, useState} from 'react';
import {useMCP} from '../../hooks/useMCP.js';
import DataChart from '../common/DataChart.jsx';
import DataCard from '../common/DataCard.jsx';
import CardWrapper from '../common/CardWrapper.jsx';

function parsePriceCsv(csv) {
  if (!csv) return [];
  const lines = csv.trim().split('\n');
  if (lines.length < 2) return [];
  const header = lines[0].split(',').map(h => h.trim());
  const closeIdx = header.findIndex(h => h === 'close' || h === '收盘');
  const volIdx = header.findIndex(h => h === 'volume' || h === '成交量');
  const ci = closeIdx >= 0 ? closeIdx : 1;
  const vi = volIdx >= 0 ? volIdx : -1;
  return lines.slice(1).map(l => {
    const p = l.split(',');
    const item = { period: (p[0] || '').slice(5), close: parseFloat(p[ci]) || 0 };
    if (vi >= 0) item.volume = parseFloat(p[vi]) || 0;
    return item;
  }).filter(d => !isNaN(d.close)).slice(-120);
}

function parseGenericCsv(csv, dateCol = 0, valCol = 1, slicePeriod = 10) {
  if (!csv) return [];
  return csv.trim().split('\n').slice(1).map(l => {
    const p = l.split(',');
    return { period: (p[dateCol] || '').slice(0, slicePeriod), value: parseFloat(p[valCol]) || 0 };
  }).filter(d => !isNaN(d.value)).slice(-60);
}

export default function FuturesPanel() {
  const [symbol, setSymbol] = useState('螺纹钢');
  const [inputVal, setInputVal] = useState('螺纹钢');
  const commonSymbols = [
    { name: '螺纹钢', label: '⛏️ 螺纹钢' },
    { name: '铁矿石', label: '🪨 铁矿石' },
    { name: '沪铜', label: '🪙 铜' },
    { name: '原油', label: '🛢️ 原油' },
    { name: '豆粕', label: '🌾 豆粕' },
    { name: '沪金', label: '🥇 黄金' },
  ];

  const { data: priceRaw } = useMCP('futures_prices', symbol ? { symbol, limit: 90 } : null);
  const { data: invRaw } = useMCP('futures_inventory', symbol ? { symbol } : null);
  const { data: basisRaw } = useMCP('futures_basis', symbol ? { symbol } : null);
  const { data: posRaw } = useMCP('futures_positions', symbol ? { symbol } : null);

  const priceData = useMemo(() => parsePriceCsv(priceRaw), [priceRaw]);
  const invData = useMemo(() => parseGenericCsv(invRaw, 0, 1, 10), [invRaw]);

  const latestPrice = priceData[priceData.length - 1]?.close;
  const prevPrice = priceData[priceData.length - 2]?.close;
  const priceChange = latestPrice && prevPrice ? ((latestPrice - prevPrice) / prevPrice * 100) : null;
  const latestInv = invData.length > 0 ? invData[invData.length - 1].value : null;
  const prevInv = invData.length > 1 ? invData[invData.length - 2].value : null;
  const invChange = latestInv && prevInv ? ((latestInv - prevInv) / prevInv * 100) : null;

  return (
    <div>
      {/* 品种选择 */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <input value={inputVal} onChange={e => setInputVal(e.target.value)} onKeyDown={e => e.key === 'Enter' && setSymbol(inputVal)}
          style={{ padding: '8px 14px', borderRadius: 4, border: '1px solid var(--border-subtle)', background: 'var(--bg-panel)', color: 'var(--text-primary)', width: 160, fontSize: 13 }}
          placeholder="输入品种名称" />
        <button onClick={() => setSymbol(inputVal)} style={{ padding: '8px 18px', borderRadius: 4, background: 'var(--accent-gold)', color: '#000', border: 'none', cursor: 'pointer', fontWeight: 700 }}>查询</button>
        {commonSymbols.map(s => (
          <button key={s.name} onClick={() => { setSymbol(s.name); setInputVal(s.name); }}
            style={{
              padding: '4px 12px', borderRadius: 4, fontSize: 11,
              fontWeight: symbol === s.name ? 700 : 500,
              background: symbol === s.name ? 'var(--accent-gold)' : 'transparent',
              color: symbol === s.name ? '#000' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)', cursor: 'pointer',
            }}>{s.label}</button>
        ))}
      </div>

      {/* 指标卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
        <DataCard label={`${symbol} 最新价`} value={latestPrice} unit="元" decimals={2} higherBetter={null} detail="主力合约" />
        <DataCard label="涨跌幅" value={priceChange} unit="%" decimals={2} higherBetter={true} />
        <DataCard label="库存变化" value={invChange} unit="%" decimals={2} higherBetter={null} detail="期货仓单环比" />
      </div>

      {/* 图表区 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 14, marginBottom: 16 }}>
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📈 价格走势 <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 400 }}>· {symbol} 主力</span></h3>
          <DataChart data={priceData} series={[{ key: 'close', name: `${symbol}`, color: '#D4A853', type: 'line' }]} dateKey="period" height={280} />
        </CardWrapper>
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📊 库存变化 <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 400 }}>· {symbol}</span></h3>
          <DataChart data={invData} series={[{ key: 'value', name: '库存', color: '#7B5E7B', type: 'bar' }]} dateKey="period" height={280} />
        </CardWrapper>
      </div>

      {/* 基差 + 持仓信息 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 14 }}>
        {basisRaw && (
          <CardWrapper style={{ padding: 14, borderLeft: '3px solid var(--accent-gold)' }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>📋 期现基差</h3>
            <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6, maxHeight: 200, overflow: 'auto' }}>{basisRaw}</pre>
          </CardWrapper>
        )}
        {posRaw && (
          <CardWrapper style={{ padding: 14, borderLeft: '3px solid var(--accent-blue)' }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>📊 持仓分析</h3>
            <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6, maxHeight: 200, overflow: 'auto' }}>{posRaw}</pre>
          </CardWrapper>
        )}
      </div>
    </div>
  );
}
