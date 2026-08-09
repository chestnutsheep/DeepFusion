import {create} from 'zustand';

// ── 市场场景计算（前端本地判定，无需后端接口）──
// 返回数据场景，驱动"首选(实时)/备抵(缓存快照)"自动切换：
//   live    = A股交易中（首选：实时数据 + 允许自动刷新）
//   closed  = A股已收盘（备抵：展示最近交易日收盘快照）
//   offday  = 周末/节假日（备抵：展示最近交易日缓存）
export function computeMarketScene() {
  const now = new Date();
  const day = now.getDay();
  const h = now.getHours();
  const m = now.getMinutes();
  const t = h * 60 + m;
  const aMorning = t >= 9 * 60 + 30 && t <= 11 * 60 + 30;
  const aAfternoon = t >= 13 * 60 && t <= 15 * 60;
  if (day === 0 || day === 6) {
    // 周六凌晨0-4点仍可能是周五美盘延续，但A股休市 → 备抵
    return 'offday';
  }
  if (aMorning || aAfternoon) return 'live';
  return 'closed';
}

export const useAppStore = create((set) => ({
  activeTab: 'macro',
  activeMacroSub: 'kitchin',
  activeMesoSub: 'signals',
  activeMicroSub: 'standby',
  activePolicySub: 'stats',
  activeGlobalSub: 'stress',
  historyMode: null,
  theme: 'matin',
  sidebarCollapsed: false,
  stockSearchKeyword: '',
  fundDetailCode: null,       // 基金详情跳转：基金代码
  fundDetailName: null,       // 金详情跳转：基金名称
  boardAutoRefresh: false,    // 看板自动刷新(60s)
  dataScene: computeMarketScene(),  // 数据场景: live/closed/offday
  setActiveTab: (tab) => set({ activeTab: tab }),
  setActiveMacroSub: (sub) => set({ activeMacroSub: sub }),
  setActiveMesoSub: (sub) => set({ activeMesoSub: sub }),
  setActiveMicroSub: (sub) => set({ activeMicroSub: sub }),
  setActivePolicySub: (sub) => set({ activePolicySub: sub }),
  setActiveGlobalSub: (sub) => set({ activeGlobalSub: sub }),
  setHistoryMode: (mode) => set({ historyMode: mode }),
  setTheme: (theme) => set({ theme }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setStockSearchKeyword: (kw) => set({ stockSearchKeyword: kw }),
  setFundDetail: (code, name) => set({ fundDetailCode: code, fundDetailName: name }),
  clearFundDetail: () => set({ fundDetailCode: null, fundDetailName: null }),
  setBoardAutoRefresh: (v) => set({ boardAutoRefresh: v }),
  setDataScene: (scene) => set({ dataScene: scene }),
}));

// 暴露到 window 便于调试和端到端测试
if (typeof window !== 'undefined') {
  window.__APP_STORE__ = useAppStore;
}

// ── 场景订阅 Hook ──
// 订阅 dataScene，并在场景边界（开盘/收盘/周末）自动刷新判定。
// 前端数据面板用此 hook 决定：live=拉实时(首选) / closed|offday=读缓存快照(备抵)。
import {useEffect} from 'react';
export function useMarketScene() {
  const scene = useAppStore((s) => s.dataScene);
  const setDataScene = useAppStore((s) => s.setDataScene);
  useEffect(() => {
    const refresh = () => setDataScene(computeMarketScene());
    refresh();
    // 每 60s 重算一次场景（覆盖开盘/收盘/周末切换）
    const id = setInterval(refresh, 60000);
    return () => clearInterval(id);
  }, [setDataScene]);
  return scene;
}

// 场景 → 文案/角标
export const SCENE_META = {
  live:   { label: '交易中 · 实时', badge: '实时', color: '#3fb950', primary: true },
  closed: { label: '已收盘 · 收盘快照', badge: '收盘快照', color: '#d29922', primary: false },
  offday: { label: '非交易日 · 缓存', badge: '缓存', color: '#888', primary: false },
};
