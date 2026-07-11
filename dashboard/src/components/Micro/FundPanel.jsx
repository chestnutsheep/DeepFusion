import {useEffect, useMemo, useState} from 'react';
import {useMCP} from '../../hooks/useMCP.js';
import {useAppStore} from '../../store/index.js';
import CardWrapper from '../common/CardWrapper.jsx';
import FundDetailPage from './FundDetailPage.jsx';
import UpdateTimestamp from '../common/UpdateTimestamp.jsx';

/* ═══ CSV 解析 ═══ */
function parseCsv(raw) {
  if (!raw) return [];
  try {
    const lines = raw.trim().split('\n');
    if (lines.length < 2) return [];
    const headers = lines[0].split(',').map(h => h.trim());
    return lines.slice(1).map(l => {
      const parts = l.split(',');
      const row = {};
      headers.forEach((h, i) => { row[h] = (parts[i] || '').trim(); });
      return row;
    });
  } catch { return []; }
}

function parseRanking(raw) {
  return parseCsv(raw).map(r => ({
    code: r['基金代码'] || '',
    name: r['基金简称'] || '',
    nav: parseFloat(r['单位净值']) || 0,
    accNav: parseFloat(r['累计净值']) || 0,
    dailyGrowth: parseFloat(r['日增长率']) || 0,
    week1: parseFloat(r['近1周']) || 0,
    month1: parseFloat(r['近1月']) || 0,
    month3: parseFloat(r['近3月']) || 0,
    month6: parseFloat(r['近6月']) || 0,
    year1: parseFloat(r['近1年']) || 0,
    year3: parseFloat(r['近3年']) || 0,
    ytd: parseFloat(r['今年来']) || 0,
    sinceInception: parseFloat(r['成立来']) || 0,
  })).filter(r => r.code && r.name);
}

function parseHoldings(raw) {
  return parseCsv(raw).map(r => ({
    code: r['股票代码'] || '',
    name: r['股票名称'] || '',
    ratio: parseFloat(r['占净值比例']) || 0,
  })).filter(h => h.code && h.name);
}

/* ═══ 行业关键词 ═══ */
const INDUSTRY_KEYWORDS = {
  '军工': ['军工', '国防', '航天', '航空'],
  '半导体': ['半导体', '芯片', '集成电路'],
  '新能源': ['新能源', '光伏', '锂电', '风电'],
  '医药': ['医药', '医疗', '生物', '健康', '创新药'],
  '消费': ['消费', '白酒', '食品', '零售'],
  '科技': ['科技', '互联网', '人工智能', 'AI'],
  '金融': ['金融', '银行', '证券', '保险'],
  '地产': ['地产', '房地产', '基建'],
  '材料': ['材料', '化工', '有色', '钢铁', '煤炭'],
  '环保': ['环保', '绿色', 'ESG'],
};

function classifyFundByName(name) {
  for (const [ind, kws] of Object.entries(INDUSTRY_KEYWORDS)) {
    if (kws.some(kw => name.includes(kw))) return ind;
  }
  return '综合';
}

function classifyFundRow(fund) {
  const n = fund.name || '';
  if (n.includes('ETF')) return { type: 'ETF', style: '被动' };
  if (n.includes('QDII') || n.includes('沪港深')) return { type: 'QDII', style: '跨境' };
  if (n.includes('LOF')) return { type: 'LOF', style: '上市型' };
  if (n.includes('指数') || /\d{3,4}/.test(n)) return { type: '指数型', style: '被动' };
  if (n.includes('债')) return { type: '债券型', style: n.includes('增强') ? '增强' : '纯债' };
  if (n.includes('混合') || n.includes('灵活')) return { type: '混合型', style: '灵活配置' };
  if (n.includes('股票')) return { type: '股票型', style: '主动' };
  const ind = classifyFundByName(n);
  return ind !== '综合' ? { type: '股票型', style: ind } : { type: '—', style: '—' };
}

/* ═══ 颜色 ═══ */
const TYPE_COLORS = {
  '股票型': '#D4A853', '混合型': '#5B8FA8', '债券型': '#3E6B5C',
  '指数型': '#8980d3', 'QDII': '#de71b2', 'ETF': '#5ca066', '—': '#888',
};
const INDUSTRY_COLORS = {
  '军工': '#8980d3', '半导体': '#de71b2', '新能源': '#5ca066',
  '医药': '#5B8FA8', '消费': '#D4A853', '科技': '#bc5d5d',
  '金融': '#3E6B5C', '地产': '#C49BA5', '材料': '#ca9c42',
  '环保': '#5B8FA8', '综合': '#888',
};
function pctColor(v) { return v > 0 ? '#3fb950' : v < 0 ? '#f85149' : 'var(--text-muted)'; }

/* ═══ 常量 ═══ */
const RANKING_TYPES = ['全部', '股票型', '混合型', '债券型', '指数型', 'QDII', 'ETF'];
const RANKING_PERIODS = [
  { key: 'dailyGrowth', label: '日涨幅' },
  { key: 'week1', label: '近1周' },
  { key: 'month1', label: '近1月' },
  { key: 'month3', label: '近3月' },
  { key: 'year1', label: '近1年' },
];

/* ══════════════════════════════════════
   主面板
   ══════════════════════════════════════ */
export default function FundPanel() {
  const [detailCode, setDetailCode] = useState(null);
  const [detailName, setDetailName] = useState(null);

  // store 跳转
  const storeFundCode = useAppStore((s) => s.fundDetailCode);
  const storeFundName = useAppStore((s) => s.fundDetailName);
  useEffect(() => {
    if (storeFundCode) {
      setDetailCode(storeFundCode);
      setDetailName(storeFundName);
      useAppStore.getState().clearFundDetail();
    }
  }, [storeFundCode]);

  // 龙虎榜排名
  const [rankType, setRankType] = useState('股票型');
  const [rankPeriod, setRankPeriod] = useState('dailyGrowth');
  const { data: rankingRaw, isLoading: rankLoading, updatedAt } = useMCP('fund_ranking', { fund_type: rankType });
  const rankingData = useMemo(() => parseRanking(rankingRaw), [rankingRaw]);

  // 行业分类 + 持仓重叠
  const [selectedIndustry, setSelectedIndustry] = useState(null);
  const { data: allRankingRaw } = useMCP('fund_ranking', { fund_type: '全部' });
  const allRankingData = useMemo(() => parseRanking(allRankingRaw), [allRankingRaw]);

  const industryGroups = useMemo(() => {
    const groups = {};
    for (const fund of allRankingData.slice(0, 50)) {
      const ind = classifyFundByName(fund.name);
      if (!groups[ind]) groups[ind] = [];
      groups[ind].push(fund);
    }
    return groups;
  }, [allRankingData]);

  const industryFunds = selectedIndustry ? (industryGroups[selectedIndustry] || []).slice(0, 5) : [];

  // 批量查询持仓
  const h0 = useMCP('fund_holdings', industryFunds[0] ? { code: industryFunds[0].code } : null);
  const h1 = useMCP('fund_holdings', industryFunds[1] ? { code: industryFunds[1].code } : null);
  const h2 = useMCP('fund_holdings', industryFunds[2] ? { code: industryFunds[2].code } : null);
  const h3 = useMCP('fund_holdings', industryFunds[3] ? { code: industryFunds[3].code } : null);
  const h4 = useMCP('fund_holdings', industryFunds[4] ? { code: industryFunds[4].code } : null);

  const allHoldings = useMemo(() =>
    [h0, h1, h2, h3, h4].map(r => parseHoldings(r.data)),
    [h0.data, h1.data, h2.data, h3.data, h4.data]
  );

  const overlapStocks = useMemo(() => {
    const sc = {};
    for (let fi = 0; fi < allHoldings.length; fi++) {
      for (const h of allHoldings[fi].slice(0, 10)) {
        if (!sc[h.code]) sc[h.code] = { code: h.code, name: h.name, count: 0, totalRatio: 0, funds: [] };
        sc[h.code].count += 1;
        sc[h.code].totalRatio += h.ratio;
        sc[h.code].funds.push(industryFunds[fi]?.name || '');
      }
    }
    return Object.values(sc)
      .filter(s => s.count >= 2)
      .sort((a, b) => b.count - a.count || b.totalRatio - a.totalRatio)
      .slice(0, 10);
  }, [allHoldings, industryFunds]);

  // 排名排序
  const sortedRanking = useMemo(() => {
    const sorted = [...rankingData].sort((a, b) => (b[rankPeriod] || 0) - (a[rankPeriod] || 0));
    return { top5: sorted.slice(0, 5), bottom5: sorted.slice(-5).reverse() };
  }, [rankingData, rankPeriod]);

  const goToDetail = (code, name) => { setDetailCode(code); setDetailName(name); };
  const navToStock = (stockCode) => {
    useAppStore.getState().setStockSearchKeyword(stockCode);
    useAppStore.getState().setActiveMicroSub('stock');
  };

  // 详情模式
  if (detailCode) {
    return <FundDetailPage code={detailCode} name={detailName} onBack={() => { setDetailCode(null); setDetailName(null); }} />;
  }

  const periodLabel = RANKING_PERIODS.find(p => p.key === rankPeriod)?.label || '日涨幅';

  // ── 表格列样式 ──
  const TH = { padding: '5px 6px', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11 };

  return (
    <div>
      <UpdateTimestamp updatedAt={updatedAt} />
      {/* ═══ 第一部分：龙虎榜 ═══ */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: 16, fontWeight: 800, color: 'var(--accent-gold)', margin: 0 }}>🏆 基金龙虎榜</h2>
          <div style={{ display: 'flex', gap: 4 }}>
            {RANKING_PERIODS.map(p => (
              <button key={p.key} onClick={() => setRankPeriod(p.key)} style={{
                padding: '4px 12px', borderRadius: 4, fontSize: 11,
                background: rankPeriod === p.key ? 'rgba(212,168,83,0.35)' : 'transparent',
                color: rankPeriod === p.key ? '#D4A853' : 'var(--text-secondary)',
                border: `1px solid ${rankPeriod === p.key ? 'rgba(212,168,83,0.6)' : 'var(--border-subtle)'}`,
                cursor: 'pointer', fontWeight: rankPeriod === p.key ? 700 : 500,
              }}>{p.label}</button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            {RANKING_TYPES.map(t => (
              <button key={t} onClick={() => setRankType(t)} style={{
                padding: '4px 10px', borderRadius: 4, fontSize: 11,
                background: rankType === t ? 'rgba(212,168,83,0.35)' : 'transparent',
                color: rankType === t ? '#D4A853' : 'var(--text-secondary)',
                border: `1px solid ${rankType === t ? 'rgba(212,168,83,0.6)' : 'var(--border-subtle)'}`,
                cursor: 'pointer', fontWeight: rankType === t ? 700 : 500,
              }}>{t}</button>
            ))}
          </div>
        </div>

        {rankLoading && <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>加载中...</div>}

        {/* TOP5 */}
        {sortedRanking.top5.length > 0 && (
          <CardWrapper style={{ padding: 16, marginBottom: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#3fb950', marginBottom: 8 }}>
              📈 涨幅最高 TOP5 ({periodLabel})
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead><tr style={{ borderBottom: '1px solid rgba(212,168,83,0.2)' }}>
                <th style={{...TH, textAlign: 'left', width: '26%' }}>基金名称</th>
                <th style={{...TH, textAlign: 'right', width: '11%' }}>涨跌幅</th>
                <th style={{...TH, textAlign: 'right', width: '10%' }}>净值</th>
                <th style={{...TH, textAlign: 'center', width: '10%' }}>基金类型</th>
                <th style={{...TH, textAlign: 'center', width: '10%' }}>基金风格</th>
                <th style={{...TH, textAlign: 'right', width: '11%' }}>今年来</th>
                <th style={{...TH, textAlign: 'right', width: '11%' }}>近1年</th>
                <th style={{...TH, textAlign: 'right', width: '11%' }}>近3年</th>
              </tr></thead>
              <tbody>
                {sortedRanking.top5.map((f, i) => <RankRow key={f.code} fund={f} idx={i+1} pk={rankPeriod} onClick={goToDetail} />)}
              </tbody>
            </table>
          </CardWrapper>
        )}

        {/* BOTTOM5 */}
        {sortedRanking.bottom5.length > 0 && (
          <CardWrapper style={{ padding: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#f85149', marginBottom: 8 }}>
              📉 涨幅最低 TOP5 ({periodLabel})
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead><tr style={{ borderBottom: '1px solid rgba(212,168,83,0.2)' }}>
                <th style={{...TH, textAlign: 'left', width: '26%' }}>基金名称</th>
                <th style={{...TH, textAlign: 'right', width: '11%' }}>涨跌幅</th>
                <th style={{...TH, textAlign: 'right', width: '10%' }}>净值</th>
                <th style={{...TH, textAlign: 'center', width: '10%' }}>基金类型</th>
                <th style={{...TH, textAlign: 'center', width: '10%' }}>基金风格</th>
                <th style={{...TH, textAlign: 'right', width: '11%' }}>今年来</th>
                <th style={{...TH, textAlign: 'right', width: '11%' }}>近1年</th>
                <th style={{...TH, textAlign: 'right', width: '11%' }}>近3年</th>
              </tr></thead>
              <tbody>
                {sortedRanking.bottom5.map((f, i) => <RankRow key={f.code} fund={f} idx={rankingData.length-i} pk={rankPeriod} onClick={goToDetail} />)}
              </tbody>
            </table>
          </CardWrapper>
        )}
      </div>

      <hr className="section-divider" />

      {/* ═══ 第二部分：行业基金持仓分析 ═══ */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <h2 style={{ fontSize: 16, fontWeight: 800, color: 'var(--accent-gold)', margin: 0 }}>🏭 行业基金持仓分析</h2>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>查看同行业基金的持仓重叠股票</span>
        </div>

        <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
          {Object.entries(INDUSTRY_KEYWORDS).map(([ind]) => {
            const cnt = (industryGroups[ind] || []).length;
            const sel = selectedIndustry === ind;
            return (
              <button key={ind} onClick={() => setSelectedIndustry(sel ? null : ind)} style={{
                padding: '5px 14px', borderRadius: 6, fontSize: 12,
                background: sel ? INDUSTRY_COLORS[ind]+'30' : 'transparent',
                color: sel ? INDUSTRY_COLORS[ind] : 'var(--text-secondary)',
                border: `1px solid ${sel ? INDUSTRY_COLORS[ind]+'80' : 'var(--border-subtle)'}`,
                cursor: 'pointer', fontWeight: sel ? 700 : 500,
              }}>{ind} ({cnt})</button>
            );
          })}
          <button onClick={() => setSelectedIndustry(null)} style={{
            padding: '5px 14px', borderRadius: 6, fontSize: 12,
            background: !selectedIndustry ? 'rgba(212,168,83,0.15)' : 'transparent',
            color: !selectedIndustry ? 'var(--accent-gold)' : 'var(--text-muted)',
            border: `1px solid ${!selectedIndustry ? 'rgba(212,168,83,0.6)' : 'var(--border-subtle)'}`,
            cursor: 'pointer',
          }}>全部</button>
        </div>

        {selectedIndustry && industryFunds.length > 0 && (
          <CardWrapper style={{ padding: 16, marginBottom: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: INDUSTRY_COLORS[selectedIndustry], marginBottom: 10 }}>
              📦 {selectedIndustry}行业基金 (前5只)
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {industryFunds.map(f => (
                <div key={f.code} style={{
                  padding: '6px 12px', borderRadius: 6,
                  background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-subtle)',
                  fontSize: 12,
                }}>
                  <span style={{ color: 'var(--accent-gold)', cursor: 'pointer', fontWeight: 700 }} onClick={() => goToDetail(f.code, f.name)}>{f.name}</span>
                  <span style={{ marginLeft: 6, color: pctColor(f.dailyGrowth) }}>{f.dailyGrowth}%</span>
                </div>
              ))}
            </div>
          </CardWrapper>
        )}

        {selectedIndustry && overlapStocks.length > 0 && (
          <CardWrapper style={{ padding: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-gold)', marginBottom: 10 }}>
              🔗 持仓重叠 TOP10
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead><tr style={{ borderBottom: '1px solid rgba(212,168,83,0.2)' }}>
                <th style={{...TH, textAlign: 'center', width: '8%' }}>重叠</th>
                <th style={{...TH, textAlign: 'left', width: '15%' }}>股票代码</th>
                <th style={{...TH, textAlign: 'left', width: '22%' }}>股票名称</th>
                <th style={{...TH, textAlign: 'right', width: '12%' }}>合计占比</th>
                <th style={{...TH, textAlign: 'left', width: '33%' }}>来源基金</th>
                <th style={{...TH, textAlign: 'center', width: '10%' }}>操作</th>
              </tr></thead>
              <tbody>
                {overlapStocks.map(s => (
                  <tr key={s.code} style={{ borderBottom: '1px solid rgba(212,168,83,0.08)' }}>
                    <td style={{ padding: '5px 8px', textAlign: 'center' }}>
                      <span style={{
                        background: s.count>=4?'#D4A85330':s.count>=3?'#8980d320':'#5B8FA820',
                        color: s.count>=4?'#D4A853':s.count>=3?'#8980d3':'#5B8FA8',
                        padding: '2px 6px', borderRadius: 3, fontWeight: 700, fontSize: 11,
                      }}>{s.count}</span>
                    </td>
                    <td style={{ padding: '5px 8px', color: 'var(--text-secondary)' }}>{s.code}</td>
                    <td style={{ padding: '5px 8px', color: 'var(--accent-gold)', fontWeight: 700, cursor: 'pointer' }}
                      onClick={() => navToStock(s.code)}>{s.name}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', fontWeight: 700 }}>{s.totalRatio.toFixed(1)}%</td>
                    <td style={{ padding: '5px 8px', color: 'var(--text-muted)', fontSize: 11 }}>{s.funds.filter(Boolean).join(', ')}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'center' }}>
                      <button onClick={() => navToStock(s.code)} style={{
                        padding: '3px 8px', borderRadius: 4, fontSize: 11,
                        background: 'rgba(212,168,83,0.15)', border: '1px solid var(--border-subtle)',
                        color: 'var(--accent-gold)', cursor: 'pointer',
                      }}>查看</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardWrapper>
        )}

        {selectedIndustry && overlapStocks.length === 0 && (
          <CardWrapper style={{ padding: 16 }}>
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>持仓数据加载中...</div>
          </CardWrapper>
        )}

        {!selectedIndustry && (
          <CardWrapper style={{ padding: 16 }}>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', textAlign: 'center' }}>
              点击行业按钮查看该行业基金的持仓重叠分析
            </div>
          </CardWrapper>
        )}
      </div>
    </div>
  );
}

/* ═══ 排名行 ═══ */
function RankRow({ fund, idx, pk, onClick }) {
  const { type, style } = classifyFundRow(fund);
  const pct = fund[pk] || 0;
  const tc = TYPE_COLORS[type] || '#888';
  return (
    <tr style={{ borderBottom: '1px solid rgba(212,168,83,0.08)' }}>
      <td style={{ padding: '5px 6px' }}>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', marginRight: 4 }}>#{idx}</span>
        <span style={{ color: 'var(--accent-gold)', fontWeight: 700, cursor: 'pointer' }} onClick={() => onClick(fund.code, fund.name)}>{fund.name}</span>
      </td>
      <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 700, color: pctColor(pct) }}>{pct.toFixed(2)}%</td>
      <td style={{ padding: '5px 6px', textAlign: 'right' }}>{fund.nav.toFixed(4)}</td>
      <td style={{ padding: '5px 6px', textAlign: 'center' }}>
        <span style={{ fontSize: 10, padding: '1px 4px', borderRadius: 3, background: tc+'20', color: tc, fontWeight: 600 }}>{type}</span>
      </td>
      <td style={{ padding: '5px 6px', textAlign: 'center', fontSize: 11, color: 'var(--text-muted)' }}>{style}</td>
      <td style={{ padding: '5px 6px', textAlign: 'right', fontWeight: 700, color: pctColor(fund.ytd) }}>{fund.ytd ? fund.ytd.toFixed(2)+'%' : '—'}</td>
      <td style={{ padding: '5px 6px', textAlign: 'right', color: pctColor(fund.year1) }}>{fund.year1 ? fund.year1.toFixed(2)+'%' : '—'}</td>
      <td style={{ padding: '5px 6px', textAlign: 'right', color: pctColor(fund.year3) }}>{fund.year3 ? fund.year3.toFixed(2)+'%' : '—'}</td>
    </tr>
  );
}
