import { useState, useEffect } from 'react';
import { Sidebar, Menu, MenuItem, SidebarContext } from 'react-pro-sidebar';
import { useContext } from 'react';
import { useAppStore } from '../store/index.js';
import { mcp } from '../services/mcp.js';

const SUB_NAV = {
  policy: ['stats','list','collect'],
  macro: ['kitchin','juglar','kuznets','kondratiev','coverage'],
  meso: ['heatmap','tree','capital'],
  micro: ['stock','fund','futures','bond','option'],
  global: ['fred','wb','trade'],
};
const SUB_LABELS = {
  policy: { stats:'📊 政策统计', list:'📋 文件列表', collect:'🔄 采集管理' },
  macro: { kitchin:'📉 基钦', juglar:'📈 朱格拉', kuznets:'🏠 库兹涅茨', kondratiev:'🌊 康波', coverage:'📊 宏观覆盖' },
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

  useEffect(() => {
    async function f() {
      try { const k=await mcp.call('data_kitchin'); const arr=JSON.parse(k); if(arr?.length) setPhase(arr[arr.length-1].stage_name||''); } catch(e){}
      try { const s=await mcp.policy.stats(); const m=s.match(/(\d+)\s*篇/); if(m) setPolicyCnt(m[1]); const r=await mcp.policy.search('','',5); setPolicyBriefs(r.split('\n').slice(1,4).filter(Boolean)); } catch(e){}
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
        {!collapsed && <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>宏观·中观·微观·政策·国际</p>}
      </div>

      {!collapsed && (
        <>
          <div style={{ margin: '8px 16px 12px', padding: 14, background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ width:8, height:8, background:'var(--accent-green)', borderRadius:'50%', display:'inline-block' }} />
              <span style={{ fontSize:16, fontWeight:700 }}>{new Date().toLocaleDateString('zh-CN',{year:'numeric',month:'long',day:'numeric'})}</span>
            </div>
            <div style={{ fontSize:11, color:'var(--text-secondary)' }}>{phase ? `基钦相位：${phase}` : '加载中...'}</div>
          </div>

          <div style={{ margin:'0 16px 12px' }}>
            <div style={{ fontSize:12,fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding:'0 4px 8px' }}>💼 资产配置</div>
            <div style={{ padding:14, background:'rgba(0,0,0,0.2)', borderRadius:'var(--radius)', border:'1px solid var(--border-subtle)' }}>
              {[['权益','35%','#D4A853'],['债券','40%','#5B8FA8'],['基金','15%','#3E6B5C'],['现金','10%','#C49BA5']].map(([l,p,c]) => (
                <div key={l} style={{ display:'flex',alignItems:'center',gap:8,marginBottom:4 }}>
                  <span style={{ width:8,height:8,borderRadius:'50%',background:c,display:'inline-block' }} />
                  <span style={{ fontSize:13,flex:1 }}>{l}</span>
                  <span style={{ fontSize:14,fontWeight:700,color:'var(--accent-gold)' }}>{p}</span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ margin:'0 16px 12px' }}>
            <div style={{ fontSize:12,fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding:'0 4px 8px' }}>🔄 基于周期大概方向</div>
            <div style={{ padding:14, background:'rgba(0,0,0,0.2)', borderRadius:'var(--radius)', border:'1px solid var(--border-subtle)' }}>
              {[['基钦','主动补库存','↑','#3fb950'],['朱格拉','弱复苏','→','#D4A853'],['库兹涅茨','L型筑底','↓','#f85149'],['康波','萧条期末','↑','#D4A853']].map(([n,p,d,c]) => (
                <div key={n} style={{ display:'flex',alignItems:'center',gap:8,marginBottom:4 }}>
                  <span style={{ fontSize:11,color:'var(--text-muted)',width:32 }}>{n}</span>
                  <span style={{ fontSize:14,color:c,fontWeight:700 }}>{d}</span>
                  <span style={{ fontSize:12 }}>{p}</span>
                </div>
              ))}
            </div>
          </div>

          {activeTab === 'policy' && (
            <div style={{ margin:'0 16px 12px' }}>
              <div style={{ fontSize:12,fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding:'0 4px 8px' }}>📜 政策速递 {policyCnt && `(${policyCnt}篇)`}</div>
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

      <div style={{ fontSize:12,fontWeight:700,letterSpacing:1,color:'var(--text-secondary)',padding: collapsed ? '8px 10px 4px' : '8px 20px 4px', textAlign: collapsed ? 'center' : 'left' }}>
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
              fontSize: 13, borderRadius: 8, margin: '2px 8px',
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
