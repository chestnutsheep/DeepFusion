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
          marginLeft: sidebarCollapsed ? '60px' : '270px',
          position: 'relative',
          zIndex: 2,
          minHeight: '100vh',
          transition: 'margin-left 0.3s ease',
        }}
      >
        <main
          id="main-panel"
          style={{
            maxWidth: '80%',
            margin: '0 auto',
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
