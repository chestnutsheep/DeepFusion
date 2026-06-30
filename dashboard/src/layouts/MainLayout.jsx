import {Outlet} from 'react-router-dom';
import Sidebar from '../components/Sidebar.jsx';
import TopTabs from '../components/TopTabs.jsx';
import {useAppStore} from '../store/index.js';

export default function MainLayout() {
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed);
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
            padding: '20px 0',
          }}
        >
          <TopTabs />
          <Outlet />
        </main>
      </div>
    </div>
  );
}
