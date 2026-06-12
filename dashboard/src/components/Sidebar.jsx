import {useContext, useEffect, useState} from 'react';
import {Menu, MenuItem, Sidebar, SidebarContext} from 'react-pro-sidebar';
import {useAppStore} from '../store/index.js';
import {mcp} from '../services/mcp.js';

const SUB_NAV = {
  policy: ['stats','list','collect'],
  macro: ['kitchin','juglar','kuznets','kondratiev','coverage','nesting','gantt'],
  meso: ['heatmap','tree','capital'],
  micro: ['stock','fund','futures','bond','option'],
  global: ['fred','wb','trade'],
};
const SUB_LABELS = {
  policy: { stats:'📊 政策统计', list:'📋 文件列表', collect:'🔄 采集管理' },
  macro: { kitchin:'📉 基钦', juglar:'📈 朱格拉', kuznets:'🏠 库兹涅茨', kondratiev:'🌊 康波', coverage:'📊 宏观覆盖', nesting:'🔗 周期嵌套', gantt:'📅 相位分布' },
  meso: { heatmap:'🔥 热力图', tree:'🌳 行业树', capital:'💰 资金流' },
  micro: { stock:'📈 个股', fund:'📦 基金', futures:'⛽ 期货', bond:'📜 债券', option:'🎯 期权' },
  global: { fred:'🇺🇸 FRED', wb:'🌍 World Bank', trade:'📊 贸易' },
};
const SUB_SETTERS = {
  policy: 'setActivePolicySub', macro: 'setActiveMacroSub', meso: 'setActiveMesoSub',
  micro: 'setActiveMicroSub', global: 'setActiveGlobalSub',
};
const SUB_GETTERS = {
  policy: 'activePolicySub', macro: 'activeMacroSub', meso: 'activeMesoSub',
  micro: 'activeMicroSub', global: 'activeGlobalSub',
};

function SidebarContent() {
  const s = useContext(SidebarContext);
  const collapsed = s?.collapsed ?? false;
  const activeTab = useAppStore((s) => s.activeTab);
  const activeMacroSub = useAppStore((s) => s.activeMacroSub);
  const activeMicroSub = useAppStore((s) => s.activeMicroSub);
  const setActiveMacroSub = useAppStore((s) => s.setActiveMacroSub);
  const setActiveMesoSub = useAppStore((s) => s.setActiveMesoSub);
  const setActiveMicroSub = useAppStore((s) => s.setActiveMicroSub);
  const setActivePolicySub = useAppStore((s) => s.setActivePolicySub);
  const setActiveGlobalSub = useAppStore((s) => s.setActiveGlobalSub);
  const [phase, setPhase] = useState('');
  const [policyCnt, setPolicyCnt] = useState('');
  const [policyBriefs, setPolicyBriefs] = useState([]);
  const [cyclePhases, setCyclePhases] = useState([]);
  const [assetAlloc, setAssetAlloc] = useState(null);

  useEffect(() => {
    async function f() {
      // 并行拉取四周期数据
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
        if (kit.stage_name || kit.phase_name) setPhase(kit.stage_name || kit.phase_name);
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
      // 政策数据
      try { const s=await mcp.call('policy_stats'); const m=s.match(/(\d+)\s*篇/); if(m) setPolicyCnt(m[1]); const r=await mcp.call('policy_search',{keyword:'',limit:5}); setPolicyBriefs(r.split('\n').slice(1,4).filter(Boolean)); } catch(e){}
    }
    f();
  }, []);

  const subKeys = SUB_NAV[activeTab] || SUB_NAV.macro;
  const activeSub = useAppStore((s) => s[SUB_GETTERS[activeTab] || 'activeMacroSub']);
  const setActiveSub = useAppStore((s) => s[SUB_SETTERS[activeTab] || 'setActiveMacroSub']);
  const labels = SUB_LABELS[activeTab] || SUB_LABELS.macro;

  return (
    <Sidebar
      width="var(--nav-width)"
      collapsedWidth="60px"
      backgroundColor="transparent"
      rootStyles={{ borderRight: '1px solid var(--border-subtle)', position: 'fixed', top: 0, left: 0, bottom: 0, zIndex: 100 }}
    >
      <div style={{ padding: collapsed ? '20px 10px' : '24px 20px 20px', borderBottom: '1px solid var(--border-subtle)', marginBottom: 12, textAlign: collapsed ? 'center' : 'left' }}>
        <h1 style={{ fontSize: collapsed ? 14 : 18, fontWeight: 800, color: 'var(--accent-gold)', letterSpacing: 1, margin: 0 }}>{collapsed ? '◈' : '◈ Deep Fusion'}</h1>
        {!collapsed && <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>宏观·中观·微观·政策·国际</p>}
      </div>

      {!collapsed && (
        <>
          <div style={{ margin: '8px 16px 12px', padding: 14, background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ width:8, height:8, background:'var(--accent-green)', borderRadius:'50%', display:'inline-block' }} />
              <span style={{ fontSize:18, fontWeight:700 }}>{new Date().toLocaleDateString('zh-CN',{year:'numeric',month:'long',day:'numeric'})}</span>
            </div>
            <div style={{ fontSize:13, color:'var(--text-secondary)' }}>{phase ? `基钦相位：${phase}` : '加载中...'}</div>
          </div>

          <div style={{ margin:'0 16px 12px' }}>
            <div style={{ fontSize:14,fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding:'0 4px 8px' }}>💼 资产配置 <span style={{ fontSize:9,fontWeight:400,color:'var(--text-muted)' }}>· 基于周期动态建议</span></div>
            <div style={{ padding:14, background:'rgba(0,0,0,0.2)', borderRadius:'var(--radius)', border:'1px solid var(--border-subtle)' }}>
              {(assetAlloc || [{label:'权益',ratio:35,color:'#D4A853'},{label:'债券',ratio:40,color:'#5B8FA8'},{label:'基金',ratio:15,color:'#3E6B5C'},{label:'现金',ratio:10,color:'#C49BA5'}]).map(a => (
                <div key={a.label} style={{ display:'flex',alignItems:'center',gap:8,marginBottom:4 }}>
                  <span style={{ width:8,height:8,borderRadius:'50%',background:a.color,display:'inline-block' }} />
                  <span style={{ fontSize:15,flex:1 }}>{a.label}</span>
                  <span style={{ fontSize:16,fontWeight:700,color:'var(--accent-gold)' }}>{a.ratio}%</span>
                </div>
              ))}
            </div>
          </div>

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

      <div style={{ fontSize:14,fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding: collapsed ? '8px 10px 4px' : '8px 20px 4px', textAlign: collapsed ? 'center' : 'left' }}>
        {collapsed ? '📍' : '📍 导航'}
      </div>
      <Menu>
        {subKeys.map((key) => (
          <MenuItem
            key={key}
            icon={<span>{labels[key]?.split(' ')[0]}</span>}
            onClick={() => {
              setActiveSub(key);
              // 宏观页面使用单页滚动
              if (activeTab === 'macro') {
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
            {collapsed ? '' : labels[key]?.split(' ').slice(1).join(' ') || key}
          </MenuItem>
        ))}
      </Menu>

      {/* 主题切换由 TopTabs 标签自动触发，不暴露手动切换 */}
    </Sidebar>
  );
}

export default function SidebarWrapper() {
  return <SidebarContent />;
}
