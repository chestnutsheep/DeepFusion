import {create} from 'zustand';

export const useAppStore = create((set) => ({
  activeTab: 'macro',
  activeMacroSub: 'kitchin',
  activeMesoSub: 'signals',
  activeMicroSub: 'stock',
  activePolicySub: 'stats',
  activeGlobalSub: 'stress',
  historyMode: null,
  theme: 'matin',
  sidebarCollapsed: false,
  stockSearchKeyword: '',
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
}));

// 暴露到 window 便于调试和端到端测试
if (typeof window !== 'undefined') {
  window.__APP_STORE__ = useAppStore;
}
