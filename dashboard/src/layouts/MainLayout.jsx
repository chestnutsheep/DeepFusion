import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar.jsx';
import TopTabs from '../components/TopTabs.jsx';

export default function MainLayout() {
  return (
    <div>
      <Sidebar />
      <div
        className="mn"
        style={{
          marginLeft: 'var(--nav-width)',
          position: 'relative',
          zIndex: 2,
          minHeight: '100vh',
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
