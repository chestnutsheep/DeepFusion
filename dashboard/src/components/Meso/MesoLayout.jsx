import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useMCP} from '../../hooks/useMCP';
import DataChart from '../common/DataChart';
import DataCard from '../common/DataCard';
import CardWrapper from '../common/CardWrapper';
import ErrorBoundary from '../common/ErrorBoundary';
import * as echarts from 'echarts';

// ── CSV 解析工具 ──

/**
 * 解析 industry_sw_daily 返回的 CSV。
 * 列序: 指数代码(0), 指数名称(1), 发布日期(2), 收盘指数(3), 成交量(4),
 *       涨跌幅(5), 换手率(6), 市盈率(7), 市净率(8), 均价(9),
 *       成交额占比(10), 流通市值(11), 平均流通市值(12), 股息率(13)
 * 
 * 返回 { industries: 按行业名索引的最新快照, dates: 所有日期, matrix: 行业×日期涨跌幅矩阵 }
 */
function parseSWDaily(csv) {
  if (!csv) return { industries: [], dates: [], matrix: {} };
  const rows = csv.trim().split('\n').slice(1).map(l => l.split(','));
  if (!rows.length) return { industries: [], dates: [], matrix: {} };

  // 收集所有日期（去重+排序）
  const dateSet = new Set();
  rows.forEach(r => { if (r[2]?.trim()) dateSet.add(r[2].trim()); });
  const dates = [...dateSet].sort();

  // 按行业分组，取最新日期作为快照
  const byName = {};
  rows.forEach(r => {
    const name = r[1]?.trim();
    if (!name) return;
    if (!byName[name]) byName[name] = [];
    byName[name].push({
      name,
      date: r[2]?.trim(),
      close: parseFloat(r[3]) || 0,
      volume: parseFloat(r[4]) || 0,        // 成交量（手）
      change: parseFloat(r[5]) || 0,         // 涨跌幅 %
      turnover: parseFloat(r[6]) || 0,       // 换手率 %
      pe: parseFloat(r[7]) || 0,
      pb: parseFloat(r[8]) || 0,
      avgPrice: parseFloat(r[9]) || 0,       // 均价
      amountRatio: parseFloat(r[10]) || 0,   // 成交额占比 %
      mktCap: parseFloat(r[11]) || 0,        // 流通市值（元）
      code: r[0]?.trim(),
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
    recs.forEach(r => { matrix[name][r.date] = r.change; });
  }

  return { industries, dates, matrix };
}

/** 行业日线 CSV — 列序同 parseSWDaily */
function parseDaily(csv) {
  if (!csv) return [];
  return csv.trim().split('\n').slice(1).map(l => {
    const p = l.split(',');
    return {
      period: p[2]?.slice(5) || p[2]?.trim() || '',
      close: parseFloat(p[3]) || 0,
      volume: parseFloat(p[4]) || 0,
      change: parseFloat(p[5]) || 0,
      turnover: parseFloat(p[6]) || 0,
      mktCap: parseFloat(p[11]) || 0,
    };
  }).filter(d => !isNaN(d.close)).slice(-120);
}

// ── 区块组件 ──

/** 英雄区 */
function Hero({ industries }) {
  const topInd = industries.length > 0
    ? [...industries].sort((a, b) => b.change - a.change)[0]
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
        {topInd && (
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
  defensive: { label: '🛡️ 强防御', names: DEFENSIVE_NAMES, accent: '#5B8FA8', desc: '穿越周期刚需' },
  growth:    { label: '⚔️ 进攻型', names: GROWTH_NAMES,    accent: '#C47B7B', desc: '高成长高Beta' },
};

// ── 工具函数 ──

/** 涨跌幅 → 热力色 (treemap 用) */
function changeToColor(v) {
  if (v > 3)   return '#c85454';
  if (v > 1.5) return '#e29944';
  if (v > 0.3) return '#e7e37f';
  if (v > -0.3)return 'rgb(238 240 233 / 0.81)';
  if (v > -1.5)return '#b1d56b';
  if (v > -3)  return '#6ac561';
  return '#21af7b';
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
  const { data: l2Raw } = useMCP('industry_sw_daily', { symbol: '二级行业', start_date: startStr, limit: 2000 });

  const mapping = useMemo(() => parseTreeMapping(treeRaw), [treeRaw]);
  const l2Parsed = useMemo(() => parseSWDaily(l2Raw), [l2Raw]);

  const subIndustries = useMemo(() => {
    if (!l2Parsed.industries.length) return [];
    // 优先用 tree mapping，回退到名称包含匹配
    const byMapping = l2Parsed.industries.filter(i => mapping[i.name] === target.industry);
    if (byMapping.length > 0) return byMapping;
    // 回退：名称包含关系（如"银行II"包含"银行"，"白酒"在"食品饮料"下但名称不含）
    return l2Parsed.industries.filter(i => {
      const parent = mapping[i.name];
      if (parent) return parent === target.industry;
      // 最终回退：代码前缀匹配
      const l1 = l2Parsed.industries.find(j => j.name === target.industry);
      return l1 && i.code && l1.code && i.code.substring(0, 5) === l1.code.substring(0, 5);
    });
  }, [l2Parsed, mapping, target.industry]);

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
        formatter: p => `${p.name}<br/>涨跌幅: ${p.data._change >= 0 ? '+' : ''}${p.data._change.toFixed(2)}%<br/>流通市值: ${(p.data._mktCap / 1e8).toFixed(0)}亿<br/>PE: ${p.data._pe.toFixed(1)}  PB: ${p.data._pb.toFixed(2)}`,
      },
      series: [{
        type: 'treemap',
        data,
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        label: {
          show: true,
          formatter: p => `${p.name}\n${p.data._change >= 0 ? '+' : ''}${p.data._change.toFixed(1)}%`,
          fontSize: 11,
          color: '#F0E8D8',
        },
        upperLabel: { show: false },
        itemStyle: { borderColor: 'rgba(212,168,83,0.15)', borderWidth: 1, gapWidth: 2 },
      }],
    });
    return () => chart.dispose();
  }, [subIndustries]);

  const avgChange = subIndustries.length ? subIndustries.reduce((s, i) => s + i.change, 0) / subIndustries.length : 0;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <button onClick={onBack} style={{
          padding: '4px 12px', borderRadius: 6, fontSize: 'var(--fs-sm)',
          background: 'rgba(212,168,83,0.1)', border: '1px solid var(--border-subtle)',
          color: 'var(--accent-gold)', cursor: 'pointer',
        }}>← 返回热力图</button>
        <span style={{ fontSize: 'var(--fs-md)', fontWeight: 700 }}>{target.industry}</span>
        <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>· {target.date} · 二级行业树状图</span>
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
    </div>
  );
}

// ── 热力图交互区 ──

/** 行业热力图 — 三分类Tab + 可点击下钻 */
function HeatmapSection({ industries, dates, matrix, onIndustrySelect }) {
  const [activeCategory, setActiveCategory] = useState('cyclical');
  const [drillTarget, setDrillTarget] = useState(null); // { industry, date }
  const chartRef = useRef(null);

  const currentConfig = CATEGORY_CONFIG[activeCategory];
  const allClassified = useMemo(() => new Set([...CYCLICAL_NAMES, ...DEFENSIVE_NAMES, ...GROWTH_NAMES]), []);

  const filteredIndustries = useMemo(() => {
    const base = industries.filter(i => currentConfig.names.has(i.name));
    if (activeCategory === 'cyclical') {
      const uncategorized = industries.filter(i => !allClassified.has(i.name));
      return [...base, ...uncategorized];
    }
    return base;
  }, [industries, activeCategory, currentConfig.names, allClassified]);

  // 热力图渲染（非下钻状态）
  useEffect(() => {
    if (drillTarget || !chartRef.current || !filteredIndustries.length || !dates.length) return;
    const chart = echarts.init(chartRef.current, 'df-dark');
    const names = filteredIndustries.map(i => i.name || i.code);
    const recentDates = dates.slice(-20);
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
      grid: { left: 90, right: 16, top: 8, bottom: 36 },
      xAxis: { type: 'category', data: recentDates.map(d => d.slice(5)), axisLabel: { fontSize: 12, rotate: 35 } },
      yAxis: { type: 'category', data: names, axisLabel: { fontSize: 12, width: 72, overflow: 'truncate' } },
      visualMap: {
        min: -4, max: 4, calculable: true, orient: 'horizontal', left: 'center', bottom: 0,
        inRange: { color: ['rgb(8 86 11)', '#217819', '#44b63a', '#75d378', '#f5c4b4', '#e2806f', '#c43e3e'] },
        textStyle: { color: '#CBC0B0', fontSize: 13 },
      },
      series: [{
        type: 'heatmap', data,
        label: { show: true, formatter: p => `${p.data[2].toFixed(1)}%`, fontSize: 12, color: '#F0E8D8' },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgb(66 66 66 / 0.5)' } },
      }],
    });
    // 点击方格 → 下钻
    chart.on('click', (params) => {
      if (params.data) {
        const industryName = names[params.data[1]];
        const date = recentDates[params.data[0]];
        setDrillTarget({ industry: industryName, date });
        onIndustrySelect(industryName);
      }
    });
    return () => chart.dispose();
  }, [filteredIndustries, dates, matrix, drillTarget, onIndustrySelect]);

  const avgChange = filteredIndustries.length
    ? filteredIndustries.reduce((s, i) => s + i.change, 0) / filteredIndustries.length : 0;
  const h = Math.max(220, filteredIndustries.length * 28 + 50);

  return (
    <div>
      {/* 三分类 Tab */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        {Object.entries(CATEGORY_CONFIG).map(([key, cfg]) => (
          <button key={key} onClick={() => { setActiveCategory(key); setDrillTarget(null); }}
            style={{
              padding: '6px 16px', borderRadius: 6, fontSize: 'var(--fs-sm)', fontWeight: 600,
              background: activeCategory === key ? `${cfg.accent}22` : 'transparent',
              color: activeCategory === key ? cfg.accent : 'var(--text-secondary)',
              border: `1.5px solid ${activeCategory === key ? cfg.accent : 'var(--border-subtle)'}`,
              cursor: 'pointer', transition: 'all 0.2s',
            }}>
            {cfg.label}
            <span style={{ fontSize: 'var(--fs-2xs)', fontWeight: 400, marginLeft: 4, opacity: 0.7 }}>{cfg.desc}</span>
          </button>
        ))}
      </div>

      {/* 热力图 或 下钻 */}
      {drillTarget ? (
        <IndustryDrilldown target={drillTarget} onBack={() => setDrillTarget(null)} />
      ) : (
        <div>
          <div style={{ fontSize: 'var(--fs-sm)', fontWeight: 700, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: currentConfig.accent }}>{currentConfig.label}</span>
            <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 400, color: 'var(--text-muted)' }}>· {filteredIndustries.length} 个行业</span>
            {filteredIndustries.length > 0 && (
              <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, marginLeft: 'auto',
                color: avgChange >= 0 ? 'var(--accent-red)' : 'var(--accent-green)'
              }}>
                均涨 {avgChange.toFixed(2)}%
              </span>
            )}
          </div>
          <div ref={chartRef} style={{ width: '100%', height: h }} />
          <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)', marginTop: 4, textAlign: 'center' }}>
            💡 点击方格可下钻至二级行业树状图
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
                }}>{i.change >= 0 ? '+' : ''}{i.change.toFixed(2)}%</td>
                <td style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '1px solid rgba(212,168,83,0.04)' }}>{i.pe.toFixed(1)}</td>
                <td style={{ padding: '6px 8px', textAlign: 'right', borderBottom: '1px solid rgba(212,168,83,0.04)' }}>{i.pb.toFixed(2)}</td>
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
  const mktCapYi = sel.mktCap ? (sel.mktCap / 1e8) : 0;
  const metrics = [
    { key: 'close', label: '收盘指数', unit: '', decimals: 2, higherBetter: true },
    { key: 'change', label: '涨跌幅', unit: '%', decimals: 2, higherBetter: true },
    { key: 'turnover', label: '换手率', unit: '%', decimals: 2, higherBetter: null },
  ];
  const staticMetrics = [
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
              <span>收盘指数</span><span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{sel.close.toFixed(2)}</span>
            </li>
            <li style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)', padding: '3px 0', display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(212,168,83,0.04)' }}>
              <span>PE(TTM)</span><span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{sel.pe.toFixed(1)}</span>
            </li>
            <li style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-secondary)', padding: '3px 0', display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(212,168,83,0.04)' }}>
              <span>PB</span><span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{sel.pb.toFixed(2)}</span>
            </li>
          </ul>
        </CardWrapper>
        {/* 涨跌指标卡 */}
        {metrics.map(m => (
          <DataCard key={m.key} label={m.label} value={latest[m.key]} prevValue={prev[m.key]} unit={m.unit} decimals={m.decimals} higherBetter={m.higherBetter} />
        ))}
        {/* 静态指标 */}
        {staticMetrics.map(m => (
          <DataCard key={m.key} label={m.label} value={m.value} unit={m.unit} decimals={m.decimals} higherBetter={m.higherBetter} />
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
          <DataChart data={chartData} series={[{ key: 'change', name: '涨跌幅', color: '#7B5E7B', type: 'bar' }]} dateKey="period" height={260} />
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
            background: i.change >= 0 ? 'rgba(196,123,123,0.12)' : 'rgba(62,107,92,0.12)',
            color: i.change >= 0 ? 'var(--accent-red)' : 'var(--accent-green)',
          }}>{i.name} {i.change >= 0 ? '+' : ''}{i.change.toFixed(1)}%</span>
        ))}
      </div>
      <div style={{ fontSize: 'var(--fs-xs)', color: 'var(--text-muted)' }}>
        行业数 {items.length} · 平均涨幅 {items.length ? (items.reduce((s, i) => s + i.change, 0) / items.length).toFixed(2) : '—'}%
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
    return csv.trim().split('\n').slice(1).map(l => {
      const p = l.split(',');
      return { period: p[0]?.slice(5) || '', close: parseFloat(p[1]) || 0 };
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
  const sorted = useMemo(() => [...industries].sort((a, b) => b.change - a.change), [industries]);
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
        <CardWrapper style={{ padding: 'var(--sp-xl)' }}>
          <HeatmapSection industries={industries} dates={dates} matrix={matrix} onIndustrySelect={handleIndustrySelect} />
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
