import {useCallback, useEffect, useRef, useState} from 'react';
import {useMCP} from '../../hooks/useMCP.js';
import {useAppStore} from '../../store/index.js';
import DataGrid from '../common/DataGrid.jsx';
import DataChart from '../common/DataChart.jsx';
import {STOCK_FINANCE_CONFIG} from '../../configs/stockFinance.js';
import AntiFraudPanel from './AntiFraudPanel.jsx';
import UpdateTimestamp from '../common/UpdateTimestamp.jsx';

function parseKline(csv) {
  if (!csv) return [];
  const match = csv.match(/=== K线数据 ===\n([\s\S]+?)\n\n/);
  if (!match) return [];
  const lines = match[1].trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',');
  const dateIdx = headers.findIndex(h => h === '日期' || h === 'date');
  const closeIdx = headers.findIndex(h => h === '收盘' || h === 'close');
  const volumeIdx = headers.findIndex(h => h === '成交量' || h === 'volume');
  if (closeIdx === -1) return [];
  return lines.slice(1).map(l => {
    const parts = l.split(',');
    return {
      period: dateIdx !== -1 ? parts[dateIdx]?.slice(5) : '',
      close: parseFloat(parts[closeIdx]),
      volume: volumeIdx !== -1 ? parseInt(parts[volumeIdx]) : 0,
    };
  }).filter(d => !isNaN(d.close)).slice(-120);
}

function parseFinancial(csv) {
  if (!csv) return {};
  // 定位 === 财务指标 === 段落
  const sectionMatch = csv.match(/=== 财务指标 ===\n([\s\S]+?)(?:\n\n|$)/);
  if (!sectionMatch) return {};
  const section = sectionMatch[1].trim();
  const lines = section.split('\n').filter(l => l.trim());
  if (lines.length < 2) return {};
  const headers = lines[0].split(',').map(h => h.trim());
  // 取最后一行有效数据（跳过空值过多的行）
  let last = null;
  for (let i = lines.length - 1; i >= 1; i--) {
    const parts = lines[i].split(',').map(v => v.trim());
    if (parts.length === headers.length) { last = parts; break; }
  }
  if (!last) return {};
  const result = {};
  headers.forEach((h, i) => { result[h] = last[i]; });
  // parseFloat 安全包装：空字符串/无效值返回 null（DataCard 显示 "—"）
  const safeParse = (v) => { const n = parseFloat(v); return isNaN(n) ? null : n; };
  return {
    revenue_growth: safeParse(result['主营业务收入增长率(%)']),
    profit_growth: safeParse(result['净利润增长率(%)']),
    roe: safeParse(result['净资产收益率(%)']),
    gross_margin: safeParse(result['销售毛利率(%)']),
  };
}

/** 根据股票代码推断市场: 6→sh, 0/3→sz, 8/4→bj */
function guessMarket(code) {
  if (!code || code.length < 1) return 'sh';
  const first = code[0];
  if (first === '6') return 'sh';
  if (first === '0' || first === '3') return 'sz';
  if (first === '8' || first === '4') return 'bj';
  return 'sh';
}

/** 判断输入是否为股票代码（6位数字或5位港股） */
function isStockCode(input) {
  return /^\d{5,6}$/.test(input.trim());
}

/** 解析搜索结果（后端返回 JSON） */
function parseSearchResult(text) {
  if (!text) return { code: '', name: '' };
  try {
    const parsed = JSON.parse(text);
    return { code: parsed.code || '', name: parsed.name || '' };
  } catch {
    // 兼容旧格式纯文本
    const lines = text.trim().split('\n');
    let code = '', name = '';
    for (const line of lines) {
      const parts = line.trim().split(/\s{2,}|\t/);
      const key = parts[0]?.trim();
      const val = parts.slice(1).join(' ').trim();
      if (['code', '证券代码', 'A股代码', 'symbol', '基金代码', '代码'].includes(key) && val) code = val;
      if (['name', '证券简称', 'A股简称', 'cname', '基金名称', '名称', '中文名称'].includes(key) && val) name = val;
    }
    return { code, name };
  }
}

export default function StockPanel() {
  const [keyword, setKeyword] = useState('');
  const [symbol, setSymbol] = useState('');
  const [stockName, setStockName] = useState('');
  const [market, setMarket] = useState('sh');
  const [showAntiFraud, setShowAntiFraud] = useState(false);
  const debounceRef = useRef(null);

  // 从 store 读取跨页面跳转的搜索关键词
  const storeKeyword = useAppStore((s) => s.stockSearchKeyword);
  useEffect(() => {
    if (storeKeyword) {
      console.log('[StockPanel] 接收到跳转关键词:', storeKeyword);
      setKeyword(storeKeyword);
      setSymbol(storeKeyword);
      setMarket(guessMarket(storeKeyword));
      // 清空 store 中的关键词，避免重复触发
      useAppStore.getState().setStockSearchKeyword('');
    }
  }, [storeKeyword]);

  // 搜索：仅 keyword 非空且不是纯代码时触发
  const isCode = isStockCode(keyword);
  const { data: searchRes, refetch } = useMCP('search', (keyword && !isCode) ? { keyword, market } : null);

  // K线和财务指标：只在 symbol 非空时查询
  const { data: klineRaw, updatedAt } = useMCP('individual_hist', symbol ? { symbol, period: 'daily', limit: 120 } : null);
  const { data: finRaw } = useMCP('financial_indicators', symbol ? { symbol } : null);

  const doSearch = useCallback(() => {
    if (!keyword.trim()) return;
    if (isStockCode(keyword)) {
      // 直接输入代码，跳过搜索
      setSymbol(keyword.trim());
      setMarket(guessMarket(keyword.trim()));
      setStockName('');
      return;
    }
    refetch();
  }, [keyword, refetch]);

  // 搜索结果解析
  useEffect(() => {
    if (searchRes) {
      const { code, name } = parseSearchResult(searchRes);
      if (code) {
        setSymbol(code);
        setMarket(guessMarket(code));
      }
      if (name) setStockName(name);
    }
  }, [searchRes]);

  // 输入防抖：代码型输入即时生效
  useEffect(() => {
    if (!keyword.trim()) return;
    if (isStockCode(keyword)) {
      setSymbol(keyword.trim());
      setMarket(guessMarket(keyword.trim()));
      return;
    }
    // 名称搜索防抖 500ms
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      refetch();
    }, 500);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [keyword]);

  const klineData = parseKline(klineRaw);
  const finData = parseFinancial(finRaw);
  const chartSeries = [{ key: 'close', name: '收盘价', color: '#d2991d', type: 'line' }];

  // 显示反诈面板时
  if (showAntiFraud && symbol) {
    return (
      <AntiFraudPanel
        symbol={symbol}
        name={stockName}
        onBack={() => setShowAntiFraud(false)}
      />
    );
  }

  return (
    <div>
      <UpdateTimestamp updatedAt={updatedAt} />
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <input
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && doSearch()}
          placeholder="股票代码/名称（输入代码直接查询）"
          style={{ flex: 1, padding: '8px 14px', borderRadius: 12, border: '1px solid var(--border-subtle)', background: 'var(--bg-panel)', color: 'var(--text-primary)' }}
        />
        <button onClick={doSearch} style={{ padding: '8px 22px', borderRadius: 20, background: 'var(--accent-gold)', color: '#000', border: 'none', cursor: 'pointer' }}>🔍 查询</button>
        {symbol && (
          <button onClick={() => setShowAntiFraud(true)} style={{ padding: '8px 16px', borderRadius: 20, background: 'rgba(212,168,83,0.1)', border: '1px solid var(--accent-gold)', color: 'var(--accent-gold)', cursor: 'pointer' }}>🛡️ 反诈分析</button>
        )}
      </div>
      <div style={{ marginBottom: 20, padding: '12px 20px', background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius)', border: '1px solid var(--border-subtle)' }}>
        <span style={{ fontSize: 18, fontWeight: 700 }}>{stockName || '—'}</span>
        <span style={{ marginLeft: 12, color: 'var(--text-muted)' }}>{symbol ? `${symbol}.${market.toUpperCase()}` : '请输入代码查询'}</span>
      </div>
      <DataChart data={klineData} series={chartSeries} dateKey="period" height={300} />
      <DataGrid config={STOCK_FINANCE_CONFIG} data={finData} prevData={{}} columns={4} gap={16} />
    </div>
  );
}