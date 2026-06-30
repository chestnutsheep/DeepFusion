import {useMemo} from 'react';
import {useMCP} from '../../hooks/useMCP.js';
import {useAppStore} from '../../store/index.js';
import CardWrapper from '../common/CardWrapper.jsx';
import DataChart from '../common/DataChart.jsx';
import DataGrid from '../common/DataGrid.jsx';

// ── fund_info 解析（雪球源：item:value 格式） ──
function parseFundInfo(raw) {
  if (!raw) return {};
  const lines = raw.trim().split('\n');
  const result = {};
  for (const line of lines) {
    const idx = line.indexOf(':');
    if (idx < 0) continue;
    const key = line.slice(0, idx).trim();
    const val = line.slice(idx + 1).trim();
    result[key] = val;
  }
  return result;
}

// ── fund_analysis 解析（CSV: 周期,较同类风险收益比,...,最大回撤） ──
function parseFundAnalysis(raw) {
  if (!raw) return {};
  try {
    const lines = raw.trim().split('\n');
    if (lines.length < 2) return {};
    const headers = lines[0].split(',').map(h => h.trim());
    const row = lines[1].split(',').map(v => v.trim());
    const result = {};
    headers.forEach((h, i) => { result[h] = row[i]; });
    return result;
  } catch { return {}; }
}

// ── fund_asset_allocation 解析（CSV） ──
function parseAssetAllocation(raw) {
  if (!raw) return null;
  try {
    const lines = raw.trim().split('\n');
    if (lines.length < 2) return null;
    const headers = lines[0].split(',').map(h => h.trim());
    const labelIdx = headers.findIndex(h => h.includes('类型') || h.includes('类别') || h === 'item') || 0;
    const ratioIdx = headers.findIndex(h => h.includes('比例') || h.includes('占比') || h.includes('ratio') || h === 'value') || headers.length - 1;
    const colorMap = { '股票': '#D4A853', '债券': '#5B8FA8', '现金': '#3E6B5C', '其他': '#C49BA5' };
    const allocs = [];
    for (const line of lines.slice(1)) {
      const parts = line.split(',');
      const label = parts[labelIdx]?.trim();
      const ratio = parseFloat(parts[ratioIdx]) || 0;
      if (label && ratio > 0) allocs.push({ label, ratio, color: colorMap[label] || '#888' });
    }
    return allocs.length > 0 ? allocs : null;
  } catch { return null; }
}

// ── fund_nav 解析（CSV：基金代码,日期,单位净值,累计净值,日增长率,...） ──
function parseNavHistory(raw) {
  if (!raw) return [];
  try {
    const lines = raw.trim().split('\n');
    if (lines.length < 2) return [];
    const headers = lines[0].split(',').map(h => h.trim());
    const dateIdx = headers.findIndex(h => h === '日期' || h === '净值日期' || h === 'date');
    const navIdx = headers.findIndex(h => h === '单位净值' || h === 'nav' || h.includes('单位'));
    const accIdx = headers.findIndex(h => h === '累计净值' || h === 'accNav' || h.includes('累计'));
    const growIdx = headers.findIndex(h => h === '日增长率' || h.includes('增长') || h.includes('growth'));
    if (navIdx === -1) return [];
    return lines.slice(1).map(l => {
      const parts = l.split(',');
      return {
        period: dateIdx !== -1 ? parts[dateIdx]?.trim() : '',
        nav: parseFloat(parts[navIdx]),
        accNav: accIdx !== -1 ? parseFloat(parts[accIdx]) : null,
        growth: growIdx !== -1 ? parseFloat(parts[growIdx]) : null,
      };
    }).filter(d => !isNaN(d.nav)).slice(-120);
  } catch { return []; }
}

// ── fund_holdings 解析（CSV: 序号,股票代码,股票名称,占净值比例,...） ──
function parseHoldings(raw) {
  if (!raw) return [];
  try {
    const lines = raw.trim().split('\n');
    if (lines.length < 2) return [];
    const headers = lines[0].split(',').map(h => h.trim());
    const codeIdx = headers.findIndex(h => h === '股票代码');
    const nameIdx = headers.findIndex(h => h === '股票名称');
    const ratioIdx = headers.findIndex(h => h === '占净值比例');
    return lines.slice(1).map(l => {
      const parts = l.split(',');
      return {
        code: parts[codeIdx]?.trim() || '',
        name: parts[nameIdx]?.trim() || '',
        ratio: parseFloat(parts[ratioIdx]) || 0,
      };
    }).filter(h => h.code && h.name);
  } catch { return []; }
}

// ── 股票代码→市场 ──
function guessMarket(code) {
  if (!code) return 'sh';
  const first = code[0];
  if (first === '6') return 'sh';
  if (first === '0' || first === '3') return 'sz';
  if (first === '8' || first === '4') return 'bj';
  return 'sh';
}

// ── 风险收益 DataGrid 配置 ──
const ANALYSIS_CONFIG = [
  { key: 'vol_1y', label: '近1年波动率', unit: '%', higherBetter: false },
  { key: 'sharpe_1y', label: '近1年夏普', unit: '', higherBetter: true },
  { key: 'drawdown_1y', label: '近1年最大回撤', unit: '%', higherBetter: false },
  { key: 'vol_3y', label: '近3年波动率', unit: '%', higherBetter: false },
  { key: 'sharpe_3y', label: '近3年夏普', unit: '', higherBetter: true },
  { key: 'drawdown_3y', label: '近3年最大回撤', unit: '%', higherBetter: false },
];

export default function FundDetailPage({ code, name, onBack }) {
  const { data: infoRaw } = useMCP('fund_info', { code });
  const { data: navRaw } = useMCP('fund_nav', { code, limit: 120 });
  const { data: allocRaw } = useMCP('fund_asset_allocation', { code });
  const { data: analysisRaw } = useMCP('fund_analysis', { code });
  const { data: holdingsRaw } = useMCP('fund_holdings', { code });

  const info = useMemo(() => parseFundInfo(infoRaw), [infoRaw]);
  const allocData = useMemo(() => parseAssetAllocation(allocRaw), [allocRaw]);
  const analysis = useMemo(() => parseFundAnalysis(analysisRaw), [analysisRaw]);
  const navData = useMemo(() => parseNavHistory(navRaw), [navRaw]);
  const holdings = useMemo(() => parseHoldings(holdingsRaw), [holdingsRaw]);

  // 风险收益数据转换（适配 DataGrid）
  const analysisGridData = useMemo(() => {
    if (!analysisRaw) return null;
    try {
      const lines = analysisRaw.trim().split('\n');
      if (lines.length < 2) return null;
      const headers = lines[0].split(',').map(h => h.trim());
      const periodIdx = headers.findIndex(h => h === '周期');
      const volIdx = headers.findIndex(h => h === '年化波动率');
      const sharpeIdx = headers.findIndex(h => h === '年化夏普比率');
      const drawdownIdx = headers.findIndex(h => h === '最大回撤');
      const result = {};
      for (const line of lines.slice(1)) {
        const parts = line.split(',').map(v => v.trim());
        const period = parts[periodIdx]?.trim();
        if (period === '近1年') {
          result.vol_1y = parseFloat(parts[volIdx]) || 0;
          result.sharpe_1y = parseFloat(parts[sharpeIdx]) || 0;
          result.drawdown_1y = parseFloat(parts[drawdownIdx]) || 0;
        } else if (period === '近3年') {
          result.vol_3y = parseFloat(parts[volIdx]) || 0;
          result.sharpe_3y = parseFloat(parts[sharpeIdx]) || 0;
          result.drawdown_3y = parseFloat(parts[drawdownIdx]) || 0;
        }
      }
      return Object.keys(result).length > 0 ? result : null;
    } catch { return null; }
  }, [analysisRaw]);

  const chartSeries = useMemo(() => [
    { key: 'nav', name: '单位净值', color: '#D4A853', type: 'line' },
    { key: 'growth', name: '日增长率', color: '#5B8FA8', type: 'bar', yAxisIndex: 1 },
  ], []);

  // 跳转到个股
  const navToStock = (stockCode, stockName) => {
    useAppStore.getState().setStockSearchKeyword(stockCode);
    useAppStore.getState().setActiveMicroSub('stock');
  };

  const displayName = info['基金名称'] || name || code;
  const fundType = info['基金类型'] || '—';
  const fundScale = info['最新规模'] || '—';
  const fundManager = info['基金经理'] || '—';
  const establishDate = info['成立时间'] || '—';
  const benchmark = info['业绩比较基准'] || '—';

  return (
    <div>
      {/* 返回按钮 + 标题 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button onClick={onBack} style={{
          padding: '6px 16px', borderRadius: 20,
          background: 'rgba(212,168,83,0.15)', border: '1px solid var(--accent-gold)',
          color: 'var(--accent-gold)', cursor: 'pointer', fontWeight: 700, fontSize: 13,
        }}>← 返回基金列表</button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 800, color: 'var(--accent-gold)', margin: 0 }}>{displayName}</h2>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2 }}>
            {code} · {fundType} · 规模{fundScale} · 基金经理{fundManager} · 成立{establishDate}
          </div>
        </div>
      </div>

      {/* 基金概况卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 14, marginBottom: 20 }}>
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>📋 基金档案</h3>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
            <div><span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>业绩基准：</span>{benchmark}</div>
            <div><span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>托管银行：</span>{info['托管银行'] || '—'}</div>
            <div><span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>投资目标：</span>{info['投资目标'] || '—'}</div>
            <div style={{ maxHeight: 80, overflow: 'auto', marginTop: 4 }}>
              <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>投资策略：</span>{info['投资策略'] || '—'}
            </div>
          </div>
        </CardWrapper>

        {/* 资产配置 */}
        {allocData && (
          <CardWrapper style={{ padding: 16 }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>💼 资产配置</h3>
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
      </div>

      {/* 风险收益分析 DataGrid */}
      {analysisGridData && (
        <div style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>📊 风险收益分析</h3>
          <DataGrid config={ANALYSIS_CONFIG} data={analysisGridData} prevData={{}} columns={3} gap={14} />
        </div>
      )}

      {/* 净值走势图 */}
      {navData.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>📈 净值走势</h3>
          <CardWrapper style={{ padding: 12 }}>
            <DataChart data={navData} series={chartSeries} dateKey="period" height={320} />
          </CardWrapper>
        </div>
      )}

      {/* 持仓明细表 */}
      {holdings.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>🔍 十大持仓股票</h3>
          <CardWrapper style={{ padding: 16 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(212,168,83,0.2)' }}>
                  <th style={{ padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 600, textAlign: 'left' }}>股票代码</th>
                  <th style={{ padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 600, textAlign: 'left' }}>股票名称</th>
                  <th style={{ padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 600, textAlign: 'right' }}>占净值比例</th>
                  <th style={{ padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 600, textAlign: 'center' }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {holdings.slice(0, 10).map((h, i) => (
                  <tr key={h.code} style={{ borderBottom: '1px solid rgba(212,168,83,0.08)' }}>
                    <td style={{ padding: '6px 8px', color: 'var(--text-secondary)' }}>{h.code}</td>
                    <td style={{
                      padding: '6px 8px', color: 'var(--accent-gold)', fontWeight: 700,
                      cursor: 'pointer',
                    }} onClick={() => navToStock(h.code, h.name)}>{h.name}</td>
                    <td style={{ padding: '6px 8px', color: 'var(--text-primary)', textAlign: 'right', fontWeight: 700 }}>{h.ratio}%</td>
                    <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                      <button onClick={() => navToStock(h.code, h.name)} style={{
                        padding: '3px 10px', borderRadius: 4, fontSize: 11,
                        background: 'rgba(212,168,83,0.15)', border: '1px solid var(--border-subtle)',
                        color: 'var(--accent-gold)', cursor: 'pointer',
                      }}>查看个股</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardWrapper>
        </div>
      )}
    </div>
  );
}
