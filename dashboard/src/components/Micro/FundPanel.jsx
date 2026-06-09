import {useState} from 'react';
import {useMCP} from '../../hooks/useMCP.js';

export default function FundPanel() {
  const [code, setCode] = useState('');
  // code 为空时不发请求
  const { data: info } = useMCP('fund_info', code ? { code } : null);
  const { data: ranking } = useMCP('fund_ranking', { fund_type: '股票型' });
  return (
    <div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center' }}>
        <input value={code} onChange={e => setCode(e.target.value)} placeholder="基金代码" style={{ padding: '8px 14px', borderRadius: 12, border: '1px solid var(--border-subtle)', background: 'var(--bg-panel)', color: 'var(--text-primary)', width: 200 }} />
      </div>
      <div className="cg2">
        <div className="chart-container"><h3>📦 基金信息</h3><pre style={{ fontSize: 12, marginTop: 12, whiteSpace: 'pre-wrap' }}>{info || '暂无数据'}</pre></div>
        <div className="chart-container"><h3>🏆 股票型基金排名</h3><pre style={{ fontSize: 12, marginTop: 12, whiteSpace: 'pre-wrap' }}>{ranking || '暂无数据'}</pre></div>
      </div>
    </div>
  );
}