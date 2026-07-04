import {Outlet, useLocation} from 'react-router-dom';
import {useEffect} from 'react';
import Sidebar from '../components/Sidebar.jsx';
import TopTabs from '../components/TopTabs.jsx';
import {useAppStore} from '../store/index.js';

// 路由路径 → store activeTab 映射
const PATH_TO_TAB = {
  '/macro': 'macro',
  '/meso': 'meso',
  '/micro': 'micro',
  '/policy': 'policy',
  '/global': 'global',
};

export default function MainLayout() {
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed);
  const activeTab = useAppStore((s) => s.activeTab);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const location = useLocation();

  // 路由变化时同步 store.activeTab（处理直接 URL 访问/刷新的情况）
  useEffect(() => {
    const path = location.pathname;
    const tab = PATH_TO_TAB[path] || (path === '/' ? 'macro' : null);
    if (tab && tab !== activeTab) setActiveTab(tab);
  }, [location.pathname, activeTab, setActiveTab]);

  return (
    <div>
      <Sidebar />
      <div
        className="mn"
        style={{
          marginLeft: sidebarCollapsed ? '70px' : 'clamp(240px, 24vw, 400px)',
          minHeight: '100vh',
          transition: 'margin-left var(--sidebar-slide-duration) cubic-bezier(0.22, 1, 0.36, 1)',
        }}
      >
        <main
          id="main-panel"
          style={{
            padding: 'var(--sp-xl) 0',
          }}
        >
          <TopTabs />
          <Outlet />
        </main>
      </div>
    </div>
  );
}
