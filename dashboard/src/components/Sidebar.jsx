import {useEffect, useRef, useState} from 'react';
import {Menu, MenuItem, Sidebar} from 'react-pro-sidebar';
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
  global: { stress:'⚡ 金融压力', debt:'🏛️ 债务可持续', capital:'💸 赠本流动', bubble:'🫧 泡沫监视', markets:'📊 衍生品市场' },
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

// ── 资产类别提示卡片数据 ──
const ASSET_DETAIL = {
  '权益': { cycleDirection: '顺周期做多', attitude: '积极配置', subAlloc: { '大盘蓝筹': 50, '中小盘': 30, '行业主题': 20 } },
  '债券': { cycleDirection: '逆周期防御', attitude: '稳健持有', subAlloc: { '国债/利率债': 40, '信用债': 35, '可转债': 25 } },
  '基金': { cycleDirection: '均衡配置', attitude: '分散风险', subAlloc: { '指数基金': 40, '混合基金': 35, 'QDII': 25 } },
  '现金': { cycleDirection: '流动性储备', attitude: '防御观望', subAlloc: { '货币基金': 60, '短期理财': 30, '外币存款': 10 } },
};

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
function AssetDonut({ assetAlloc, collapsed }) {
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
        formatter: (params) => {
          const label = params.name;
          const detail = ASSET_DETAIL[label];
          if (!detail) return `${label}: ${params.value}%`;
          const subAllocLines = Object.entries(detail.subAlloc)
            .map(([k, v]) => `  ${k}  ${v}%`).join('\n');
          return `<div style="font-weight:700;margin-bottom:4px;font-size:14px">${label}  ${params.value}%</div>
            <div style="font-size:12px;margin-bottom:2px">📈 顺周期方向：${detail.cycleDirection}</div>
            <div style="font-size:12px;margin-bottom:4px">🎯 投资态度：${detail.attitude}</div>
            <div style="font-size:12px;color:#CBC0B0">细分配比：</div>
            <div style="font-size:11px;color:#CBC0B0;line-height:1.6">${subAllocLines}</div>`;
        },
        backgroundColor: 'rgba(26,47,42,0.95)',
        borderColor: 'rgba(212,168,83,0.2)',
        textStyle: { color: '#CBC0B0' },
        extraCssText: 'border-radius:8px;padding:12px 16px;min-width:180px;',
      },
      series: [{
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: false,
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: 700, color: '#D4A853' },
          itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' },
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
          fontSize: 13,
          fontWeight: 600,
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
  }, [assetAlloc, collapsed]);

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
  const activeMacroSub = useAppStore((s) => s.activeMacroSub);
  const activeMicroSub = useAppStore((s) => s.activeMicroSub);
  const setActiveMacroSub = useAppStore((s) => s.setActiveMacroSub);
  const setActiveMesoSub = useAppStore((s) => s.setActiveMesoSub);
  const setActiveMicroSub = useAppStore((s) => s.setActiveMicroSub);
  const setActivePolicySub = useAppStore((s) => s.setActivePolicySub);
  const setActiveGlobalSub = useAppStore((s) => s.setActiveGlobalSub);
  const [policyCnt, setPolicyCnt] = useState('');
  const [policyBriefs, setPolicyBriefs] = useState([]);
  const [cyclePhases, setCyclePhases] = useState([]);
  const [assetAlloc, setAssetAlloc] = useState(null);
  const [marketStatus, setMarketStatus] = useState(getMarketStatus());

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
    <Sidebar
      width="270px"
      collapsedWidth="60px"
      collapsed={sidebarCollapsed}
      backgroundColor="transparent"
      rootStyles={{ borderRight: '1px solid var(--border-subtle)', position: 'fixed', top: 0, left: 0, bottom: 0, zIndex: 100, transition: 'width 0.3s ease' }}
    >
      {/* 折叠/展开按钮 */}
      <div style={{
        position: 'absolute', bottom: 16, left: sidebarCollapsed ? 10 : 20,
        zIndex: 200, cursor: 'pointer',
        width: 32, height: 32, borderRadius: 16,
        background: 'rgba(212,168,83,0.15)', border: '1px solid var(--border-subtle)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 16, color: 'var(--accent-gold)', transition: 'left 0.3s ease',
      }} onClick={toggleSidebar}>
        {sidebarCollapsed ? '☰' : '✕'}
      </div>

      {/* 标题 */}
      <div style={{ padding: sidebarCollapsed ? '20px 10px' : '24px 20px 20px', borderBottom: '1px solid var(--border-subtle)', marginBottom: 12, textAlign: sidebarCollapsed ? 'center' : 'left' }}>
        <h1 style={{ fontSize: sidebarCollapsed ? 14 : 18, fontWeight: 800, color: 'var(--accent-gold)', letterSpacing: 1, margin: 0 }}>{sidebarCollapsed ? '◈' : '◈ Deep Fusion'}</h1>
        {!sidebarCollapsed && <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>宏观·中观·微观·政策·国际</p>}
      </div>

      {!sidebarCollapsed && (
        <>
          {/* 日期/星期/时间/市场状态 — 替代旧的基钦相位日期区 */}
          <div style={{ margin: '8px 16px 12px', padding: 14, background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{ width:8, height:8, background: marketStatus.color, borderRadius:'50%', display:'inline-block', boxShadow: `0 0 6px ${marketStatus.color}44` }} />
              <span style={{ fontSize:18, fontWeight:700 }}>{dateStr}</span>
            </div>
            <div style={{ fontSize:13, color:'var(--text-secondary)', display:'flex', justifyContent:'space-between' }}>
              <span>{weekDay}</span>
              <span>{timeStr}</span>
            </div>
            <div style={{ fontSize:13, fontWeight:600, color: marketStatus.color, marginTop: 4 }}>
              {marketStatus.label}
            </div>
          </div>

          {/* 资产配置环形图 */}
          <div style={{ margin:'0 16px 12px' }}>
            <div style={{ fontSize:14,fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding:'0 4px 8px' }}>💼 资产配置 <span style={{ fontSize:9,fontWeight:400,color:'var(--text-muted)' }}>· 基于周期动态建议</span></div>
            <div style={{ padding:14, background:'rgba(0,0,0,0.2)', borderRadius:'var(--radius)', border:'1px solid var(--border-subtle)' }}>
              <AssetDonut assetAlloc={assetAlloc} collapsed={sidebarCollapsed} />
            </div>
          </div>

          {/* 四周期方向指示器 */}
          <div style={{ margin:'0 16px 12px' }}>
            <div style={{ fontSize:14,fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding:'0 4px 8px' }}>🔄 基于周期大概方向</div>
            <div style={{ padding:16, background:'rgba(0,0,0,0.2)', borderRadius:'var(--radius)', border:'1px solid var(--border-subtle)' }}>
              {cyclePhases.length > 0 ? cyclePhases.map(c => (
                <div key={c.name} style={{ display:'flex',alignItems:'center',gap:8,marginBottom:4 }}>
                  <span style={{ fontSize:13,color:'var(--text-muted)',width:32 }}>{c.name}</span>
                  <span style={{ fontSize:16,color:c.color,fontWeight:700 }}>{c.dir}</span>
                  <span style={{ fontSize:14 }}>{c.phase}</span>
                </div>
              )) : [['基钦','—','→','#888'],['朱格拉','—','→','#888'],['库兹涅茨','—','→','#888'],['康波','—','→','#888']].map(([n,p,d,c]) => (
                <div key={n} style={{ display:'flex',alignItems:'center',gap:8,marginBottom:4 }}>
                  <span style={{ fontSize:13,color:'var(--text-muted)',width:32 }}>{n}</span>
                  <span style={{ fontSize:16,color:c,fontWeight:700 }}>{d}</span>
                  <span style={{ fontSize:14 }}>{p}</span>
                </div>
              ))}
            </div>
          </div>

          {activeTab === 'policy' && (
            <div style={{ margin:'0 16px 12px' }}>
              <div style={{ fontSize:14,fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding:'0 4px 8px' }}>📜 政策速递 {policyCnt && `(${policyCnt}篇)`}</div>
              <div style={{ padding:14, background:'rgba(0,0,0,0.2)', borderRadius:'var(--radius)', border:'1px solid var(--border-subtle)' }}>
                {policyBriefs.length>0 ? policyBriefs.map((b,i)=>(
                  <div key={i} style={{ fontSize:11,color:'var(--text-secondary)',padding:'3px 0',borderBottom:i<policyBriefs.length-1?'1px solid rgba(212,168,83,0.06)':'none' }}>
                    {b.length>35?b.slice(0,35)+'...':b}
                  </div>
                )) : <div style={{fontSize:11,color:'var(--text-muted)'}}>加载中...</div>}
              </div>
            </div>
          )}
        </>
      )}

      <div style={{ fontSize:14,fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding: sidebarCollapsed ? '8px 10px 4px' : '8px 20px 4px', textAlign: sidebarCollapsed ? 'center' : 'left' }}>
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
              fontSize: 15, borderRadius: 8, margin: '2px 8px',
              backgroundColor: activeSub === key ? 'rgba(212,168,83,0.08)' : 'transparent',
            }}
          >
            {sidebarCollapsed ? '' : labels[key]?.split(' ').slice(1).join(' ') || key}
          </MenuItem>
        ))}
      </Menu>
    </Sidebar>
  );
}

export default function SidebarWrapper() {
  return <SidebarContent />;
}
