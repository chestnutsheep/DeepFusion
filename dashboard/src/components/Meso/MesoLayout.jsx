import {useEffect, useMemo, useRef, useState} from 'react';
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
        borderRadius: 20, fontSize: 11, fontWeight: 600,
        color: 'var(--accent-gold)', marginBottom: 10,
      }}>✦ DeepFusion · 中观产业</span>
      <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: 0.5 }}>
        行业景气与 <span style={{ color: 'var(--accent-gold)' }}>产业链定位</span>
      </h1>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 640, marginTop: 4 }}>
        行业热度追踪 · 产业链结构拆解 · 景气轮动信号 · 与宏观/微观联动
      </p>
      <div style={{ display: 'flex', gap: 18, marginTop: 10, fontSize: 11, color: 'var(--text-muted)' }}>
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
        borderRadius: 16, fontSize: 10, fontWeight: 600,
        color: 'var(--accent-rose)', marginBottom: 6,
      }}>{badge}</span>
      <h2 style={{ fontSize: 18, fontWeight: 700 }}>
        {title} <span style={{ color: 'var(--accent-gold)' }}>{highlight}</span>
      </h2>
      {desc && <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 2 }}>{desc}</p>}
    </div>
  );
}

/** 行业热力图 — x=日期, y=行业, value=涨跌幅 */
function HeatmapChart({ industries, dates, matrix }) {
  const chartRef = useRef(null);
  useEffect(() => {
    if (!chartRef.current || !industries.length || !dates.length) return;
    const chart = echarts.init(chartRef.current, 'df-dark');
    const names = industries.map(i => i.name || i.code);
    // 只取最近 30 个交易日
    const recentDates = dates.slice(-30);
    const data = [];
    for (let yi = 0; yi < names.length; yi++) {
      for (let xi = 0; xi < recentDates.length; xi++) {
        const val = matrix[names[yi]]?.[recentDates[xi]];
        if (val !== undefined) data.push([xi, yi, val]);
      }
    }
    chart.setOption({
      "tooltip": {
        "formatter": p => `${names[p.data[1]]}<br/>${recentDates[p.data[0]]}: ${p.data[2] >= 0 ? '+' : ''}${p.data[2].toFixed(2)}%`,
      },
      "grid": { "left": 90, "right": 30, "top": 10, "bottom": 40 },
      "xAxis": { "type": 'category', "data": recentDates.map(d => d.slice(5)), "axisLabel": { "fontSize": 10, "rotate": 30 } },
      "yAxis": { "type": 'category', "data": names, "axisLabel": { "fontSize": 12 } },
      "visualMap": {
        "min": -4, "max": 4, "calculable": true, "orient": 'horizontal', "left": 'center', "bottom": 0,
        "inRange": { "color": ['#FFF5F5', '#FFCCCC', '#FF9999', '#FF6666', '#CC3333', '#990000'] },
        "textStyle": { "color": '#CBC0B0', "fontSize": 12 },
      },
      "series": [{ "type": 'heatmap', data, "label": { "show": true, "formatter": p => `${p.data[2].toFixed(1)}%`, "fontSize": 11, "color": '#F0E8D8' },
        "emphasis": { "itemStyle": { "shadowBlur": 10, "shadowColor": 'rgba(0,0,0,0.5)' } },
      }]
    });
    return () => chart.dispose();
  }, [industries, dates, matrix]);
  return <div ref={chartRef} style={{ width: '100%', height: Math.max(280, industries.length * 22 + 30) }} />;
}

/** 行业排名 TOP/BOTTOM 表格 */
function RankingTable({ title, subtitle, items, colorKey }) {
  const isUp = colorKey === 'up';
  return (
    <CardWrapper style={{ padding: 16 }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
        {title} <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 400 }}>{subtitle}</span>
      </h3>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, minWidth: 320 }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 10, color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>排名</th>
              <th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 10, color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>行业</th>
              <th style={{ textAlign: 'right', padding: '6px 8px', fontSize: 10, color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>涨跌幅</th>
              <th style={{ textAlign: 'right', padding: '6px 8px', fontSize: 10, color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>PE</th>
              <th style={{ textAlign: 'right', padding: '6px 8px', fontSize: 10, color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>PB</th>
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
        <CardWrapper style={{ padding: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-gold)', marginBottom: 8 }}>📊 行业概况</div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            <li style={{ fontSize: 12, color: 'var(--text-secondary)', padding: '3px 0', display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(212,168,83,0.04)' }}>
              <span>收盘指数</span><span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{sel.close.toFixed(2)}</span>
            </li>
            <li style={{ fontSize: 12, color: 'var(--text-secondary)', padding: '3px 0', display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(212,168,83,0.04)' }}>
              <span>PE(TTM)</span><span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{sel.pe.toFixed(1)}</span>
            </li>
            <li style={{ fontSize: 12, color: 'var(--text-secondary)', padding: '3px 0', display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(212,168,83,0.04)' }}>
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
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📈 行业指数走势 <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 400 }}>· 近 1 年</span></h3>
          <DataChart data={chartData} series={[{ key: 'close', name: `${sel.name}指数`, color: '#D4A853', type: 'line' }]} dateKey="period" height={260} />
        </CardWrapper>
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>📊 涨跌幅走势 <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 400 }}>· 近期</span></h3>
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
    <CardWrapper style={{ padding: 16, borderLeft: `3px solid ${borderColor}` }}>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>{icon} {title}</h3>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
        {items.slice(0, 6).map(i => (
          <span key={i.name} style={{
            padding: '2px 8px', borderRadius: 6, fontSize: 10,
            background: i.change >= 0 ? 'rgba(196,123,123,0.12)' : 'rgba(62,107,92,0.12)',
            color: i.change >= 0 ? 'var(--accent-red)' : 'var(--accent-green)',
          }}>{i.name} {i.change >= 0 ? '+' : ''}{i.change.toFixed(1)}%</span>
        ))}
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
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
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>原油价格走势</h3>
          <DataChart data={oilData} series={[{ key: 'close', name: '原油', color: '#C47B7B', type: 'line' }]} dateKey="period" height={240} />
        </CardWrapper>
        <CardWrapper style={{ padding: 16 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>煤炭价格走势</h3>
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

  return (
    <div>
      {/* 英雄区 */}
      <ErrorBoundary><Hero industries={industries} /></ErrorBoundary>

      {/* 区块一：行业热力图与轮动 */}
      <div style={{ paddingBottom: 24, borderBottom: '1px solid rgba(212,168,83,0.04)' }}>
        <SectionHeader badge="行业轮动" title="全行业" highlight="波动率热力图" desc="申万一级行业涨跌幅排行，颜色越红 = 表现越强" />
        <CardWrapper style={{ padding: 16 }}>
          <HeatmapChart industries={industries} dates={dates} matrix={matrix} />
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

        {/* 行业快速导航 */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
          {industries.slice(0, 31).map(ind => (
            <button key={ind.code} onClick={() => setActiveInd(ind.name)}
              style={{
                padding: '4px 14px', borderRadius: 4, fontSize: 12,
                fontWeight: selName === ind.name ? 700 : 500,
                background: selName === ind.name ? 'var(--accent-gold)' : 'transparent',
                color: selName === ind.name ? '#fff' : 'var(--text-secondary)',
                border: '1.5px solid var(--border-subtle)', cursor: 'pointer',
              }}>
              {ind.name}
            </button>
          ))}
        </div>

        {/* 行业详情 */}
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
