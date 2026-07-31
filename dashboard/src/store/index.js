import {create} from 'zustand';

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
}));

// 暴露到 window 便于调试和端到端测试
if (typeof window !== 'undefined') {
  window.__APP_STORE__ = useAppStore;
}
