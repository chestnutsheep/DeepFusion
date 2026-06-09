import { describe, it, expect } from 'vitest';
import { useAppStore } from '../src/store';

// 每次测试前重置 store 到初始状态
beforeEach(() => {
  useAppStore.setState({
    activeTab: 'macro',
    activeMacroSub: 'kitchin',
    activeMesoSub: 'heatmap',
    activeMicroSub: 'stock',
    activePolicySub: 'stats',
    activeGlobalSub: 'fred',
    historyMode: null,
    theme: 'matin',
  });
});

describe('useAppStore', () => {
  it('初始值正确', () => {
    const s = useAppStore.getState();
    expect(s.activeTab).toBe('macro');
    expect(s.activeMacroSub).toBe('kitchin');
    expect(s.activeMesoSub).toBe('heatmap');
    expect(s.activeMicroSub).toBe('stock');
    expect(s.activePolicySub).toBe('stats');
    expect(s.activeGlobalSub).toBe('fred');
    expect(s.historyMode).toBeNull();
    expect(s.theme).toBe('matin');
  });

  it('setActiveTab 切换主标签', () => {
    useAppStore.getState().setActiveTab('policy');
    expect(useAppStore.getState().activeTab).toBe('policy');
    // 切换后其他字段不变
    expect(useAppStore.getState().activeMacroSub).toBe('kitchin');
  });

  it('setActiveMacroSub 切换宏端子标签', () => {
    useAppStore.getState().setActiveMacroSub('juglar');
    expect(useAppStore.getState().activeMacroSub).toBe('juglar');
  });

  it('各子标签独立互不影响', () => {
    const s = useAppStore.getState();
    s.setActiveTab('micro');
    s.setActiveMicroSub('futures');
    expect(useAppStore.getState().activeMicroSub).toBe('futures');
    expect(useAppStore.getState().activeMacroSub).toBe('kitchin'); // 不受影响
  });

  it('setHistoryMode', () => {
    useAppStore.getState().setHistoryMode('compare');
    expect(useAppStore.getState().historyMode).toBe('compare');
  });

  it('setTheme', () => {
    useAppStore.getState().setTheme('crepuscule');
    expect(useAppStore.getState().theme).toBe('crepuscule');
  });
});
