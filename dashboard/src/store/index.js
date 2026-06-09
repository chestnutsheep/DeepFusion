import { create } from 'zustand';

export const useAppStore = create((set) => ({
  activeTab: 'macro',
  activeMacroSub: 'kitchin',
  activeMesoSub: 'heatmap',
  activeMicroSub: 'stock',
  activePolicySub: 'stats',
  activeGlobalSub: 'fred',
  historyMode: null,
  theme: 'matin',
  setActiveTab: (tab) => set({ activeTab: tab }),
  setActiveMacroSub: (sub) => set({ activeMacroSub: sub }),
  setActiveMesoSub: (sub) => set({ activeMesoSub: sub }),
  setActiveMicroSub: (sub) => set({ activeMicroSub: sub }),
  setActivePolicySub: (sub) => set({ activePolicySub: sub }),
  setActiveGlobalSub: (sub) => set({ activeGlobalSub: sub }),
  setHistoryMode: (mode) => set({ historyMode: mode }),
  setTheme: (theme) => set({ theme }),
}));
