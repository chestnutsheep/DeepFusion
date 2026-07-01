import {useEffect, useRef, useState} from 'react';
import {Menu, MenuItem} from 'react-pro-sidebar';
import {useAppStore} from '../store/index.js';
import {mcp} from '../services/mcp.js';
import * as echarts from 'echarts';

const SUB_NAV = {
  policy: ['stats','list','collect'],
  macro: ['kitchin','juglar','kuznets','kondratiev','coverage','nesting','gantt'],
  meso: ['signals','heatmap','ranking','chain'],
  micro: ['stock','fund','futures','bond','option'],
  global: ['stress','debt','capital','bubble','markets'],
};
const SUB_LABELS = {
  policy: { stats:'📊 政策统计', list:'📋 文件列表', collect:'🔄 采集管理' },
  macro: { kitchin:'📉 基钦', juglar:'📈 朱格拉', kuznets:'🏠 库兹涅茨', kondratiev:'🌊 康波', coverage:'📊 宏观覆盖', nesting:'🔗 周期嵌套', gantt:'📅 相位分布' },
  meso: { signals:'📡 趋势与信号', heatmap:'🔥 行业热力图', ranking:'📊 排名详情', chain:'⛓️ 产业链' },
  micro: { stock:'📈 个股', fund:'📦 基金', futures:'⛽ 期货', bond:'📜 债券', option:'🎯 期权' },
  global: { stress:'⚡ 金融压力', debt:'🏛️ 债务可持续', capital:'💸 资本流动', bubble:'🫧 泡沫监视', markets:'📊 衍生品市场' },
};
const SUB_SETTERS = {
  policy: 'setActivePolicySub', macro: 'setActiveMacroSub', meso: 'setActiveMesoSub',
  micro: 'setActiveMicroSub', global: 'setActiveGlobalSub',
};
const SUB_GETTERS = {
  policy: 'activePolicySub', macro: 'activeMacroSub', meso: 'activeMesoSub',
  micro: 'activeMicroSub', global: 'activeGlobalSub',
};

// ── 资产类别→跳转目标映射 ──
const ASSET_NAV_MAP = {
  '权益': { tab: 'micro', sub: 'stock' },
  '债券': { tab: 'micro', sub: 'bond' },
  '基金': { tab: 'micro', sub: 'fund' },
  '现金': { tab: 'global', sub: 'markets' },
};

// ── 基于周期数据动态计算资产类别提示卡片 ──
// cycleDirection / attitude / subAlloc 全部由周期 zscore + phase 动态推导
function computeAssetDetail(kit, jug, kuz, kon, equity, bond, fund, cash) {
  const kz = kit?.composite_z ?? 0;
  const jz = jug?.composite_z ?? 0;
  const kp = kon?.phase ?? 0;

  // ── 权益方向 ──
  let equityDir, equityAttitude;
  if (kz > 0.5 && jz > 0.3) { equityDir = '强顺周期做多'; equityAttitude = '激进进攻'; }
  else if (kz > 0.3 || jz > 0.2) { equityDir = '顺周期做多'; equityAttitude = '积极配置'; }
  else if (kz < -0.3 && jz < -0.2) { equityDir = '逆周期减仓'; equityAttitude = '防御减配'; }
  else if (kz < -0.3 || jz < -0.2) { equityDir = '谨慎观望'; equityAttitude = '适度减配'; }
  else { equityDir = '震荡均衡'; equityAttitude = '标配持有'; }

  // ── 债券方向 ──
  let bondDir, bondAttitude;
  if (kz < -0.3 && kp >= 3) { bondDir = '强逆周期防御'; bondAttitude = '超配避险'; }
  else if (kz < -0.3 || kp >= 3) { bondDir = '逆周期防御'; bondAttitude = '稳健持有'; }
  else if (kz > 0.3) { bondDir = '顺周期减配'; bondAttitude = '适度减配'; }
  else { bondDir = '均衡配置'; bondAttitude = '标配持有'; }

  // ── 基金方向 ──
  let fundDir, fundAttitude;
  if (kz > 0.3 && jz > 0.2) { fundDir = '顺周期偏股'; fundAttitude = '偏股型为主'; }
  else if (kz < -0.3) { fundDir = '逆周期偏债'; fundAttitude = '偏债型为主'; }
  else { fundDir = '均衡配置'; fundAttitude = '分散风险'; }

  // ── 现金方向 ──
  let cashDir, cashAttitude;
  if (kz < -0.5 || (kp >= 3 && jz < -0.2)) { cashDir = '流动性优先'; cashAttitude = '大幅增持'; }
  else if (kz < -0.3 || kp >= 3) { cashDir = '流动性储备'; cashAttitude = '防御增持'; }
  else if (kz > 0.3) { cashDir = '降低现金'; cashAttitude = '适度释放'; }
  else { cashDir = '适度储备'; cashAttitude = '标配持有'; }

  // ── 细分配比（基于大类占比等比例缩放） ──
  // 权益细分：根据周期强度调整大盘/中小盘/主题比例
  let eqLarge, eqMid, eqTheme;
  if (kz > 0.3) { eqLarge = 35; eqMid = 35; eqTheme = 30; }
  else if (kz < -0.3) { eqLarge = 55; eqMid = 25; eqTheme = 20; }
  else { eqLarge = 45; eqMid = 30; eqTheme = 25; }
  // 归一化到100
  const eqSum = eqLarge + eqMid + eqTheme;
  eqLarge = Math.round(eqLarge / eqSum * 100);
  eqMid = Math.round(eqMid / eqSum * 100);
  eqTheme = 100 - eqLarge - eqMid;

  // 债券细分：根据周期位置调整利率债/信用债/可转债
  let bdRate, bdCredit, bdConv;
  if (kz < -0.3) { bdRate = 50; bdCredit = 30; bdConv = 20; }
  else if (kz > 0.3) { bdRate = 30; bdCredit = 35; bdConv = 35; }
  else { bdRate = 40; bdCredit = 35; bdConv = 25; }
  const bdSum = bdRate + bdCredit + bdConv;
  bdRate = Math.round(bdRate / bdSum * 100);
  bdCredit = Math.round(bdCredit / bdSum * 100);
  bdConv = 100 - bdRate - bdCredit;

  // 基金细分：根据周期偏股/偏债
  let fdIndex, fdMixed, fdQdii;
  if (kz > 0.3) { fdIndex = 45; fdMixed = 30; fdQdii = 25; }
  else if (kz < -0.3) { fdIndex = 30; fdMixed = 40; fdQdii = 30; }
  else { fdIndex = 40; fdMixed = 35; fdQdii = 25; }
  const fdSum = fdIndex + fdMixed + fdQdii;
  fdIndex = Math.round(fdIndex / fdSum * 100);
  fdMixed = Math.round(fdMixed / fdSum * 100);
  fdQdii = 100 - fdIndex - fdMixed;

  // 现金细分
  let csMoney, csShort, csFx;
  if (cash > 20) { csMoney = 50; csShort = 35; csFx = 15; }
  else { csMoney = 60; csShort = 30; csFx = 10; }

  return {
    '权益': { cycleDirection: equityDir, attitude: equityAttitude, subAlloc: { '大盘蓝筹': eqLarge, '中小盘': eqMid, '行业主题': eqTheme } },
    '债券': { cycleDirection: bondDir, attitude: bondAttitude, subAlloc: { '国债/利率债': bdRate, '信用债': bdCredit, '可转债': bdConv } },
    '基金': { cycleDirection: fundDir, attitude: fundAttitude, subAlloc: { '指数基金': fdIndex, '混合基金': fdMixed, 'QDII': fdQdii } },
    '现金': { cycleDirection: cashDir, attitude: cashAttitude, subAlloc: { '货币基金': csMoney, '短期理财': csShort, '外币存款': csFx } },
  };
}

// ── 市场状态计算 ──
function getMarketStatus() {
  const now = new Date();
  const day = now.getDay(); // 0=周日, 6=周六
  const h = now.getHours();
  const m = now.getMinutes();
  const timeVal = h * 60 + m; // 分钟数

  // 周末休市
  if (day === 0 || day === 6) {
    // 检查是否美盘交易中（周六凌晨0-4点仍可能是周五美盘延续）
    if (day === 6 && h < 4) return { label: '美盘交易中', color: '#5B8FA8' };
    return { label: '休市', color: '#888' };
  }

  // A股交易时间: 9:30-11:30, 13:00-15:00
  const aMorningStart = 9 * 60 + 30;
  const aMorningEnd = 11 * 60 + 30;
  const aAfternoonStart = 13 * 60;
  const aAfternoonEnd = 15 * 60;

  // 美盘交易时间(北京时间): 21:30-次日4:00
  const usStart = 21 * 60 + 30;
  const usEnd = 4 * 60; // 次日凌晨4点

  // 判断A股
  if (timeVal >= aMorningStart && timeVal <= aMorningEnd ||
      timeVal >= aAfternoonStart && timeVal <= aAfternoonEnd) {
    return { label: '交易中', color: '#3fb950' };
  }
  // 判断收盘后但美盘未开（15:00-21:30）
  if (timeVal > aAfternoonEnd && timeVal < usStart) {
    return { label: '已收盘', color: '#D4A853' };
  }
  // 判断美盘交易中（21:30-24:00）
  if (timeVal >= usStart) {
    return { label: '美盘交易中', color: '#5B8FA8' };
  }
  // 判断美盘延续（0:00-4:00）
  if (timeVal < usEnd) {
    return { label: '美盘交易中', color: '#5B8FA8' };
  }
  // 早盘前（4:00-9:30）
  return { label: '盘前', color: '#888' };
}

// ── 环形图组件 ──
function AssetDonut({ assetAlloc, assetDetail, collapsed }) {
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);

  useEffect(() => {
    if (!chartRef.current || !assetAlloc?.length || collapsed) return;
    let chart = echarts.getInstanceByDom(chartRef.current);
    if (!chart) chart = echarts.init(chartRef.current, 'df-dark');
    chartInstanceRef.current = chart;

    const option = {
      tooltip: {
        trigger: 'item',
        confine: true,
        position: ['50%', '50%'],
        formatter: (params) => {
          const label = params.name;
          const detail = assetDetail?.[label];
          if (!detail) return `${label}: ${params.value}%`;
          const subAllocLines = Object.entries(detail.subAlloc)
            .map(([k, v]) => `  ${k}  ${v}%`).join('\n');
          return `<div style="font-weight:800;margin-bottom:6px;font-size:var(--fs-lg,18px);color:#D4A853">${label}</div>
            <div style="font-weight:800;font-size:var(--fs-xl,20px);color:#f2d89f;margin-bottom:8px">${params.value}%</div>
            <div style="font-size:var(--fs-base,14px);margin-bottom:3px;font-weight:600">📈 ${detail.cycleDirection}</div>
            <div style="font-size:var(--fs-base,14px);margin-bottom:8px;font-weight:600">🎯 ${detail.attitude}</div>
            <div style="font-size:var(--fs-xs,12px);color:#CBC0B0;border-top:1px solid rgba(212,168,83,0.2);padding-top:6px;margin-top:4px">细分配比</div>
            <div style="font-size:var(--fs-sm,13px);color:#CBC0B0;line-height:1.8">${subAllocLines}</div>`;
        },
        backgroundColor: 'rgba(26,47,42,0.96)',
        borderColor: 'rgba(212,168,83,0.3)',
        textStyle: { color: '#CBC0B0' },
        extraCssText: 'border-radius:10px;padding:16px 20px;min-width:220px;box-shadow:0 8px 32px rgba(0,0,0,0.4);',
      },
      series: [{
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: false,
        label: {
          show: true,
          position: 'outside',
          formatter: '{b}\n{d}%',
          fontSize: 'var(--fs-sm)',
          fontWeight: 700,
          color: '#CBC0B0',
          lineHeight: 18,
        },
        labelLine: {
          show: true,
          length: 10,
          length2: 14,
          lineStyle: { color: 'rgba(212,168,83,0.3)', width: 1 },
        },
        emphasis: {
          label: { show: true, fontSize: 'var(--fs-md)', fontWeight: 800, color: '#D4A853' },
          itemStyle: { shadowBlur: 12, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' },
        },
        data: assetAlloc.map(a => ({
          name: a.label,
          value: a.ratio,
          itemStyle: { color: a.color, borderColor: 'rgba(212,168,83,0.15)', borderWidth: 2 },
        })),
      }],
      graphic: [{
        type: 'text',
        left: 'center',
        top: 'middle',
        style: {
          text: '配置',
          fontSize: 'var(--fs-base)',
          fontWeight: 800,
          fill: '#D4A853',
          textAlign: 'center',
        },
      }],
    };
    chart.setOption(option, { notMerge: true });
    chart.resize();

    // 点击扇区跳转
    chart.on('click', (params) => {
      const nav = ASSET_NAV_MAP[params.name];
      if (nav) {
        const store = useAppStore.getState();
        store.setActiveTab(nav.tab);
        if (nav.tab === 'micro') store.setActiveMicroSub(nav.sub);
        else if (nav.tab === 'global') store.setActiveGlobalSub(nav.sub);
      }
    });

    return () => {
      // 不 dispose，保留实例
    };
  }, [assetAlloc, assetDetail, collapsed]);

  // 组件卸载时 dispose
  useEffect(() => {
    return () => {
      if (chartRef.current) {
        const chart = echarts.getInstanceByDom(chartRef.current);
        if (chart) chart.dispose();
      }
    };
  }, []);

  if (collapsed) return null;

  return <div ref={chartRef} style={{ width: '100%', height: 180 }} />;
}

function SidebarContent() {
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const activeTab = useAppStore((s) => s.activeTab);
  const [policyCnt, setPolicyCnt] = useState('');
  const [policyBriefs, setPolicyBriefs] = useState([]);
  const [cyclePhases, setCyclePhases] = useState([]);
  const [assetAlloc, setAssetAlloc] = useState(null);
  const [assetDetail, setAssetDetail] = useState(null);
  const [marketStatus, setMarketStatus] = useState(getMarketStatus());
  // 移动端侧边栏抽屉状态（默认隐藏，点击汉堡按钮才滑出）
  const [mobileOpen, setMobileOpen] = useState(false);

  // 动态检测移动端：监听窗口尺寸变化，<=768px 视为移动端
  // 使用 useEffect + ResizeObserver 确保响应式切换时状态正确重置
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 768 && mobileOpen) {
        setMobileOpen(false); // 切回宽屏时自动关闭抽屉
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [mobileOpen]);

  // 每分钟更新市场状态
  useEffect(() => {
    const timer = setInterval(() => setMarketStatus(getMarketStatus()), 60000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    async function f() {
      try {
        const [kitRaw, jugRaw, kuzRaw, konRaw] = await Promise.all([
          mcp.call('data_kitchin'),
          mcp.call('data_juglar'),
          mcp.call('data_kuznets'),
          mcp.call('data_kondratiev', { method: 'pca' }),
        ]);
        const parseLast = (raw) => {
          try { const arr = JSON.parse(raw); return arr?.[arr.length - 1] || {}; } catch { return {}; }
        };
        const kit = parseLast(kitRaw);
        const jug = parseLast(jugRaw);
        const kuz = parseLast(kuzRaw);
        const kon = parseLast(konRaw);
        const zDir = (z) => z != null ? (z > 0.2 ? '↑' : z < -0.2 ? '↓' : '→') : '·';
        const zColor = (z) => z != null ? (z > 0.2 ? '#3fb950' : z < -0.2 ? '#f85149' : '#D4A853') : '#888';
        setCyclePhases([
          { name: '基钦', phase: kit.stage_name || kit.phase_name || '—', dir: zDir(kit.composite_z), color: zColor(kit.composite_z) },
          { name: '朱格拉', phase: jug.stage_name || jug.phase_name || '—', dir: zDir(jug.composite_z), color: zColor(jug.composite_z) },
          { name: '库兹涅茨', phase: kuz.stage_name || kuz.phase_name || '—', dir: zDir(kuz.composite_z), color: zColor(kuz.composite_z) },
          { name: '康波', phase: kon.phase_name || kon.global_phase_name || '—', dir: (kon.phase || 0) <= 2 ? '↑' : '↓', color: (kon.phase || 0) <= 2 ? '#3fb950' : '#f85149' },
        ]);
        // 基于周期计算建议资产配置
        let equity = 35, bond = 40, fund = 15, cash = 10;
        const kz = kit.composite_z || 0;
        const jz = jug.composite_z || 0;
        const kp = kon.phase || 0;
        if (kz > 0.3) { equity += 8; bond -= 8; }
        else if (kz < -0.3) { equity -= 8; bond += 5; cash += 3; }
        if (jz > 0.2) { equity += 5; cash -= 5; }
        else if (jz < -0.2) { equity -= 5; cash += 5; }
        if (kp <= 2) { equity += 4; bond -= 4; }
        else { equity -= 6; cash += 3; bond += 3; }
        equity = Math.max(10, Math.min(65, equity));
        bond = Math.max(15, Math.min(65, bond));
        cash = Math.max(5, Math.min(30, cash));
        fund = 100 - equity - bond - cash;
        fund = Math.max(5, fund);
        setAssetAlloc([
          { label: '权益', ratio: equity, color: '#D4A853' },
          { label: '债券', ratio: bond, color: '#5B8FA8' },
          { label: '基金', ratio: fund, color: '#3E6B5C' },
          { label: '现金', ratio: cash, color: '#C49BA5' },
        ]);
        // 基于周期数据动态计算提示卡片详情
        setAssetDetail(computeAssetDetail(kit, jug, kuz, kon, equity, bond, fund, cash));
      } catch(e) { console.error('cycle data error', e); }
      try { const s=await mcp.call('policy_stats'); const m=s.match(/(\d+)\s*篇/); if(m) setPolicyCnt(m[1]); const r=await mcp.call('policy_search',{keyword:'',limit:5}); setPolicyBriefs(r.split('\n').slice(1,4).filter(Boolean)); } catch(e){}
    }
    f();
  }, []);

  const subKeys = SUB_NAV[activeTab] || SUB_NAV.macro;
  const activeSub = useAppStore((s) => s[SUB_GETTERS[activeTab] || 'activeMacroSub']);
  const setActiveSub = useAppStore((s) => s[SUB_SETTERS[activeTab] || 'setActiveMacroSub']);
  const labels = SUB_LABELS[activeTab] || SUB_LABELS.macro;

  const now = new Date();
  const weekDays = ['日','一','二','三','四','五','六'];
  const dateStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
  const weekDay = `星期${weekDays[now.getDay()]}`;
  const timeStr = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

  return (
    <>
      {/* 移动端浮动汉堡按钮 — 固定在屏幕左上角，不跟随侧边栏滑出 */}
      <button
        className="mobile-menu-toggle"
        aria-label="打开菜单"
        onClick={() => setMobileOpen(!mobileOpen)}
      >
        {mobileOpen ? '✕' : '☰'}
      </button>

      {/* 遮罩层 — 展开时点击关闭 */}
      {!sidebarCollapsed && (
        <div
          className={`sidebar-overlay visible${mobileOpen ? ' mobile-active' : ''}`}
          onClick={() => { setMobileOpen(false); toggleSidebar(); }}
        />
      )}

      {/* 侧边栏滑入面板 */}
      <nav
        className={`sidebar-slide-panel ${sidebarCollapsed ? 'collapsed-mode' : 'open'}${mobileOpen ? ' mobile-active' : ''}`}
      >
        {/* 折叠/展开按钮 */}
        <div style={{
          position: 'absolute', top: 24,
          right: sidebarCollapsed ? 'auto' : 8,
          left: sidebarCollapsed ? '50%' : 'auto',
          transform: sidebarCollapsed ? 'translateX(-50%)' : 'none',
          zIndex: 100, cursor: 'pointer',
          width: 32, height: 32, borderRadius: 16,
          background: 'rgba(212,168,83,0.32)', border: '1px solid var(--border-subtle)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 'var(--fs-lg)', color: 'var(--accent-gold)',
        }} onClick={() => {
          if (window.innerWidth <= 768) setMobileOpen(!mobileOpen);
          else toggleSidebar();
        }}>
          {sidebarCollapsed ? '☰' : '‹'}
        </div>

        {/* 标题 */}
        <div style={{ padding: sidebarCollapsed ? '8px 4px' : 'var(--sp-lg) var(--sp-md) var(--sp-sm)', borderBottom: '1px solid var(--border-subtle)', marginBottom: 4, textAlign: sidebarCollapsed ? 'center' : 'left' }}>
          <h1 style={{ fontSize: sidebarCollapsed ? 'var(--fs-base)' : 'var(--fs-2xl)', fontWeight: 800, color: 'var(--accent-gold)', letterSpacing: 1, margin: 0 }}>{sidebarCollapsed ? '◈' : 'Deep Fusion'}</h1>
          {!sidebarCollapsed && <p style={{ fontSize: 'var(--fs-sm)', color: 'var(--text-muted)', marginTop: 6 }}>多维分析系统</p>}
        </div>

      {/* ── 展开态信息区 ── */}
      {!sidebarCollapsed && (
        <>
          {/* 日期/星期/时间/市场状态 */}
          <div style={{ margin: '4px var(--sp-md) var(--sp-sm)', padding: 'var(--sp-md)', background: 'rgba(0,0,0,0.20)', borderRadius: 'var(--radius)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width:8, height:8, background: marketStatus.color, borderRadius:'50%', display:'inline-block', boxShadow: `0 0 6px ${marketStatus.color}44` }} />
              <span style={{ fontSize:'var(--fs-xl)', fontWeight:800, color:'var(--text-primary)' }}>{dateStr}</span>
              <span style={{ fontSize:'var(--fs-sm)', color:'var(--text-muted)', fontWeight:600 }}>{weekDay}</span>
              <span style={{ fontSize:'var(--fs-sm)', color:'var(--text-muted)' }}>{timeStr}</span>
              <span style={{ fontSize:'var(--fs-base)', fontWeight:700, color: marketStatus.color, marginLeft:4 }}>{marketStatus.label}</span>
            </div>
          </div>

          {/* 资产配置环形图 */}
          <div style={{ margin:'4px var(--sp-md) var(--sp-sm)' }}>
            <div style={{ fontSize:'var(--fs-sm)',fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding:'0 4px 6px',display:'flex',alignItems:'center',justifyContent:'space-between' }}>💼 资产配置 <span style={{ fontSize:'var(--fs-2xs)',fontWeight:400,color:'var(--text-muted)' }}>周期动态建议</span></div>
            <div style={{ padding:'var(--sp-md)', background:'rgba(0,0,0,0.2)', borderRadius:'var(--radius)', border:'1px solid var(--border-subtle)' }}>
              <AssetDonut assetAlloc={assetAlloc} assetDetail={assetDetail} collapsed={sidebarCollapsed} />
            </div>
          </div>

          {/* 四周期方向指示器 */}
          <div style={{ margin:'4px var(--sp-md) var(--sp-sm)' }}>
            <div style={{ fontSize:'var(--fs-sm)',fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding:'0 4px 6px' }}>🔄 周期方向</div>
            <div style={{ display:'flex', gap:6 }}>
              {(cyclePhases.length > 0 ? cyclePhases : [
                { name:'基钦', phase:'—', dir:'→', color:'#888' },
                { name:'朱格拉', phase:'—', dir:'→', color:'#888' },
                { name:'库兹涅茨', phase:'—', dir:'→', color:'#888' },
                { name:'康波', phase:'—', dir:'→', color:'#888' },
              ]).map(c => (
                <div key={c.name} style={{
                  flex:1, padding:'var(--sp-xs) 4px', background:'rgba(0,0,0,0.2)',
                  borderRadius:'var(--radius)', border:'1px solid var(--border-subtle)',
                  display:'flex', flexDirection:'column', alignItems:'center', gap:1,
                }}>
                  <div style={{ width:10, height:10, borderRadius:2, background:c.color, boxShadow:`0 0 4px ${c.color}44`, marginBottom:2 }} />
                  <span style={{ fontSize:'var(--fs-2xs)', color:'var(--text-muted)', fontWeight:700, lineHeight:1 }}>{c.name}</span>
                  <span style={{ fontSize:'var(--fs-md)', color:c.color, fontWeight:800, lineHeight:1 }}>{c.dir}</span>
                  <span style={{ fontSize:'var(--fs-2xs)', color:'var(--text-secondary)', textAlign:'center', lineHeight:1.2 }}>{c.phase}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 政策速递 */}
          {activeTab === 'policy' && (
            <div style={{ margin:'4px var(--sp-md) var(--sp-sm)' }}>
              <div style={{ fontSize:'var(--fs-sm)',fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding:'0 4px 6px' }}>📜 政策速递 {policyCnt && `(${policyCnt}篇)`}</div>
              <div style={{ padding:'var(--sp-md)', background:'rgba(0,0,0,0.2)', borderRadius:'var(--radius)', border:'1px solid var(--border-subtle)' }}>
                {policyBriefs.length>0 ? policyBriefs.map((b,i)=>(
                  <div key={i} style={{ fontSize:'var(--fs-xs)',color:'var(--text-secondary)',padding:'3px 0',borderBottom:i<policyBriefs.length-1?'1px solid rgba(212,168,83,0.06)':'none' }}>
                    {b.length>40?b.slice(0,40)+'...':b}
                  </div>
                )) : <div style={{fontSize:'var(--fs-xs)',color:'var(--text-muted)'}}>加载中...</div>}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── 导航区（展开/折叠都显示） ── */}
      <div style={{ fontSize:'var(--fs-sm)',fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding: sidebarCollapsed ? 'var(--sp-sm) var(--sp-xs) 4px' : 'var(--sp-sm) var(--sp-md) 4px', textAlign: sidebarCollapsed ? 'center' : 'left' }}>
        {sidebarCollapsed ? '📍' : '📍 导航'}
      </div>
      <Menu>
        {subKeys.map((key) => (
          <MenuItem
            key={key}
            icon={<span>{labels[key]?.split(' ')[0]}</span>}
            onClick={() => {
              setActiveSub(key);
              if (activeTab === 'macro' || activeTab === 'meso') {
                const el = document.getElementById(key);
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }
            }}
            style={{
              color: activeSub === key ? 'var(--accent-gold)' : 'var(--text-secondary)',
              fontSize: sidebarCollapsed ? 'var(--fs-base)' : 'var(--fs-md)', borderRadius: 8,
              margin: sidebarCollapsed ? '2px 4px' : '2px 8px',
              backgroundColor: activeSub === key ? 'rgba(212,168,83,0.08)' : 'transparent',
            }}
          >
            {sidebarCollapsed ? '' : labels[key]?.split(' ').slice(1).join(' ') || key}
          </MenuItem>
        ))}
      </Menu>
      </nav>
    </>
  );
}

export default function SidebarWrapper() {
  return <SidebarContent />;
}
