import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {useQueryClient} from '@tanstack/react-query';
import {useMCP} from '../../hooks/useMCP';
import {mcp} from '../../services/mcp.js';
import {useAppStore} from '../../store/index.js';
import DataChart from '../common/DataChart';
import DataCard from '../common/DataCard';
import CardWrapper from '../common/CardWrapper';
import ErrorBoundary from '../common/ErrorBoundary';
import UpdateTimestamp from '../common/UpdateTimestamp.jsx';
import SectionHeader from '../common/SectionHeader';
import * as echarts from 'echarts';
import TrendsAndSignals, {WarningBar} from './TrendsAndSignals';
import SeasonalCorrelation from './SeasonalCorrelation';

// ── CSV 解析工具 ──

/** 安全解析浮点数，无效值返回 null（DataCard 会显示 "—"） */
const safeFloat = (v) => { const n = parseFloat(v); return isNaN(n) ? null : n; };

/** 通用：解析 CSV 表头 → 列名→索引映射 */
function buildColMap(headerLine) {
  const headers = headerLine.split(',').map(h => h.trim());
  const m = {};
  headers.forEach((h, i) => { m[h] = i; });
  return m;
}

/**
 * 解析 industry_sw_daily 返回的 CSV（akshare index_analysis_daily_sw）。
 * 使用表头列名映射，避免 akshare 列序变更导致静默错位。
 *
 * 返回 { industries: 按行业名索引的最新快照, dates: 所有日期, matrix: 行业×日期涨跌幅矩阵 }
 */
function parseSWDaily(csv) {
  if (!csv) return { industries: [], dates: [], matrix: {} };
  const lines = csv.trim().split('\n');
  if (lines.length < 2) return { industries: [], dates: [], matrix: {} };

  // 建立列名映射
  const col = buildColMap(lines[0]);
  const iCode   = col['指数代码'] ?? 0;
  const iName   = col['指数名称'] ?? 1;
  const iDate   = col['发布日期'] ?? 2;
  const iClose  = col['收盘指数'] ?? 3;
  const iVol    = col['成交量'] ?? 4;
  const iChange = col['涨跌幅'] ?? 5;
  const iTurn   = col['换手率'] ?? 6;
  const iPe     = col['市盈率'] ?? 7;
  const iPb     = col['市净率'] ?? 8;
  const iAvg    = col['均价'] ?? 9;
  const iAmtR   = col['成交额占比'] ?? 10;
  const iMktCap = col['流通市值'] ?? 11;

  const rows = lines.slice(1).map(l => l.split(','));

  // 收集所有日期（去重+排序）
  const dateSet = new Set();
  rows.forEach(r => { const d = r[iDate]?.trim(); if (d) dateSet.add(d); });
  const dates = [...dateSet].sort();

  // 按行业分组，取最新日期作为快照
  const byName = {};
  rows.forEach(r => {
    const name = r[iName]?.trim();
    if (!name) return;
    if (!byName[name]) byName[name] = [];
    byName[name].push({
      name,
      date: r[iDate]?.trim(),
      close: safeFloat(r[iClose]),
      volume: safeFloat(r[iVol]),
      change: safeFloat(r[iChange]),
      turnover: safeFloat(r[iTurn]),
      pe: safeFloat(r[iPe]),
      pb: safeFloat(r[iPb]),
      avgPrice: safeFloat(r[iAvg]),
      amountRatio: safeFloat(r[iAmtR]),
      mktCap: safeFloat(r[iMktCap]),
      code: r[iCode]?.trim(),
    });
  });

  // 每个行业按日期倒排，取最新一条作为快照
  const industries = [];
  const matrix = {};  // { industryName: { date: change% } }
  for (const [name, recs] of Object.entries(byName)) {
    recs.sort((a, b) => b.date.localeCompare(a.date));
    const latest = recs[0];
    industries.push(latest);
    // 构建矩阵
    matrix[name] = {};
    recs.forEach(r => { if (r.change != null) matrix[name][r.date] = r.change; });
  }

  return { industries, dates, matrix };
}

/**
 * 行业日线 CSV — 来自 industry_daily_query（SQLite meso_industry_daily 表）。
 * 列: industry_code, trade_date, open, close, high, low, volume, amount, change_pct, turnover_rate
 */
function parseDaily(csv) {
  if (!csv) return [];
  const lines = csv.trim().split('\n');
  if (lines.length < 2) return [];

  const col = buildColMap(lines[0]);
  const iDate  = col['trade_date'] ?? 1;
  const iClose = col['close'] ?? 3;
  const iVol   = col['volume'] ?? 6;
  const iAmt   = col['amount'] ?? 7;
  const iChg   = col['change_pct'] ?? 8;
  const iTurn  = col['turnover_rate'] ?? 9;

  return lines.slice(1).map(l => {
    const p = l.split(',');
    return {
      period: (p[iDate] || '').trim().slice(5),
      close: safeFloat(p[iClose]),
      volume: safeFloat(p[iVol]),
      amount: safeFloat(p[iAmt]),
      change: safeFloat(p[iChg]),
      turnover: safeFloat(p[iTurn]),
    };
  }).filter(d => d.close != null).slice(-120);
}

// ── 区块组件 ──

/** 英雄区 — 只展示实际数据信息，不堆砌废话 */
function Hero({ industries, dates }) {
  const topInd = industries.length > 0
    ? [...industries].sort((a, b) => (b.change || 0) - (a.change || 0))[0]
    : null;
  const bottomInd = industries.length > 0
    ? [...industries].sort((a, b) => (a.change || 0) - (b.change || 0))[0]
    : null;
  const latestDate = dates.length > 0 ? dates[dates.length - 1] : '—';
  const avgChange = industries.length > 0
    ? industries.reduce((s, i) => s + (i.change || 0), 0) / industries.length
    : null;
  return (
    <div style={{
      padding: '28px 0 16px',
      borderBottom: '1px solid var(--border-subtle)',
      marginBottom: 24,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{
          display: 'inline-block', padding: '4px 14px',
          background: 'var(--shadow-glow)', border: '1px solid var(--border-subtle)',
          borderRadius: 20, fontSize: 'var(--fs-sm)', fontWeight: 600,
          color: 'var(--accent-gold)',
        }}>✦ 中观产业</span>
        <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 700, color: 'var(--accent-gold)', background: 'rgba(212,168,83,0.1)', padding: '3px 10px', borderRadius: 12 }}>
          {latestDate}
        </span>
      </div>
      <h1 style={{ fontSize: 'var(--fs-2xl)', fontWeight: 700, letterSpacing: 0.5 }}>
        行业景气与 <span style={{ color: 'var(--accent-gold)' }}>产业链定位</span>
      </h1>
      <div style={{ display: 'flex', gap: 20, marginTop: 8, fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)', alignItems: 'center' }}>
        <span>覆盖 <b style={{ color: 'var(--text-primary)' }}>{industries.length}</b> 行业</span>
        {avgChange != null && (
          <span>均涨 <b style={{ color: avgChange >= 0 ? 'var(--accent-red)' : 'var(--accent-green)', fontWeight: 700 }}>{avgChange >= 0 ? '+' : ''}{avgChange.toFixed(2)}%</b></span>
        )}
        {topInd && topInd.change != null && (
          <span>领涨 <b style={{ color: 'var(--accent-red)' }}>{topInd.name} {topInd.change >= 0 ? '+' : ''}{topInd.change.toFixed(2)}%</b></span>
        )}
        {bottomInd && bottomInd.change != null && (
          <span>领跌 <b style={{ color: 'var(--accent-green)' }}>{bottomInd.name} {bottomInd.change >= 0 ? '+' : ''}{bottomInd.change.toFixed(2)}%</b></span>
        )}
      </div>
    </div>
  );
}

// ── 三分法行业分类 ──
// 强周期：传统经济周期高度敏感，与GDP/投资强相关
const CYCLICAL_NAMES = new Set([
  '采掘', '钢铁',                                         // 上游原材料(传统大宗)
  '房地产', '建筑装饰', '建筑材料',                         // 地产基建链
  '机械设备',                                               // Capex 周期
  '汽车',                                                   // 大件可选消费周期
  '非银金融',                                               // 市场周期(券商)
  '综合',                                                   // 难归类，归入周期
]);
// 强防御：穿越周期刚需，低Beta，稳定现金流
const DEFENSIVE_NAMES = new Set([
  '银行',                                                   // 低估值高分红
  '食品饮料',                                               // 必选消费
  '农林牧渔',                                               // 刚需
  '公用事业',                                               // 必选服务
  '交通运输',                                               // 基础设施
  '商业贸易',                                               // 基础消费/零售
  '纺织服装',                                               // 基础消费
  '轻工制造',                                               // 基础消费
  '家用电器',                                               // 偏刚需换代
  '美容护理',                                               // 传统消费
  '环保',                                                   // 公益属性，穿越周期
  '社会服务',                                               // 申万2021版(原休闲服务)，刚需服务
  '休闲服务',                                               // 申万2014版，刚需服务
]);
// 进攻型：高成长/高Beta + 第六次康波驱动(新能源金属/新材料/创新药/科技)
const GROWTH_NAMES = new Set([
  '有色金属',                                               // 第六次康波: 新能源金属(锂/钴/稀土)
  '化工',                                                   // 第六次康波: 新材料/半导体材料
  '电子', '计算机', '通信',                                 // TMT 科技
  '电气设备',                                               // 新能源/成长
  '国防军工',                                               // 高弹性
  '医药生物',                                               // 创新药/器械
  '传媒',                                                   // 游戏/内容
  '新能源汽车',                                             // 成长赛道
]);

// ── 分类配置表 ──
const CATEGORY_CONFIG = {
  cyclical:  { label: '🔄 强周期', names: CYCLICAL_NAMES,  accent: '#D4A853', desc: '经济周期敏感' },
  defensive: { label: '🛡️ 强防御', names: DEFENSIVE_NAMES, accent: '#5B8FA8', desc: '横盘抱团刚需' },
  growth:    { label: '⚔️ 进攻型', names: GROWTH_NAMES,    accent: '#C47B7B', desc: '高成长高Beta;风险收益成正比' },
  custom:    { label: '⭐ 自选',   names: null,             accent: '#9B7EC8', desc: '自选行业热力图' },
};

// ── 自选组合持久化 ──
const COMBO_STORAGE_KEY = 'meso_saved_combos';
const COMBO_COLORS = ['#C47B7B', '#7BAAC4', '#7BC47B', '#C4A87B', '#A87BC4', '#7BC4B8', '#C47BA8', '#B8C47B'];
function loadSavedCombos() {
  try { return JSON.parse(localStorage.getItem(COMBO_STORAGE_KEY) || '[]'); } catch { return []; }
}
function persistCombos(combos) {
  localStorage.setItem(COMBO_STORAGE_KEY, JSON.stringify(combos));
}

// ── 强周期行业的三周期映射 ──
// 基钦(库存)周期：上游原材料(钢铁/采掘，价格随库存波动) + 产成品库存(汽车/非银/综合)
// 朱格拉(设备投资)周期：机械设备(Capex周期核心载体)
// 库兹涅茨(建筑)周期：房地产 + 建筑材料(水泥/玻璃) + 建筑装饰(施工链)
const CYCLE_GROUPS = {
  kitchin: {
    label: '基钦周期', icon: '📦', sub: '库存周期 3~5年',
    names: ['钢铁', '采掘', '汽车', '非银金融', '综合'],
  },
  juglar: {
    label: '朱格拉周期', icon: '🏭', sub: '设备投资 8~10年',
    names: ['机械设备'],
  },
  kuznets: {
    label: '库兹涅茨周期', icon: '🏘️', sub: '建筑/房地产 15~25年',
    names: ['房地产', '建筑材料', '建筑装饰'],
  },
};

/** 获取行业所属周期组 key */
function getCycleGroupOf(name) {
  for (const [key, grp] of Object.entries(CYCLE_GROUPS)) {
    if (grp.names.includes(name)) return key;
  }
  return 'kitchin'; // 兜底
}

/** 按三周期分组排序强周期行业 */
function sortByCycleGroup(industries) {
  const order = { kitchin: 0, juglar: 1, kuznets: 2 };
  return [...industries].sort((a, b) => {
    const ga = order[getCycleGroupOf(a.name)] ?? 0;
    const gb = order[getCycleGroupOf(b.name)] ?? 0;
    return ga - gb;
  });
}

// ── 工具函数 ──

/** 涨跌幅 → 热力色 (treemap 用) */
function changeToColor(v) {
  if (v > 3)   return '#c33636';
  if (v > 1.5) return '#db7126';
  if (v > 0.3) return '#ccc203';
  if (v > -0.3)return 'rgb(195 195 195 / 0.96)';
  if (v > -1.5)return '#97b431';
  if (v > -3)  return '#3ca039';
  return '#0e7851';
}

/** 解析 industry_sw_tree 文本 → { "二级行业名": "一级行业名" } 映射 */
function parseTreeMapping(text) {
  if (!text) return {};
  const mapping = {};
  let currentL1 = null;
  for (const line of text.split('\n')) {
    if (line.startsWith('申万') || !line.trim()) continue;
    // Level 1: ├── 农林牧渔 ... 或 └── ...
    const l1 = line.match(/^[├└]──\s*(\S+)/);
    if (l1) { currentL1 = l1[1]; continue; }
    // Level 2: │   ├── 种植业 ... 或 │   └── ...
    const l2 = line.match(/│\s+[├└]──\s*(\S+)/);
    if (l2 && currentL1) mapping[l2[1]] = currentL1;
  }
  return mapping;
}

/** 判断行业所属分类 key */
function getCategoryOf(name) {
  if (CYCLICAL_NAMES.has(name))  return 'cyclical';
  if (DEFENSIVE_NAMES.has(name)) return 'defensive';
  if (GROWTH_NAMES.has(name))    return 'growth';
  return 'cyclical'; // 兜底
}

// ── 下钻组件 ──

/** 成分股下钻：权重 treemap + 涨跌幅热色，点击跳转个股 */
function ConstituentDrilldown({ target, onBack }) {
  // target: { industry_code, industry_name }
  const navigate = useNavigate();
  const { data: consRaw, isLoading } = useMCP(
    'industry_sw_constituents_detail',
    target.industry_code ? { 行业代码: target.industry_code, limit: 200 } : null,
  );
  const treemapRef = useRef(null);

  const constituents = useMemo(() => {
    if (!consRaw) return [];
    const lines = consRaw.trim().split('\n');
    if (lines.length < 2) return [];
    const col = buildColMap(lines[0]);
    const iCode  = col['stock_code'] ?? 0;
    const iName  = col['stock_name'] ?? 1;
    const iWt    = col['weight'] ?? 2;
    const iChg   = col['change_pct'] ?? 3;
    const iPrice = col['price'] ?? 4;
    const iTurn  = col['turnover'] ?? 5;
    const iPe    = col['pe_dynamic'] ?? 6;
    const iPb    = col['pb'] ?? 7;
    return lines.slice(1).map(l => {
      const p = l.split(',');
      return {
        code: (p[iCode] || '').trim(),
        name: (p[iName] || '').trim(),
        weight: safeFloat(p[iWt]),
        change_pct: safeFloat(p[iChg]),
        price: safeFloat(p[iPrice]),
        turnover: safeFloat(p[iTurn]),
        pe: safeFloat(p[iPe]),
        pb: safeFloat(p[iPb]),
      };
    });
  }, [consRaw]);

  // 权重>=2% 的成分股用于 treemap
  const treemapData = useMemo(() => {
    return constituents
      .filter(c => c.weight != null && c.weight >= 2)
      .sort((a, b) => b.weight - a.weight);
  }, [constituents]);

  // 权重<2% 的成分股汇总
  const smallWeightCount = useMemo(() => {
    return constituents.filter(c => c.weight != null && c.weight < 2).length;
  }, [constituents]);

  const avgChange = constituents.length
    ? constituents.reduce((s, c) => s + (c.change_pct || 0), 0) / constituents.filter(c => c.change_pct != null).length
    : 0;

  // 绘制 treemap
  useEffect(() => {
    if (!treemapRef.current || !treemapData.length) return;
    let chart = echarts.getInstanceByDom(treemapRef.current);
    if (!chart) chart = echarts.init(treemapRef.current, 'df-dark');

    const data = treemapData.map(c => ({
      name: c.name,
      value: Math.max(0.5, c.weight),
      itemStyle: { color: changeToColor(c.change_pct), borderColor: 'rgba(212,168,83,0.15)', borderWidth: 1, gapWidth: 2 },
      _code: c.code,
      _change: c.change_pct,
      _weight: c.weight,
      _price: c.price,
      _turnover: c.turnover,
      _pe: c.pe,
      _pb: c.pb,
    }));

    // 先移除旧的 click handler（在 setOption 之前，避免影响新 option 的事件绑定）
    chart.off('click');

    chart.setOption({
      tooltip: {
        formatter: p => {
          const d = p.data;
          if (!d) return '';
          return `<div style="font-weight:700;font-size:14px">${d.name}</div>
            <div style="font-size:12px;margin-top:4px">代码: ${d._code || '—'}</div>
            <div style="font-size:12px">权重: ${d._weight != null ? d._weight.toFixed(2) + '%' : '—'}</div>
            <div style="font-size:12px;color:${d._change >= 0 ? '#E85050' : '#3DBB6E'}">涨跌幅: ${d._change != null ? (d._change >= 0 ? '+' : '') + d._change.toFixed(2) + '%' : '—'}</div>
            <div style="font-size:12px">最新价: ${d._price != null ? d._price.toFixed(2) : '—'}</div>
            <div style="font-size:12px">换手率: ${d._turnover != null ? d._turnover.toFixed(2) + '%' : '—'}</div>
            <div style="font-size:12px">PE: ${d._pe != null ? d._pe.toFixed(1) : '—'}  PB: ${d._pb != null ? d._pb.toFixed(2) : '—'}</div>
            <div style="font-size:11px;color:#D4A853;margin-top:4px">点击查看个股分析</div>`;
        },
        backgroundColor: 'rgba(26,47,42,0.95)',
        borderColor: 'rgba(212,168,83,0.2)',
        textStyle: { color: '#CBC0B0' },
        extraCssText: 'border-radius:8px;padding:10px 14px;',
      },
      series: [{
        type: 'treemap',
        data,
        roam: false,
        nodeClick: false, // 禁用 zoom，但 click 事件仍会触发
        breadcrumb: { show: false },
        label: {
          show: true,
          formatter: p => {
            const d = p.data;
            return `${d.name}\n${d._weight != null ? d._weight.toFixed(1) + '%' : ''}`;
          },
          fontSize: 14,
          color: '#141414',
          fontWeight: 600,
        },
        upperLabel: { show: false },
        itemStyle: { borderColor: 'rgba(212,168,83,0.15)', borderWidth: 1, gapWidth: 2 },
      }],
    }, { notMerge: true });

    // setOption 之后再绑定 click 事件
    chart.on('click', (params) => {
      const code = params?.data?._code;
      console.log('[ConstituentDrilldown] treemap click:', params?.data?.name, 'code:', code);
      if (code) {
        const store = useAppStore.getState();
        // 先设置 store 状态，再通过 navigate 切换路由
        // 必须调用 navigate，否则 URL 仍是 /meso，StockPanel 不会挂载
        store.setActiveMicroSub('stock');
        store.setStockSearchKeyword(code);
        store.setActiveTab('micro');
        navigate('/micro');
        console.log('[ConstituentDrilldown] 已触发跳转:', code);
      }
    });

    return () => {
      // cleanup 时移除所有 click handler
      if (treemapRef.current) {
        const ch = echarts.getInstanceByDom(treemapRef.current);
        if (ch) ch.off('click');
      }
    };
  }, [treemapData]);

  // 组件卸载时 dispose
  useEffect(() => {
    return () => {
      if (treemapRef.current) {
        const chart = echarts.getInstanceByDom(treemapRef.current);
        if (chart) chart.dispose();
      }
    };
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <button onClick={onBack} style={{
          padding: '4px 12px', borderRadius: 6, fontSize: 'var(--fs-sm)',
          background: 'rgba(212,168,83,0.1)', border: '1px solid var(--border-subtle)',
          color: 'var(--accent-gold)', cursor: 'pointer',
        }}>← 返回二级行业</button>
        <span style={{ fontSize: 'var(--fs-md)', fontWeight: 700 }}>{target.industry_name}</span>
        <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>· 成分股权重分布</span>
        {constituents.length > 0 && (
          <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, marginLeft: 'auto',
            color: avgChange >= 0 ? 'var(--accent-red)' : 'var(--accent-green)'
          }}>
            均涨 {avgChange.toFixed(2)}% · {constituents.length} 只 · 权重≥2% {treemapData.length} 只
            {smallWeightCount > 0 ? ` · <2% ${smallWeightCount}只已忽略` : ''}
          </span>
        )}
      </div>
      {isLoading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>加载中...</div>
      ) : treemapData.length > 0 ? (
        <div ref={treemapRef} style={{ width: '100%', height: Math.max(300, treemapData.length * 18 + 60) }} />
      ) : (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
          暂无成分股数据（权重≥2%）
        </div>
      )}
    </div>
  );
}


/** 行业下钻：二级行业树状图 + 成分股三级下钻 */
function IndustryDrilldown({ target, onBack }) {
  const chartRef = useRef(null);
  const [constituentTarget, setConstituentTarget] = useState(null);

  // 自选二级模式下直接跳成分股
  const skipToConstituents = target.skip_to_constituents;

  const { data: treeRaw } = useMCP('industry_sw_tree', { '深度': 2, '展开': 31 });
  const today = new Date();
  const startDay = new Date(today.getTime() - 30 * 86400000);
  const startStr = startDay.toISOString().slice(0, 10).replace(/-/g, '');
  const { data: l2Raw } = useMCP('industry_sw_daily', { symbol: '二级行业', start_date: startStr, end_date: new Date().toISOString().slice(0, 10).replace(/-/g, ''), limit: 5000 });

  // 历史指数走势数据（一级行业级别）
  const { data: histRaw } = useMCP('industry_daily_query', target.industry ? { industry: target.industry, limit: 120 } : null);
  const histData = useMemo(() => parseDaily(histRaw), [histRaw]);

  const mapping = useMemo(() => parseTreeMapping(treeRaw), [treeRaw]);
  const l2Parsed = useMemo(() => parseSWDaily(l2Raw), [l2Raw]);

  const subIndustries = useMemo(() => {
    if (!l2Parsed.industries.length) return [];
    let base;
    const byMapping = l2Parsed.industries.filter(i => mapping[i.name] === target.industry);
    if (byMapping.length > 0) base = byMapping;
    else {
      base = l2Parsed.industries.filter(i => {
        const parent = mapping[i.name];
        if (parent) return parent === target.industry;
        const l1 = l2Parsed.industries.find(j => j.name === target.industry);
        return l1 && i.code && l1.code && i.code.substring(0, 5) === l1.code.substring(0, 5);
      });
    }
    if (target.date) {
      return base.map(si => ({
        ...si,
        change: l2Parsed.matrix[si.name]?.[target.date] ?? si.change,
      }));
    }
    return base;
  }, [l2Parsed, mapping, target.industry, target.date]);

  useEffect(() => {
    if (!chartRef.current || !subIndustries.length) return;
    const chart = echarts.init(chartRef.current, 'df-dark');
    const data = subIndustries.map(si => ({
      name: si.name,
      value: Math.max(1, si.mktCap / 1e8),
      itemStyle: { color: changeToColor(si.change), borderColor: 'rgba(212,168,83,0.15)', borderWidth: 1, gapWidth: 2 },
      _change: si.change,
      _pe: si.pe,
      _pb: si.pb,
      _mktCap: si.mktCap,
      _code: si.code,
    }));
    chart.setOption({
      tooltip: {
        formatter: p => `${p.name}<br/>涨跌幅: ${p.data._change != null ? `${p.data._change >= 0 ? '+' : ''}${p.data._change.toFixed(2)}%` : '—'}<br/>流通市值: ${p.data._mktCap != null ? `${(p.data._mktCap / 1e8).toFixed(0)}亿` : '—'}<br/>PE: ${p.data._pe != null ? p.data._pe.toFixed(1) : '—'}  PB: ${p.data._pb != null ? p.data._pb.toFixed(2) : '—'}<br/><span style="color:#D4A853">点击查看成分股</span>`,
      },
      series: [{
        type: 'treemap',
        data,
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        label: {
          show: true,
          formatter: p => `${p.name}\n${p.data._change != null ? `${p.data._change >= 0 ? '+' : ''}${p.data._change.toFixed(1)}%` : '—'}`,
          fontSize: 18,
          color: '#141414',
        },
        upperLabel: { show: false },
        itemStyle: { borderColor: 'rgba(212,168,83,0.15)', borderWidth: 1, gapWidth: 2 },
      }],
    });
    // 点击二级行业方块 → 下钻成分股
    chart.on('click', (params) => {
      if (params.data?._code) {
        setConstituentTarget({
          industry_code: params.data._code,
          industry_name: params.data.name,
        });
      }
    });
    return () => chart.dispose();
  }, [subIndustries]);

  const avgChange = subIndustries.length ? subIndustries.reduce((s, i) => s + (i.change || 0), 0) / subIndustries.length : 0;

  // 三级下钻：成分股
  if (constituentTarget || skipToConstituents) {
    const cTarget = constituentTarget || { industry_code: target.industry_code, industry_name: target.industry };
    return <ConstituentDrilldown target={cTarget} onBack={skipToConstituents ? onBack : () => setConstituentTarget(null)} />;
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <button onClick={onBack} style={{
          padding: '4px 12px', borderRadius: 6, fontSize: 'var(--fs-sm)',
          background: 'rgba(212,168,83,0.1)', border: '1px solid var(--border-subtle)',
          color: 'var(--accent-gold)', cursor: 'pointer',
        }}>← 返回热力图</button>
        <span style={{ fontSize: 'var(--fs-md)', fontWeight: 700 }}>{target.industry}</span>
        <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>· {target.date} 涨跌幅 · 二级行业树状图</span>
        {subIndustries.length > 0 && (
          <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, marginLeft: 'auto',
            color: avgChange >= 0 ? 'var(--accent-red)' : 'var(--accent-green)'
          }}>
            均涨 {avgChange.toFixed(2)}% · {subIndustries.length} 子行业
          </span>
        )}
      </div>
      {subIndustries.length > 0 ? (
        <div ref={chartRef} style={{ width: '100%', height: 380 }} />
      ) : (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--fs-base)' }}>
          暂无二级行业数据，请先执行 industry_collect 采集
        </div>
      )}
      {histData.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 600 }}>📈 {target.industry} 指数走势</span>
            <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>· 近 {histData.length} 日</span>
          </div>
          <DataChart data={histData} series={[
            { key: 'close', name: `${target.industry}指数`, color: '#D4A853', type: 'line' },
          ]} dateKey="period" height={200} />
        </div>
      )}
    </div>
  );
}

// ── 自选行业选择器 ──

/** 自选行业多选器 — 支持切换一级/二级行业数据源 */
function IndustryPicker({ allIndustries, selectedNames, onToggle, level, setLevel, l2Industries }) {
  const [search, setSearch] = useState('');
  const sourceIndustries = level === 1 ? allIndustries : l2Industries;
  const filtered = search
    ? sourceIndustries.filter(i => i.name.includes(search) || (i.code || '').includes(search))
    : sourceIndustries;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '12px 14px',
      background: 'var(--bg-panel)', border: '1px solid var(--border-subtle)', borderRadius: 8,
      maxHeight: 420, overflow: 'hidden',
    }}>
      {/* 级别切换 */}
      <div style={{ display: 'flex', gap: 6 }}>
        {[1, 2].map(lv => (
          <button key={lv} onClick={() => setLevel(lv)} style={{
            padding: '4px 14px', borderRadius: 5, fontSize: 'var(--fs-xs)', fontWeight: 600,
            background: level === lv ? 'rgba(155,126,200,0.2)' : 'transparent',
            color: level === lv ? '#9B7EC8' : 'var(--text-muted)',
            border: `1px solid ${level === lv ? '#9B7EC8' : 'var(--border-subtle)'}`,
            cursor: 'pointer',
          }}>
            {lv === 1 ? '一级行业' : '二级行业'}
          </button>
        ))}
        <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', marginLeft: 'auto', lineHeight: '28px' }}>
          已选 {selectedNames.length} / {filtered.length}
        </span>
      </div>

      {/* 搜索 */}
      <input
        type="text"
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="搜索行业名称或代码..."
        style={{
          width: '100%', padding: '5px 10px', borderRadius: 5, fontSize: 'var(--fs-sm)',
          background: 'var(--bg-primary)', color: 'var(--text-primary)',
          border: '1px solid var(--border-subtle)', outline: 'none',
        }}
      />

      {/* 全选/清空 */}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={() => onToggle(filtered.map(i => i.name), true)} style={{
          padding: '2px 10px', borderRadius: 4, fontSize: 'var(--fs-xs)',
          background: 'transparent', border: '1px solid var(--border-subtle)',
          color: 'var(--accent-gold)', cursor: 'pointer',
        }}>全选</button>
        <button onClick={() => onToggle([], false)} style={{
          padding: '2px 10px', borderRadius: 4, fontSize: 'var(--fs-xs)',
          background: 'transparent', border: '1px solid var(--border-subtle)',
          color: 'var(--text-muted)', cursor: 'pointer',
        }}>清空</button>
      </div>

      {/* 行业列表 */}
      <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexWrap: 'wrap', gap: 4, alignContent: 'flex-start' }}>
        {filtered.map(i => {
          const checked = selectedNames.includes(i.name);
          return (
            <label key={i.name} style={{
              display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px',
              borderRadius: 5, fontSize: 'var(--fs-xs)', cursor: 'pointer',
              background: checked ? 'rgba(155,126,200,0.18)' : 'transparent',
              border: `1px solid ${checked ? '#9B7EC844' : 'var(--border-subtle)'}`,
              color: checked ? '#9B7EC8' : 'var(--text-secondary)',
              transition: 'all 0.15s',
            }}>
              <input
                type="checkbox"
                checked={checked}
                onChange={() => {
                  const next = checked
                    ? selectedNames.filter(n => n !== i.name)
                    : [...selectedNames, i.name];
                  onToggle(next, true);
                }}
                style={{ display: 'none' }}
              />
              {i.name}
              {i.change != null && (
                <span style={{ fontSize: 10, color: i.change >= 0 ? 'var(--accent-red)' : 'var(--accent-green)' }}>
                  {i.change >= 0 ? '+' : ''}{i.change.toFixed(1)}
                </span>
              )}
            </label>
          );
        })}
      </div>
    </div>
  );
}

// ── 热力图交互区 ──

/** 行业热力图 — 纯图表渲染（控制栏由父组件渲染） */
function HeatmapChart({ filteredIndustries, dates, matrix, onIndustrySelect, activeCategory, displayDays, drillTarget, setDrillTarget, customLevel }) {
  const chartRef = useRef(null);
  const [cycleTooltip, setCycleTooltip] = useState(null);

  // 强周期模式：请求三周期数据，用于信号灯标记
  const isCyclical = activeCategory === 'cyclical';
  const { data: kitchinRaw } = useMCP('data_kitchin', isCyclical ? {} : null);
  const { data: juglarRaw }  = useMCP('data_juglar', isCyclical ? {} : null);
  const { data: kuznetsRaw } = useMCP('data_kuznets', isCyclical ? {} : null);

  // 相位→颜色（与原来 CyclePhasePanel 一致）
  const phaseColor = (name) => {
    if (!name) return '#888';
    if (['主动补库', '繁荣', '主动补库存'].includes(name)) return '#E85050';
    if (['被动去库', '复苏', '被动去库存'].includes(name)) return '#D4A853';
    if (['被动补库', '衰退', '被动补库存'].includes(name)) return '#7B8FA8';
    if (['主动去库', '萧条', '主动去库存'].includes(name)) return '#3DBB6E';
    return '#888';
  };
  // 相位→rich text 标签名
  const phaseTag = (name) => {
    if (!name) return 'dotUnknown';
    if (['主动补库', '繁荣', '主动补库存'].includes(name)) return 'dotBoom';
    if (['被动去库', '复苏', '被动去库存'].includes(name)) return 'dotRecovery';
    if (['被动补库', '衰退', '被动补库存'].includes(name)) return 'dotRecession';
    if (['主动去库', '萧条', '主动去库存'].includes(name)) return 'dotDepression';
    return 'dotUnknown';
  };

  // 解析最新周期相位 → 行业名→周期信息映射
  const cyclePhaseMap = useMemo(() => {
    if (!isCyclical) return {};
    const parseLatest = (raw) => {
      try {
        const arr = typeof raw === 'string' ? JSON.parse(raw) : raw;
        if (!Array.isArray(arr) || !arr.length) return null;
        return arr[arr.length - 1];
      } catch { return null; }
    };
    const phases = {
      kitchin: parseLatest(kitchinRaw),
      juglar:  parseLatest(juglarRaw),
      kuznets: parseLatest(kuznetsRaw),
    };
    const KITCHIN_NAMES = { 1: '主动去库存', 2: '被动去库存', 3: '主动补库存', 4: '被动补库存' };
    const MACRO_NAMES = { 1: '复苏', 2: '繁荣', 3: '衰退', 4: '萧条' };
    const map = {};
    for (const [key, grp] of Object.entries(CYCLE_GROUPS)) {
      const ph = phases[key];
      let pName = null;
      if (ph) {
        if (ph.cycle_phase_name) {
          pName = ph.cycle_phase_name;
        } else if (key === 'kitchin') {
          pName = ph.stage_name || KITCHIN_NAMES[ph.stage] || null;
        } else {
          pName = ph.phase_name || MACRO_NAMES[ph.phase] || null;
        }
      }
      for (const name of grp.names) {
        map[name] = { cycleKey: key, phaseName: pName, phase: ph, group: grp };
      }
    }
    return map;
  }, [isCyclical, kitchinRaw, juglarRaw, kuznetsRaw]);

  // 每组行业的20日波动率和均值（用于tooltip）
  const groupStats = useMemo(() => {
    if (!isCyclical) return {};
    const recent = dates.slice(-20);
    if (!recent.length || !filteredIndustries.length) return {};
    const stats = {};
    for (const [key, grp] of Object.entries(CYCLE_GROUPS)) {
      const groupInds = filteredIndustries.filter(i => grp.names.includes(i.name));
      const changes = [];
      groupInds.forEach(ind => {
        recent.forEach(d => {
          const v = matrix[ind.name]?.[d];
          if (v !== undefined) changes.push(v);
        });
      });
      if (!changes.length) { stats[key] = { vol: null, avg: null }; continue; }
      const avg = changes.reduce((s, v) => s + v, 0) / changes.length;
      const vol = Math.sqrt(changes.reduce((s, v) => s + (v - avg) ** 2, 0) / changes.length);
      stats[key] = { vol, avg };
    }
    return stats;
  }, [isCyclical, filteredIndustries, matrix, dates]);

  // 强周期模式按三周期分组排序
  const sortedIndustries = useMemo(() =>
    activeCategory === 'cyclical' ? sortByCycleGroup(filteredIndustries) : filteredIndustries,
    [activeCategory, filteredIndustries],
  );

  useEffect(() => {
    if (drillTarget || !chartRef.current || !sortedIndustries.length || !dates.length) return;
    const chart = echarts.init(chartRef.current, 'df-dark');
    const names = sortedIndustries.map(i => i.name || i.code);
    const recentDates = dates.slice(-displayDays);
    const data = [];
    for (let yi = 0; yi < names.length; yi++) {
      for (let xi = 0; xi < recentDates.length; xi++) {
        const val = matrix[names[yi]]?.[recentDates[xi]];
        if (val !== undefined) data.push([xi, yi, val]);
      }
    }

    const hasCycleDots = isCyclical && Object.keys(cyclePhaseMap).length > 0;

    // Y轴 rich text 样式 — 信号灯圆点
    const dotStyle = (color) => ({
      color,
      fontSize: 22,
      padding: [0, 6, 4, 0],
      textShadowBlur: 8,
      textShadowColor: `${color}66`,
    });

    chart.setOption({
      tooltip: {
        formatter: p => {
          if (p.componentType === 'yAxis') return null; // 由自定义 tooltip 处理
          return `${names[p.data[1]]}<br/>${recentDates[p.data[0]]}: ${p.data[2] >= 0 ? '+' : ''}${p.data[2].toFixed(2)}%`;
        },
      },
      grid: { left: hasCycleDots ? 120 : 95, right: 50, top: 20, bottom: 60 },
      xAxis: { type: 'category', data: recentDates.map(d => d.slice(5)), axisLabel: { fontSize: 12, rotate: 35 } },
      yAxis: {
        type: 'category',
        data: names,
        triggerEvent: isCyclical,
        axisLabel: {
          fontSize: 13,
          width: hasCycleDots ? 105 : 85,
          overflow: 'truncate',
          ...(hasCycleDots ? {
            formatter: function(name) {
              const info = cyclePhaseMap[name];
              if (info) {
                const tag = phaseTag(info.phaseName);
                return `{${tag}|●} {name|${name}}`;
              }
              return `{name|${name}}`;
            },
            rich: {
              name: { fontSize: 13, width: 82, overflow: 'truncate' },
              dotBoom: dotStyle('#E85050'),
              dotRecovery: dotStyle('#D4A853'),
              dotRecession: dotStyle('#7B8FA8'),
              dotDepression: dotStyle('#3DBB6E'),
              dotUnknown: dotStyle('#888'),
            },
          } : {}),
        },
      },
      visualMap: {
        min: -4, max: 4, calculable: true, orient: 'vertical', right: 4, bottom: 40,
        inRange: { color: ['rgb(206 206 206)', '#048152', '#47a83d', '#91c133', '#ccb022', '#db8f36', '#c85454'] },
        textStyle: { color: '#CBC0B0', fontSize: 13 },
      },
      series: [{
        type: 'heatmap', data,
        label: { show: true, formatter: p => `${p.data[2].toFixed(1)}%`, fontSize: 12, color: '#ffffff' },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgb(0 0 0 / 0.8)' } },
      }],
    });

    // Y轴标签 hover → 显示周期信号灯悬浮卡片
    if (isCyclical) {
      chart.on('mouseover', function(params) {
        if (params.componentType === 'yAxis') {
          const name = params.value;
          const info = cyclePhaseMap[name];
          if (info) {
            const evt = params.event?.event || params.event;
            const rect = chartRef.current.getBoundingClientRect();
            setCycleTooltip({
              name,
              info,
              stats: groupStats[info.cycleKey] || {},
              x: evt.clientX - rect.left,
              y: evt.clientY - rect.top,
            });
          }
        }
      });
      chart.on('mouseout', function(params) {
        if (params.componentType === 'yAxis') {
          setCycleTooltip(null);
        }
      });
    }

    chart.on('click', (params) => {
      if (params.data) {
        const industryName = names[params.data[1]];
        const date = recentDates[params.data[0]];
        // 自选二级行业模式 → 直接跳成分股下钻
        if (activeCategory === 'custom' && customLevel === 2) {
          const ind = sortedIndustries.find(i => i.name === industryName);
          if (ind && ind.code) {
            setDrillTarget({ industry: industryName, date, industry_code: ind.code, skip_to_constituents: true });
          }
        } else {
          setDrillTarget({ industry: industryName, date });
        }
        onIndustrySelect(industryName);
      }
    });
    return () => chart.dispose();
  }, [sortedIndustries, dates, matrix, drillTarget, onIndustrySelect, displayDays, setDrillTarget, isCyclical, cyclePhaseMap, groupStats]);

  const h = Math.max(380, sortedIndustries.length * 40 + 90);

  if (drillTarget) {
    return <IndustryDrilldown target={drillTarget} onBack={() => setDrillTarget(null)} />;
  }

  // 自选模式无选中行业
  if (activeCategory === 'custom' && sortedIndustries.length === 0) {
    return (
      <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--fs-base)' }}>
        请在上方选择行业后生成热力图
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div ref={chartRef} style={{ width: '100%', height: h }} />
      {/* 周期信号灯悬浮卡片 */}
      {cycleTooltip && (
        <div style={{
          position: 'absolute',
          left: Math.min(cycleTooltip.x + 14, (chartRef.current?.clientWidth || 800) - 260),
          top: Math.max(cycleTooltip.y - 80, 4),
          zIndex: 100,
          background: 'var(--bg-panel)',
          border: `1px solid ${phaseColor(cycleTooltip.info.phaseName)}44`,
          borderRadius: 8,
          padding: '10px 14px',
          boxShadow: `0 4px 20px rgba(0,0,0,0.4), 0 0 12px ${phaseColor(cycleTooltip.info.phaseName)}22`,
          minWidth: 220,
          pointerEvents: 'none',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <span style={{ fontSize: 17 }}>{cycleTooltip.info.group.icon}</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--accent-gold)' }}>{cycleTooltip.info.group.label}</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{cycleTooltip.info.group.sub}</span>
          </div>
          <div style={{ marginBottom: 6 }}>
            <span style={{
              display: 'inline-block', padding: '2px 10px', borderRadius: 12,
              fontSize: 14, fontWeight: 800,
              background: `${phaseColor(cycleTooltip.info.phaseName)}18`,
              color: phaseColor(cycleTooltip.info.phaseName),
              border: `1px solid ${phaseColor(cycleTooltip.info.phaseName)}33`,
            }}>
              {cycleTooltip.info.phaseName || '—'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
            <span>波动率 <b style={{ color: 'var(--text-primary)' }}>{cycleTooltip.stats.vol != null ? cycleTooltip.stats.vol.toFixed(2) : '—'}%</b></span>
            <span>均值 <b style={{ color: cycleTooltip.stats.avg != null && cycleTooltip.stats.avg >= 0 ? '#E85050' : '#3DBB6E' }}>{cycleTooltip.stats.avg != null ? (cycleTooltip.stats.avg >= 0 ? '+' : '') + cycleTooltip.stats.avg.toFixed(2) : '—'}%</b></span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
            {cycleTooltip.info.group.names.join(' · ')}
          </div>
        </div>
      )}
    </div>
  );
}

/** 行业排名 TOP/BOTTOM 表格 */
function RankingTable({ title, subtitle, items, colorKey }) {
  const isUp = colorKey === 'up';
  return (
    <CardWrapper style={{ padding: 'var(--sp-xl)' }}>
      <h3 style={{ fontSize: 'var(--fs-base)', fontWeight: 600, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
        {title} <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', fontWeight: 400 }}>{subtitle}</span>
      </h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--fs-sm)', minWidth: 320 }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>排名</th>
              <th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>行业</th>
              <th style={{ textAlign: 'right', padding: '6px 8px', fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>涨跌幅</th>
              <th style={{ textAlign: 'right', padding: '6px 8px', fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>PE</th>
              <th style={{ textAlign: 'right', padding: '6px 8px', fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>PB</th>
            </tr>
          </thead>
          <tbody>
            {items.map((i, idx) => (
              <tr key={i.code} style={idx === 0 ? { background: 'var(--shadow-glow)' } : {}}>
                <td style={{ padding: '6px 8px', fontWeight: 700, borderBottom: '1px solid rgba(212,168,83,0.04)' }}>{idx + 1}</td>
                <td style={{ padding: '6px 8px', fontWeight: 600, borderBottom: '1px solid rgba(212,168,83,0.04)' }}>{i.name}</td>
                <td style={{
                  padding: '6px 8px', textAlign: 'right', fontWeight: 700,
                  color: isUp ? 'var(--accent-red)' : 'var(--accent-green)',
                  borderBottom: '1px solid rgba(212,168,83,0.04)',
                }}>{i.change != null ? `${i.change >= 0 ? '+' : ''}${i.change.toFixed(2)}%` : '—'}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '1px solid rgba(212,168,83,0.04)' }}>{i.pe != null ? i.pe.toFixed(1) : '—'}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '1px solid rgba(212,168,83,0.04)' }}>{i.pb != null ? i.pb.toFixed(2) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </CardWrapper>
  );
}

/** 行业详情五维面板 */
function IndustryDetail({ sel, chartData, latest, prev }) {
  if (!sel) return null;
  // 流通市值：后端返回单位为元，转亿元
  const mktCapYi = sel.mktCap ? (sel.mktCap / 1e8) : null;
  const metrics = [
    { key: 'close', label: '收盘指数', unit: '', decimals: 2, higherBetter: true },
    { key: 'change', label: '涨跌幅', unit: '%', decimals: 2, higherBetter: true },
    { key: 'turnover', label: '换手率', unit: '%', decimals: 2, higherBetter: null },
    { key: 'pe', label: 'PE(TTM)', value: sel.pe, decimals: 1, higherBetter: null },
    { key: 'pb', label: 'PB', value: sel.pb, decimals: 2, higherBetter: null },
    { key: 'mktCap', label: '流通市值', value: mktCapYi, decimals: 0, unit: '亿', higherBetter: null },
  ];

  return (
    <div style={{ marginTop: 4 }}>
      <SectionHeader badge="🔍 行业详情" title="当前选中" highlight={sel.name} desc="点击行业名称切换" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 20, marginBottom: 20 }}>
        {/* 行业概况 */}
        <CardWrapper style={{ padding: 'var(--sp-lg)' }}>
          <div style={{ fontSize: 'var(--fs-sm)', fontWeight: 600, color: 'var(--accent-gold)', marginBottom: 8 }}>📊 行业概况</div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            <li style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)', padding: '3px 0', display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(212,168,83,0.04)' }}>
              <span>行业代码</span><span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{sel.code || '—'}</span>
            </li>
            <li style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)', padding: '3px 0', display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(212,168,83,0.04)' }}>
              <span>日期</span><span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{sel.date || '—'}</span>
            </li>
            <li style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)', padding: '3px 0', display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(212,168,83,0.04)' }}>
              <span>分类</span><span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{getCategoryOf(sel.name) === 'cyclical' ? '强周期' : getCategoryOf(sel.name) === 'defensive' ? '强防御' : '进攻型'}</span>
            </li>
          </ul>
        </CardWrapper>
        {/* 指标卡（去重：不再重复展示收盘/PE/PB） */}
        {metrics.map(m => (
          <DataCard
            key={m.key}
            label={m.label}
            value={m.value != null ? m.value : latest[m.key]}
            prevValue={m.value == null ? prev[m.key] : undefined}
            unit={m.unit}
            decimals={m.decimals}
            higherBetter={m.higherBetter}
          />
        ))}
      </div>
      {/* 图表区 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 20 }}>
        <CardWrapper style={{ padding: 'var(--sp-xl)' }}>
          <h3 style={{ fontSize: 'var(--fs-base)', fontWeight: 600, marginBottom: 10 }}>📈 行业指数走势 <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', fontWeight: 400 }}>· 近 1 年</span></h3>
          <DataChart data={chartData} series={[{ key: 'close', name: `${sel.name}指数`, color: '#D4A853', type: 'line' }]} dateKey="period" height={260} showYAxisToggle={false} />
        </CardWrapper>
        <CardWrapper style={{ padding: 'var(--sp-xl)' }}>
          <h3 style={{ fontSize: 'var(--fs-base)', fontWeight: 600, marginBottom: 10 }}>📊 涨跌幅走势 <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', fontWeight: 400 }}>· 近期</span></h3>
          <DataChart data={chartData} series={[{ key: 'change', name: '涨跌幅', color: '#6abbdb', type: 'bar' }]} dateKey="period" height={260} showYAxisToggle={false} />
        </CardWrapper>
      </div>
    </div>
  );
}

/** 产业链穿透 */
function ChainView({ industries }) {
  // 按涨跌幅将行业分配到上/中/下游
  const sorted = [...industries].sort((a, b) => b.change - a.change);
  // 上游原材料类
  const upstream = sorted.filter(i => ['钢铁','采掘','化工','有色金属','煤炭'].includes(i.name));
  // 中游制造类
  const midstream = sorted.filter(i => ['电子','电气设备','机械设备','国防军工','计算机','通信','新能源汽车'].includes(i.name));
  // 下游消费类
  const downstream = sorted.filter(i => ['食品饮料','医药生物','汽车','家用电器','纺织服装','房地产','银行','非银金融','商业贸易','休闲服务'].includes(i.name));

  const ChainCard = ({ title, icon, items, borderColor }) => (
    <CardWrapper style={{ padding: 'var(--sp-xl)', borderLeft: `3px solid ${borderColor}` }}>
      <h3 style={{ fontSize: 'var(--fs-base)', fontWeight: 600, marginBottom: 10 }}>{icon} {title}</h3>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
        {items.slice(0, 6).map(i => (
          <span key={i.name} style={{
            padding: '2px 8px', borderRadius: 6, fontSize: 'var(--fs-xs)',
            background: (i.change || 0) >= 0 ? 'rgba(196,123,123,0.12)' : 'rgba(62,107,92,0.12)',
            color: (i.change || 0) >= 0 ? 'var(--accent-red)' : 'var(--accent-green)',
          }}>{i.name} {i.change != null ? `${i.change >= 0 ? '+' : ''}${i.change.toFixed(1)}%` : '—'}</span>
        ))}
      </div>
      <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>
        行业数 {items.length} · 平均涨幅 {items.length ? (items.reduce((s, i) => s + (i.change || 0), 0) / items.length).toFixed(2) : '—'}%
      </div>
    </CardWrapper>
  );

  return (
    <div>
      <SectionHeader badge="⛓️ 产业链穿透" title="从宏观到微观的" highlight="传导路径" desc="上游原材料 → 中游制造 → 下游消费，每一环节的关键变量" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
        <ChainCard title="上游 · 原材料" icon="⬆" items={upstream} borderColor="var(--accent-gold)" />
        <ChainCard title="中游 · 制造" icon="➡" items={midstream} borderColor="var(--accent-blue)" />
        <ChainCard title="下游 · 消费" icon="⬇" items={downstream} borderColor="var(--accent-green)" />
      </div>
    </div>
  );
}



/** 能源监测 */
function EnergySection() {
  const { data: oilRaw } = useMCP('futures_prices', { symbol: '原油', limit: 60 });
  const { data: coalRaw } = useMCP('futures_prices', { symbol: '动力煤', limit: 60 });

  const parsePrice = (csv) => {
    if (!csv) return [];
    const lines = csv.trim().split('\n');
    if (lines.length < 2) return [];
    const col = buildColMap(lines[0]);
    const ci = col['close'] ?? 4;
    return lines.slice(1).map(l => {
      const p = l.split(',');
      return { period: (p[0] || '').slice(5), close: parseFloat(p[ci]) || 0 };
    }).filter(d => !isNaN(d.close)).slice(-60);
  };

  const oilData = parsePrice(oilRaw);
  const coalData = parsePrice(coalRaw);
  const oilLatest = oilData[oilData.length - 1]?.close;
  const coalLatest = coalData[coalData.length - 1]?.close;

  return (
    <div>
      <SectionHeader badge="⚡ 能源监测" title="能源价格与" highlight="产量追踪" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 20, marginBottom: 16 }}>
        <DataCard label="🛢️ 原油" value={oilLatest} unit="元/桶" decimals={1} higherBetter={null}
          detail="INE主力合约" />
        <DataCard label="⚡ 动力煤" value={coalLatest} unit="元/吨" decimals={0} higherBetter={null}
          detail="郑商所主力合约" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 20 }}>
        <CardWrapper style={{ padding: 'var(--sp-xl)' }}>
          <h3 style={{ fontSize: 'var(--fs-base)', fontWeight: 600, marginBottom: 10 }}>原油价格走势</h3>
          <DataChart data={oilData} series={[{ key: 'close', name: '原油', color: '#C47B7B', type: 'line' }]} dateKey="period" height={240} />
        </CardWrapper>
        <CardWrapper style={{ padding: 'var(--sp-xl)' }}>
          <h3 style={{ fontSize: 'var(--fs-base)', fontWeight: 600, marginBottom: 10 }}>煤炭价格走势</h3>
          <DataChart data={coalData} series={[{ key: 'close', name: '动力煤', color: '#7B5E7B', type: 'line' }]} dateKey="period" height={240} />
        </CardWrapper>
      </div>
    </div>
  );
}

// ── 主组件 ──

export default function MesoLayout() {
  const queryClient = useQueryClient();
  // ── 行情数据刷新状态 ──
  const [dataRefreshing, setDataRefreshing] = useState(false);  // 正在采集+刷新
  const [collectStatus, setCollectStatus] = useState(null);     // 采集结果提示

  // 请求最近 20 个交易日的数据，让热力图有足够列
  const today = new Date();
  const startDay = new Date(today.getTime() - 30 * 86400000); // 30自然日≈20交易日
  const startStr = startDay.toISOString().slice(0, 10).replace(/-/g, '');
  const endStr = today.toISOString().slice(0, 10).replace(/-/g, '');
  const swResult = useMCP('industry_sw_daily', { symbol: '一级行业', start_date: startStr, end_date: endStr, limit: 800 });
  const updatedAt = swResult.updatedAt;
  const { industries, dates, matrix } = useMemo(() => parseSWDaily(swResult.data), [swResult.data]);

  // ── 刷新行情数据：先采集入库，再刷新热力图 ──
  const handleDataRefresh = useCallback(async () => {
    setDataRefreshing(true);
    setCollectStatus('⏳ 正在采集行业日线入库...');
    try {
      // Step 1: 调用 industry_daily_collect 采集最新数据入库
      const collectResult = await mcp.call('industry_daily_collect', { start_date: '20200101', force: false });
      setCollectStatus('✅ 采集完成，正在刷新热力图...');
      // Step 2: invalidate 所有行业相关缓存，强制重新拉取
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['industry_sw_daily'] }),
        queryClient.invalidateQueries({ queryKey: ['industry_daily_query'] }),
        queryClient.invalidateQueries({ queryKey: ['industry_sw_tree'] }),
        queryClient.invalidateQueries({ queryKey: ['industry_sw_constituents_detail'] }),
      ]);
      setCollectStatus('✅ 行情数据已刷新！');
    } catch (e) {
      setCollectStatus(`❌ 刷新失败: ${e.message}`);
    }
    setDataRefreshing(false);
    // 5秒后清除提示
    setTimeout(() => setCollectStatus(null), 5000);
  }, [queryClient]);
  const [activeInd, setActiveInd] = useState('');

  // 热力图控制状态（提升到父组件，控制栏渲染在 CardWrapper 外部）
  const [heatmapCategory, setHeatmapCategory] = useState('cyclical');
  const [heatmapDays, setHeatmapDays] = useState(20);
  const [drillTarget, setDrillTarget] = useState(null);

  // ── 自选模式状态 ──
  const [customLevel, setCustomLevel] = useState(1); // 1=一级 2=二级
  const [customSelected, setCustomSelected] = useState([]); // 选中的行业名

  // ── 组合保存 ──
  const [savedCombos, setSavedCombos] = useState(() => loadSavedCombos());
  const [comboNameInput, setComboNameInput] = useState('');
  const [showComboSave, setShowComboSave] = useState(false);
  const saveCombo = useCallback((name) => {
    if (!name.trim() || customSelected.length === 0) return;
    const id = Date.now();
    const accent = COMBO_COLORS[savedCombos.length % COMBO_COLORS.length];
    const next = [...savedCombos, { id, label: name.trim(), names: [...customSelected], level: customLevel, accent }];
    setSavedCombos(next);
    persistCombos(next);
    setShowComboSave(false);
    setComboNameInput('');
    // 保存后自动切换到新组合
    setHeatmapCategory(`combo_${id}`);
    setDrillTarget(null);
  }, [savedCombos, customSelected, customLevel]);
  const deleteCombo = useCallback((id) => {
    const next = savedCombos.filter(c => c.id !== id);
    setSavedCombos(next);
    persistCombos(next);
    if (heatmapCategory === `combo_${id}`) {
      setHeatmapCategory('custom');
    }
  }, [savedCombos, heatmapCategory]);

  // 动态分类配置 = 内置 + 保存的组合
  const dynamicConfig = useMemo(() => {
    const config = { ...CATEGORY_CONFIG };
    savedCombos.forEach(combo => {
      config[`combo_${combo.id}`] = {
        label: `📌 ${combo.label}`,
        names: new Set(combo.names),
        accent: combo.accent,
        desc: `自定义组合 · ${combo.names.length} 行业`,
        _isCombo: true,
        _comboId: combo.id,
        _comboLevel: combo.level || 1,
      };
    });
    return config;
  }, [savedCombos]);

  // 二级行业数据（自选二级 + 组合二级 + 趋势信号晴雨表都需要）
  const l2Result = useMCP('industry_sw_daily', { symbol: '二级行业', start_date: startStr, end_date: endStr, limit: 5000 });
  const l2Parsed = useMemo(() => parseSWDaily(l2Result.data), [l2Result.data]);

  // 自选模式用的行业列表和矩阵
  const customIndustries = customLevel === 1 ? industries : l2Parsed.industries;
  const customMatrix = customLevel === 1 ? matrix : l2Parsed.matrix;
  const customDates = customLevel === 1 ? dates : l2Parsed.dates;

  // 计算 filteredIndustries
  const allClassified = useMemo(() => new Set([...CYCLICAL_NAMES, ...DEFENSIVE_NAMES, ...GROWTH_NAMES]), []);
  const heatmapConfig = dynamicConfig[heatmapCategory];
  const filteredIndustries = useMemo(() => {
    // 自选模式：用自定义选中的行业
    if (heatmapCategory === 'custom') {
      return customIndustries.filter(i => customSelected.includes(i.name));
    }
    // 组合模式：用组合保存的行业列表
    if (heatmapConfig?._isCombo) {
      const comboLevel = heatmapConfig._comboLevel || 1;
      const source = comboLevel === 2 ? l2Parsed.industries : industries;
      return source.filter(i => heatmapConfig.names.has(i.name));
    }
    const base = industries.filter(i => heatmapConfig?.names?.has(i.name));
    if (heatmapCategory === 'cyclical') {
      const uncategorized = industries.filter(i => !allClassified.has(i.name));
      return [...base, ...uncategorized];
    }
    return base;
  }, [industries, heatmapCategory, heatmapConfig, allClassified, customIndustries, customSelected, l2Parsed.industries]);

  // 自选模式的热力图数据（传给 HeatmapChart）
  const isComboMode = heatmapConfig?._isCombo;
  const comboLevel = heatmapConfig?._comboLevel || 1;
  const effectiveLevel = heatmapCategory === 'custom' ? customLevel : comboLevel;
  const activeMatrix = (heatmapCategory === 'custom' || isComboMode) && effectiveLevel === 2 ? customMatrix : matrix;
  const activeDates = (heatmapCategory === 'custom' || isComboMode) && effectiveLevel === 2 ? customDates : dates;

  const avgChange = filteredIndustries.length
    ? filteredIndustries.reduce((s, i) => s + (i.change || 0), 0) / filteredIndustries.length : 0;

  // 数据加载完成后自动选中第一个行业
  useEffect(() => {
    if (!activeInd && industries.length > 0) {
      setActiveInd(industries[0].name);
    }
  }, [industries, activeInd]);

  const selName = activeInd || (industries[0]?.name || '');
  const sel = industries.find(i => i.name === selName);

  const dailyResult = useMCP('industry_daily_query', selName ? { industry: selName, limit: 120 } : null);
  const chartData = useMemo(() => parseDaily(dailyResult.data), [dailyResult.data]);
  const latest = chartData[chartData.length - 1] || {};
  const prev = chartData[chartData.length - 2] || {};

  // 排序
  const sorted = useMemo(() => [...industries].sort((a, b) => (b.change || 0) - (a.change || 0)), [industries]);
  const top5 = sorted.slice(0, 5);
  const bottom5 = sorted.slice(-5).reverse();

  // 热力图点击 → 联动行业选择
  const handleIndustrySelect = useCallback((name) => {
    setActiveInd(name);
  }, []);

  return (
    <div>
      <UpdateTimestamp updatedAt={updatedAt} />
      {/* 英雄区 */}
      <ErrorBoundary><Hero industries={industries} dates={dates} /></ErrorBoundary>

      {/* 动态警告条 */}
      <ErrorBoundary>
        <WarningBar
          l1Industries={industries} l1Matrix={matrix} l1Dates={dates}
        />
      </ErrorBoundary>

      {/* ═══ 区块一：趋势与信号 ═══ */}
      <section id="signals" style={{ paddingBottom: 24, borderBottom: '1px solid rgba(212,168,83,0.04)' }}>
        <SectionHeader badge="📡 趋势与信号" title="市场结构" highlight="晴雨表" desc="先行/滞后行业信号 + 因果传导 + 阵营对比" />
        <ErrorBoundary>
          <TrendsAndSignals
            l1Industries={industries}
            l2Industries={l2Parsed.industries}
            l1Dates={dates}
            l2Dates={l2Parsed.dates}
            l1Matrix={matrix}
            l2Matrix={l2Parsed.matrix}
          />
        </ErrorBoundary>
      </section>

      <hr className="section-divider" />

      {/* ═══ 区块二：行业热力图 ═══ */}
      <section id="heatmap" style={{ paddingBottom: 24, borderBottom: '1px solid rgba(212,168,83,0.04)' }}>
        <SectionHeader badge="行业轮动" title="全行业" highlight="波动率热力图" desc="申万一级行业涨跌幅排行，点击方格下钻二级行业" />

        {/* 控制栏 — 在卡片外部，水平排列 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
          {/* 刷新行情数据按钮 */}
          <button
            onClick={handleDataRefresh}
            disabled={dataRefreshing}
            style={{
              padding: '6px 16px', borderRadius: 8, fontSize: 'var(--fs-sm)', fontWeight: 700,
              background: dataRefreshing ? 'rgba(212,168,83,0.08)' : 'rgba(212,168,83,0.15)',
              border: `1.5px solid ${dataRefreshing ? 'var(--border-subtle)' : 'rgba(212,168,83,0.4)'}`,
              color: dataRefreshing ? 'var(--text-muted)' : 'var(--accent-gold)',
              cursor: dataRefreshing ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}
          >
            {dataRefreshing ? '⏳ 采集中...' : '🔄 刷新行情'}
          </button>
          {collectStatus && !dataRefreshing && (
            <span style={{ fontSize: 'var(--fs-xs)', color: collectStatus.startsWith('✅') ? 'var(--accent-green)' : 'var(--accent-red)' }}>
              {collectStatus}
            </span>
          )}

          {/* 分类按钮 */}
          {Object.entries(CATEGORY_CONFIG).map(([key, cfg]) => (
            <button key={key} onClick={() => { setHeatmapCategory(key); setDrillTarget(null); }}
              style={{
                padding: '6px 16px', borderRadius: 6, fontSize: 'var(--fs-sm)', fontWeight: 600,
                background: heatmapCategory === key ? `${cfg.accent}22` : 'transparent',
                color: heatmapCategory === key ? cfg.accent : 'var(--text-secondary)',
                border: `1.5px solid ${heatmapCategory === key ? cfg.accent : 'var(--border-subtle)'}`,
                cursor: 'pointer', transition: 'all 0.2s',
              }}>
              {cfg.label}
            </button>
          ))}
          {/* 已保存的组合标签 */}
          {savedCombos.map(combo => {
            const key = `combo_${combo.id}`;
            const isActive = heatmapCategory === key;
            return (
              <span key={key} style={{ position: 'relative', display: 'inline-flex' }}>
                <button
                  onClick={() => { setHeatmapCategory(key); setDrillTarget(null); }}
                  style={{
                    padding: '6px 16px', borderRadius: 6, fontSize: 'var(--fs-sm)', fontWeight: 600,
                    background: isActive ? `${combo.accent}22` : 'transparent',
                    color: isActive ? combo.accent : 'var(--text-secondary)',
                    border: `1.5px solid ${isActive ? combo.accent : 'var(--border-subtle)'}`,
                    cursor: 'pointer', transition: 'all 0.2s',
                    paddingRight: 28,
                  }}>
                  📌 {combo.label}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteCombo(combo.id); }}
                  title="删除组合"
                  style={{
                    position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)',
                    width: 18, height: 18, borderRadius: 9, border: 'none',
                    background: isActive ? `${combo.accent}33` : 'transparent',
                    color: isActive ? combo.accent : 'var(--text-muted)',
                    fontSize: 11, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    lineHeight: 1, padding: 0,
                  }}>×</button>
              </span>
            );
          })}

          {/* 天数选择 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginLeft: 8 }}>
            <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>天数</span>
            <input
              type="number"
              min={3}
              max={60}
              value={heatmapDays}
              onChange={e => {
                const v = parseInt(e.target.value, 10);
                if (!isNaN(v) && v >= 3 && v <= 60) setHeatmapDays(v);
              }}
              style={{
                width: 46, padding: '3px 6px', borderRadius: 4,
                fontSize: 'var(--fs-sm)', fontWeight: 600,
                background: 'var(--bg-panel)', color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)', textAlign: 'center',
                outline: 'none',
              }}
            />
          </div>

          {/* 均涨跌 — 醒目显示 */}
          {filteredIndustries.length > 0 && (
            <span style={{
              fontSize: 18, fontWeight: 800, letterSpacing: '0.5px',
              color: avgChange >= 0 ? '#E85050' : '#3DBB6E',
              marginLeft: 4,
              textShadow: avgChange >= 0
                ? '0 0 12px rgba(232,80,80,0.35)'
                : '0 0 12px rgba(61,187,110,0.35)',
            }}>
              {avgChange >= 0 ? '▲' : '▼'} 均涨 {avgChange.toFixed(2)}%
            </span>
          )}

          {/* 提示文字 — 右侧水平排列 */}
          <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', marginLeft: 'auto' }}>
            💡 点击方格下钻二级行业 → 再点击查看成分股
          </span>
        </div>

        {/* 自选模式：行业选择器 + 组合保存 */}
        {heatmapCategory === 'custom' && (
          <div style={{ marginBottom: 12 }}>
            <IndustryPicker
              allIndustries={industries}
              l2Industries={l2Parsed.industries}
              selectedNames={customSelected}
              onToggle={(namesOrList, isList) => {
                if (isList) setCustomSelected(namesOrList);
                else setCustomSelected([]);
              }}
              level={customLevel}
              setLevel={lv => { setCustomLevel(lv); setCustomSelected([]); }}
            />
            {/* 保存为组合 */}
            {customSelected.length > 0 && (
              <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                {!showComboSave ? (
                  <button onClick={() => setShowComboSave(true)} style={{
                    padding: '5px 14px', borderRadius: 6, fontSize: 'var(--fs-xs)', fontWeight: 600,
                    background: 'rgba(155,126,200,0.12)', border: '1px solid #9B7EC844',
                    color: '#9B7EC8', cursor: 'pointer',
                  }}>
                    💾 保存为组合
                  </button>
                ) : (
                  <>
                    <input
                      type="text"
                      value={comboNameInput}
                      onChange={e => setComboNameInput(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') saveCombo(comboNameInput); }}
                      placeholder="输入组合名称..."
                      autoFocus
                      style={{
                        padding: '4px 10px', borderRadius: 5, fontSize: 'var(--fs-sm)',
                        background: 'var(--bg-primary)', color: 'var(--text-primary)',
                        border: '1px solid #9B7EC844', outline: 'none', width: 160,
                      }}
                    />
                    <button onClick={() => saveCombo(comboNameInput)} disabled={!comboNameInput.trim()} style={{
                      padding: '4px 12px', borderRadius: 5, fontSize: 'var(--fs-xs)', fontWeight: 600,
                      background: comboNameInput.trim() ? '#9B7EC8' : 'rgba(155,126,200,0.2)',
                      border: 'none', color: comboNameInput.trim() ? '#fff' : 'var(--text-muted)',
                      cursor: comboNameInput.trim() ? 'pointer' : 'default',
                    }}>确认</button>
                    <button onClick={() => { setShowComboSave(false); setComboNameInput(''); }} style={{
                      padding: '4px 8px', borderRadius: 5, fontSize: 'var(--fs-xs)',
                      background: 'transparent', border: '1px solid var(--border-subtle)',
                      color: 'var(--text-muted)', cursor: 'pointer',
                    }}>取消</button>
                  </>
                )}
                <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>
                  已选 {customSelected.length} 行业 · {customLevel === 1 ? '一级' : '二级'}行业
                </span>
              </div>
            )}
          </div>
        )}

        <CardWrapper style={{ padding: '24px 30px' }}>
          <HeatmapChart
            filteredIndustries={filteredIndustries}
            dates={activeDates} matrix={activeMatrix}
            onIndustrySelect={handleIndustrySelect}
            activeCategory={heatmapCategory}
            displayDays={heatmapDays}
            drillTarget={drillTarget}
            setDrillTarget={setDrillTarget}
            customLevel={effectiveLevel}
          />
        </CardWrapper>


      </section>

      <hr className="section-divider" />

      {/* ═══ 区块三：排名详情 ═══ */}
      <section id="ranking" style={{ paddingBottom: 24 }}>
        <SectionHeader badge="📊 行业排名" title="当期" highlight="TOP / BOTTOM" desc="各维度排名前 5 / 后 5 行业" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 20, marginBottom: 20 }}>
          <RankingTable title="🔥 涨幅 TOP 5" subtitle="· 今日" items={top5} colorKey="up" />
          <RankingTable title="❄️ 跌幅 TOP 5" subtitle="· 今日" items={bottom5} colorKey="down" />
        </div>

        {/* 行业详情（由热力图点击驱动） */}
        <ErrorBoundary>
          <IndustryDetail sel={sel} chartData={chartData} latest={latest} prev={prev} />
        </ErrorBoundary>
      </section>

      <hr className="section-divider" />

      {/* ═══ 区块四：产业链穿透 ═══ */}
      <section id="chain" style={{ paddingBottom: 24 }}>
        <ErrorBoundary><ChainView industries={industries} /></ErrorBoundary>
      </section>

      <hr className="section-divider" />

      {/* 区块四附：能源专项 */}
      <div style={{ paddingBottom: 24 }}>
        <ErrorBoundary><EnergySection /></ErrorBoundary>
      </div>

      <hr className="section-divider" />

      {/* ═══ 区块五：季节性相关性分析 ═══ */}
      <section id="seasonal" style={{ paddingBottom: 24 }}>
        <ErrorBoundary><SeasonalCorrelation industries={industries} /></ErrorBoundary>
      </section>
    </div>
  );
}
