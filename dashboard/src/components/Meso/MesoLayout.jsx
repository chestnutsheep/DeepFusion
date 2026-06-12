import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useMCP} from '../../hooks/useMCP';
import DataChart from '../common/DataChart';
import DataCard from '../common/DataCard';
import CardWrapper from '../common/CardWrapper';
import ErrorBoundary from '../common/ErrorBoundary';
import * as echarts from 'echarts';

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

/** 英雄区 */
function Hero({ industries }) {
  const topInd = industries.length > 0
    ? [...industries].sort((a, b) => (b.change || 0) - (a.change || 0))[0]
    : null;
  return (
    <div style={{
      padding: '32px 0 20px',
      borderBottom: '1px solid var(--border-subtle)',
      marginBottom: 24,
    }}>
      <span style={{
        display: 'inline-block', padding: '4px 14px',
        background: 'var(--shadow-glow)', border: '1px solid var(--border-subtle)',
        borderRadius: 20, fontSize: 'var(--fs-sm)', fontWeight: 600,
        color: 'var(--accent-gold)', marginBottom: 10,
      }}>✦ DeepFusion · 中观产业</span>
      <h1 style={{ fontSize: 'var(--fs-2xl)', fontWeight: 700, letterSpacing: 0.5 }}>
        行业景气与 <span style={{ color: 'var(--accent-gold)' }}>产业链定位</span>
      </h1>
      <p style={{ fontSize: 'var(--fs-base)', color: 'var(--text-secondary)', maxWidth: 640, marginTop: 4 }}>
        行业热度追踪 · 产业链结构拆解 · 景气轮动信号 · 与宏观/微观联动
      </p>
      <div style={{ display: 'flex', gap: 18, marginTop: 10, fontSize: 'var(--fs-sm)', color: 'var(--text-muted)' }}>
        <span>◈ 数据源: akshare · 申万行业</span>
        <span>◈ 覆盖: {industries.length} 申万一级行业</span>
        <span>◈ 更新: 日频</span>
        {topInd && topInd.change != null && (
          <span>◈ 领涨: <span style={{ color: 'var(--accent-red)' }}>{topInd.name} {topInd.change >= 0 ? '+' : ''}{topInd.change.toFixed(2)}%</span></span>
        )}
      </div>
    </div>
  );
}

/** 区块标题 */
function SectionHeader({ badge, title, highlight, desc }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <span style={{
        display: 'inline-flex', padding: '4px 12px',
        background: 'rgba(123,94,123,0.12)', border: '1px solid rgba(123,94,123,0.2)',
        borderRadius: 16, fontSize: 'var(--fs-sm)', fontWeight: 600,
        color: 'var(--accent-rose)', marginBottom: 6,
      }}>{badge}</span>
      <h2 style={{ fontSize: 'var(--fs-lg)', fontWeight: 700 }}>
        {title} <span style={{ color: 'var(--accent-gold)' }}>{highlight}</span>
      </h2>
      {desc && <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-sm)', marginTop: 2 }}>{desc}</p>}
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
};

// ── 强周期行业的三周期映射 ──
// 基钦(库存)周期：上游原材料(钢铁/采掘，价格随库存波动) + 产成品库存(汽车/非银/综合)
// 朱格拉(设备投资)周期：机械设备(Capex周期核心载体)
// 库兹涅茨(建筑)周期：房地产 + 建筑材料(水泥/玻璃) + 建筑装饰(施工链)
const CYCLE_GROUP_ORDER = ['kitchin', 'juglar', 'kuznets'];
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

/** 行业下钻：二级行业树状图 */
function IndustryDrilldown({ target, onBack }) {
  const chartRef = useRef(null);
  const { data: treeRaw } = useMCP('industry_sw_tree', { '深度': 2, '展开': 31 });
  const today = new Date();
  const startDay = new Date(today.getTime() - 30 * 86400000);
  const startStr = startDay.toISOString().slice(0, 10).replace(/-/g, '');
  const { data: l2Raw } = useMCP('industry_sw_daily', { symbol: '二级行业', start_date: startStr, limit: 5000 });

  // 历史指数走势数据（一级行业级别）
  const { data: histRaw } = useMCP('industry_daily_query', target.industry ? { industry: target.industry, limit: 120 } : null);
  const histData = useMemo(() => parseDaily(histRaw), [histRaw]);

  const mapping = useMemo(() => parseTreeMapping(treeRaw), [treeRaw]);
  const l2Parsed = useMemo(() => parseSWDaily(l2Raw), [l2Raw]);

  const subIndustries = useMemo(() => {
    if (!l2Parsed.industries.length) return [];
    // 优先用 tree mapping，回退到名称包含匹配
    let base;
    const byMapping = l2Parsed.industries.filter(i => mapping[i.name] === target.industry);
    if (byMapping.length > 0) base = byMapping;
    else {
      // 回退：名称包含关系（如"银行II"包含"银行"，"白酒"在"食品饮料"下但名称不含）
      base = l2Parsed.industries.filter(i => {
        const parent = mapping[i.name];
        if (parent) return parent === target.industry;
        // 最终回退：代码前缀匹配
        const l1 = l2Parsed.industries.find(j => j.name === target.industry);
        return l1 && i.code && l1.code && i.code.substring(0, 5) === l1.code.substring(0, 5);
      });
    }
    // 用目标日期的涨跌幅覆盖最新值，使下钻与热力图点击日期一致
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
    }));
    chart.setOption({
      tooltip: {
        formatter: p => `${p.name}<br/>涨跌幅: ${p.data._change != null ? `${p.data._change >= 0 ? '+' : ''}${p.data._change.toFixed(2)}%` : '—'}<br/>流通市值: ${p.data._mktCap != null ? `${(p.data._mktCap / 1e8).toFixed(0)}亿` : '—'}<br/>PE: ${p.data._pe != null ? p.data._pe.toFixed(1) : '—'}  PB: ${p.data._pb != null ? p.data._pb.toFixed(2) : '—'}`,
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
    return () => chart.dispose();
  }, [subIndustries]);

  const avgChange = subIndustries.length ? subIndustries.reduce((s, i) => s + (i.change || 0), 0) / subIndustries.length : 0;

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

// ── 热力图交互区 ──

/** 行业热力图 — 纯图表渲染（控制栏由父组件渲染） */
function HeatmapChart({ filteredIndustries, dates, matrix, onIndustrySelect, activeCategory, displayDays, drillTarget, setDrillTarget }) {
  const chartRef = useRef(null);

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
    chart.setOption({
      tooltip: {
        formatter: p => `${names[p.data[1]]}<br/>${recentDates[p.data[0]]}: ${p.data[2] >= 0 ? '+' : ''}${p.data[2].toFixed(2)}%`,
      },
      grid: { left: 65, right: 70, top: 20, bottom: 60 },
      xAxis: { type: 'category', data: recentDates.map(d => d.slice(5)), axisLabel: { fontSize: 12, rotate: 35 } },
      yAxis: { type: 'category', data: names, axisLabel: { fontSize: 13, width: 68, overflow: 'truncate' } },
      visualMap: {
        min: -4, max: 4, calculable: true, orient: 'vertical', right: 4, bottom: 40,
        inRange: { color: ['rgb(158 158 158)', '#048152', '#47a83d', '#91c133', '#ccb022', '#db8f36', '#c85454'] },
        textStyle: { color: '#CBC0B0', fontSize: 13 },
      },
      series: [{
        type: 'heatmap', data,
        label: { show: true, formatter: p => `${p.data[2].toFixed(1)}%`, fontSize: 12, color: '#ffffff' },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgb(0 0 0 / 0.6)' } },
      }],
    });
    chart.on('click', (params) => {
      if (params.data) {
        const industryName = names[params.data[1]];
        const date = recentDates[params.data[0]];
        setDrillTarget({ industry: industryName, date });
        onIndustrySelect(industryName);
      }
    });
    return () => chart.dispose();
  }, [sortedIndustries, dates, matrix, drillTarget, onIndustrySelect, displayDays, setDrillTarget]);

  const h = Math.max(380, sortedIndustries.length * 40 + 90);

  if (drillTarget) {
    return <IndustryDrilldown target={drillTarget} onBack={() => setDrillTarget(null)} />;
  }

  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }}>
      <div ref={chartRef} style={{ width: '100%', height: h }} />
    </div>
  );
}

/** 三周期数据面板 — 强周期热力图左侧 */
function CyclePhasePanel({ industries, matrix, dates }) {
  // 请求三个周期的最新数据
  const { data: kitchinRaw } = useMCP('data_kitchin', {});
  const { data: juglarRaw }  = useMCP('data_juglar', {});
  const { data: kuznetsRaw } = useMCP('data_kuznets', {});

  // 解析最新周期相位
  const phases = useMemo(() => {
    const parse = (raw) => {
      try {
        const arr = typeof raw === 'string' ? JSON.parse(raw) : raw;
        if (!Array.isArray(arr) || !arr.length) return null;
        return arr[arr.length - 1];
      } catch { return null; }
    };
    return {
      kitchin: parse(kitchinRaw),
      juglar:  parse(juglarRaw),
      kuznets: parse(kuznetsRaw),
    };
  }, [kitchinRaw, juglarRaw, kuznetsRaw]);

  // 计算每组行业的 20 日波动率和均值
  const groupStats = useMemo(() => {
    const recent = dates.slice(-20);
    if (!recent.length || !industries.length) return {};
    const stats = {};
    for (const [key, grp] of Object.entries(CYCLE_GROUPS)) {
      const groupInds = industries.filter(i => grp.names.includes(i.name));
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
  }, [industries, matrix, dates]);

  // 相位名映射
  const phaseLabel = (phase, cycleKey) => {
    if (!phase) return '—';
    if (cycleKey === 'kitchin') return phase.cycle_phase_name || phase.stage || '—';
    return phase.cycle_phase_name || phase.phase || '—';
  };

  // 相位→颜色
  const phaseColor = (name) => {
    if (!name || name === '—') return 'var(--text-muted)';
    if (['主动补库', '繁荣', '复苏', '主动补库存'].includes(name)) return 'var(--accent-red)';
    if (['被动去库', '复苏', '被动去库存'].includes(name)) return '#D4A853';
    if (['被动补库', '衰退', '被动补库存'].includes(name)) return '#7B8FA8';
    if (['主动去库', '萧条', '主动去库存'].includes(name)) return 'var(--accent-green)';
    return 'var(--text-secondary)';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 15, minWidth: 250 }}>
      {CYCLE_GROUP_ORDER.map(key => {
        const grp = CYCLE_GROUPS[key];
        const ph = phases[key];
        const st = groupStats[key] || {};
        const pName = phaseLabel(ph, key);
        return (
          <CardWrapper key={key} style={{ padding: '12px 14px' }}>
            {/* 周期标题行 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 17 }}>{grp.icon}</span>
              <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--accent-gold)' }}>{grp.label}</span>
              <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>{grp.sub}</span>
            </div>
            {/* 相位标签 */}
            <div style={{ marginBottom: 8 }}>
              <span style={{
                display: 'inline-block', padding: '3px 12px', borderRadius: 14,
                fontSize: 16, fontWeight: 800,
                background: phaseColor(pName).startsWith('var') ? 'rgba(136,136,136,0.1)' : `${phaseColor(pName)}18`,
                color: phaseColor(pName), border: `1px solid ${phaseColor(pName)}33`,
              }}>
                {pName}
              </span>
            </div>
            {/* 数据指标 — 正常文字 */}
            <div style={{ display: 'flex', gap: 20, fontSize: 18, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
              <span>波动率 <b style={{ color: 'var(--text-primary)' }}>{st.vol != null ? st.vol.toFixed(2) : '—'}%</b></span>
              <span>均值 <b style={{ color: st.avg != null && st.avg >= 0 ? '#E85050' : '#3DBB6E' }}>{st.avg != null ? (st.avg >= 0 ? '+' : '') + st.avg.toFixed(2) : '—'}%</b></span>
            </div>
            {/* 关联行业 */}
            <div style={{ fontSize: 15, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.6 }}>
              {grp.names.join(' · ')}
            </div>
          </CardWrapper>
        );
      })}
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 14 }}>
        <CardWrapper style={{ padding: 'var(--sp-xl)' }}>
          <h3 style={{ fontSize: 'var(--fs-base)', fontWeight: 600, marginBottom: 10 }}>📈 行业指数走势 <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', fontWeight: 400 }}>· 近 1 年</span></h3>
          <DataChart data={chartData} series={[{ key: 'close', name: `${sel.name}指数`, color: '#D4A853', type: 'line' }]} dateKey="period" height={260} />
        </CardWrapper>
        <CardWrapper style={{ padding: 'var(--sp-xl)' }}>
          <h3 style={{ fontSize: 'var(--fs-base)', fontWeight: 600, marginBottom: 10 }}>📊 涨跌幅走势 <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', fontWeight: 400 }}>· 近期</span></h3>
          <DataChart data={chartData} series={[{ key: 'change', name: '涨跌幅', color: '#6abbdb', type: 'bar' }]} dateKey="period" height={260} />
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 14 }}>
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 14 }}>
        <DataCard label="🛢️ 原油" value={oilLatest} unit="元/桶" decimals={1} higherBetter={null}
          detail="INE主力合约" />
        <DataCard label="⚡ 动力煤" value={coalLatest} unit="元/吨" decimals={0} higherBetter={null}
          detail="郑商所主力合约" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 14 }}>
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
  // 请求最近 20 个交易日的数据，让热力图有足够列
  const today = new Date();
  const startDay = new Date(today.getTime() - 30 * 86400000); // 30自然日≈20交易日
  const startStr = startDay.toISOString().slice(0, 10).replace(/-/g, '');
  const swResult = useMCP('industry_sw_daily', { symbol: '一级行业', start_date: startStr, limit: 800 });
  const { industries, dates, matrix } = useMemo(() => parseSWDaily(swResult.data), [swResult.data]);
  const [activeInd, setActiveInd] = useState('');

  // 热力图控制状态（提升到父组件，控制栏渲染在 CardWrapper 外部）
  const [heatmapCategory, setHeatmapCategory] = useState('cyclical');
  const [heatmapDays, setHeatmapDays] = useState(20);
  const [drillTarget, setDrillTarget] = useState(null);

  // 计算 filteredIndustries（与 HeatmapChart 内部逻辑一致）
  const allClassified = useMemo(() => new Set([...CYCLICAL_NAMES, ...DEFENSIVE_NAMES, ...GROWTH_NAMES]), []);
  const heatmapConfig = CATEGORY_CONFIG[heatmapCategory];
  const filteredIndustries = useMemo(() => {
    const base = industries.filter(i => heatmapConfig.names.has(i.name));
    if (heatmapCategory === 'cyclical') {
      const uncategorized = industries.filter(i => !allClassified.has(i.name));
      return [...base, ...uncategorized];
    }
    return base;
  }, [industries, heatmapCategory, heatmapConfig.names, allClassified]);

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
      {/* 英雄区 */}
      <ErrorBoundary><Hero industries={industries} /></ErrorBoundary>

      {/* 区块一：行业热力图与轮动（可交互Tab+下钻） */}
      <div style={{ paddingBottom: 24, borderBottom: '1px solid rgba(212,168,83,0.04)' }}>
        <SectionHeader badge="行业轮动" title="全行业" highlight="波动率热力图" desc="申万一级行业涨跌幅排行，点击方格下钻二级行业" />

        {/* 控制栏 — 在卡片外部，水平排列 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
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
            💡 点击方格下钻二级行业
          </span>
        </div>

        <CardWrapper style={{ padding: 'var(--sp-xl)' }}>
          <div style={{ display: heatmapCategory === 'cyclical' ? 'flex' : 'block', gap: 16, alignItems: 'flex-start' }}>
            {heatmapCategory === 'cyclical' && (
              <div style={{ flex: '0 0 auto', minWidth: 260, maxWidth: 340 }}>
                <CyclePhasePanel industries={filteredIndustries} matrix={matrix} dates={dates} />
              </div>
            )}
            <div style={{ flex: 1, minWidth: 0 }}>
              <HeatmapChart
                filteredIndustries={filteredIndustries}
                dates={dates} matrix={matrix}
                onIndustrySelect={handleIndustrySelect}
                activeCategory={heatmapCategory}
                displayDays={heatmapDays}
                drillTarget={drillTarget}
                setDrillTarget={setDrillTarget}
              />
            </div>
          </div>
        </CardWrapper>
      </div>

      <hr className="section-divider" />

      {/* 区块二：行业排名 + 行业详情 */}
      <div style={{ paddingBottom: 24 }}>
        <SectionHeader badge="📊 行业排名" title="当期" highlight="TOP / BOTTOM" desc="各维度排名前 5 / 后 5 行业" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 12, marginBottom: 16 }}>
          <RankingTable title="🔥 涨幅 TOP 5" subtitle="· 今日" items={top5} colorKey="up" />
          <RankingTable title="❄️ 跌幅 TOP 5" subtitle="· 今日" items={bottom5} colorKey="down" />
        </div>

        {/* 行业详情（由热力图点击驱动） */}
        <ErrorBoundary>
          <IndustryDetail sel={sel} chartData={chartData} latest={latest} prev={prev} />
        </ErrorBoundary>
      </div>

      <hr className="section-divider" />

      {/* 区块三：产业链穿透 */}
      <div style={{ paddingBottom: 24 }}>
        <ErrorBoundary><ChainView industries={industries} /></ErrorBoundary>
      </div>

      <hr className="section-divider" />

      {/* 区块四：能源专项 */}
      <div style={{ paddingBottom: 24 }}>
        <ErrorBoundary><EnergySection /></ErrorBoundary>
      </div>
    </div>
  );
}
