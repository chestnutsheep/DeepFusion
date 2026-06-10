import {useMemo, useState} from 'react';
import {useMCP} from '../../hooks/useMCP.js';
import CardWrapper from '../common/CardWrapper.jsx';

export default function FundPanel() {
  const [code, setCode] = useState('');
  const [inputVal, setInputVal] = useState('');
  const commonFunds = [
    { code: '110022', name: '易方达消费' },
    { code: '000001', name: '华夏成长' },
    { code: '510300', name: '沪深300ETF' },
    { code: '510050', name: '50ETF' },
  ];

  const { data: info } = useMCP('fund_info', code ? { code } : null);
  const { data: ranking } = useMCP('fund_ranking', { fund_type: '股票型' });
  const { data: allocRaw } = useMCP('fund_asset_allocation', code ? { code } : null);
  const { data: analysisRaw } = useMCP('fund_analysis', code ? { code } : null);

  // 解析资产配置
  const allocData = useMemo(() => {
    if (!allocRaw) return null;
    try {
      const lines = allocRaw.trim().split('\n');
      if (lines.length < 2) return null;
      const header = lines[0].split(',').map(h => h.trim());
      const labelIdx = header.findIndex(h => h.includes('类型') || h.includes('类别') || h === 'item') || 0;
      const ratioIdx = header.findIndex(h => h.includes('比例') || h.includes('占比') || h.includes('ratio')) || header.length - 1;
      const allocs = [];
      const colorMap = { '股票': '#D4A853', '债券': '#5B8FA8', '现金': '#3E6B5C', '其他': '#C49BA5' };
      for (const line of lines.slice(1)) {
        const parts = line.split(',');
        const label = parts[labelIdx]?.trim();
        const ratio = parseFloat(parts[ratioIdx]) || 0;
        if (label && ratio > 0) allocs.push({ label, ratio, color: colorMap[label] || '#888' });
      }
      return allocs.length > 0 ? allocs : null;
    } catch { return null; }
  }, [allocRaw]);

  return (
    <div>
      {/* 搜索栏 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <input value={inputVal} onChange={e => setInputVal(e.target.value)} onKeyDown={e => e.key === 'Enter' && setCode(inputVal)}
          style={{ padding: '8px 14px', borderRadius: 4, border: '1px solid var(--border-subtle)', background: 'var(--bg-panel)', color: 'var(--text-primary)', width: 160, fontSize: 13 }}
          placeholder="输入基金代码" />
        <button onClick={() => setCode(inputVal)} style={{ padding: '8px 18px', borderRadius: 4, background: 'var(--accent-gold)', color: '#000', border: 'none', cursor: 'pointer', fontWeight: 700 }}>查询</button>
        {commonFunds.map(f => (
          <button key={f.code} onClick={() => { setCode(f.code); setInputVal(f.code); }}
            style={{
              padding: '4px 12px', borderRadius: 4, fontSize: 11,
              fontWeight: code === f.code ? 700 : 500,
              background: code === f.code ? 'var(--accent-gold)' : 'transparent',
              color: code === f.code ? '#000' : 'var(--text-secondary)',
              border: '1px solid var(--border-subtle)', cursor: 'pointer',
            }}>{f.name}</button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 14 }}>
        {/* 基金信息 */}
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📦 基金信息</h3>
          <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6, maxHeight: 300, overflow: 'auto' }}>{info || '输入基金代码查看详情'}</pre>
        </CardWrapper>

        {/* 资产配置 */}
        {allocData && (
          <CardWrapper style={{ padding: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>💼 资产配置</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {allocData.map(a => (
                <div key={a.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: a.color, display: 'inline-block' }} />
                  <span style={{ fontSize: 13, flex: 1 }}>{a.label}</span>
                  <div style={{ flex: 2, height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ width: `${a.ratio}%`, height: '100%', background: a.color, borderRadius: 3 }} />
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-gold)', width: 50, textAlign: 'right' }}>{a.ratio.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </CardWrapper>
        )}

        {/* 风险收益分析 */}
        {analysisRaw && (
          <CardWrapper style={{ padding: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📊 风险收益分析</h3>
            <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6, maxHeight: 200, overflow: 'auto' }}>{analysisRaw}</pre>
          </CardWrapper>
        )}

        {/* 基金排名 */}
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>🏆 股票型基金排名</h3>
          <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6, maxHeight: 300, overflow: 'auto' }}>{ranking || '暂无数据'}</pre>
        </CardWrapper>
      </div>
    </div>
  );
}
