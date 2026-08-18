import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { ProSidebarProvider } from 'react-pro-sidebar';
import { queryClient } from './lib/react-query.js';
import MainLayout from './layouts/MainLayout.jsx';
import MacroPage from './pages/MacroPage.jsx';
import MesoPage from './pages/MesoPage.jsx';
import MicroPage from './pages/MicroPage.jsx';
import PolicyPage from './pages/PolicyPage.jsx';
import GlobalPage from './pages/GlobalPage.jsx';
import DailyBoardPage from './pages/DailyBoardPage.jsx';
import VisualTweakPanel from './components/VisualTweakPanel.jsx';
import LogDrawer from './components/LogDrawer.jsx';
import './styles/global.css';

// 后端恢复自动 reload：桌面图标/restart_all.sh 重启服务后，已打开的看板页面
// 通过心跳检测到后端从不可达恢复时，自动刷新到最新代码（避免手动刷/重复开标签）。
// 仅在“断开→恢复”跃迁时 reload 一次，不轮询刷新。
(function watchBackendReload() {
  const PING = '/api/tools/list'; // 经 vite 代理到后端 5173
  let wasUp = true;
  const tick = () => {
    fetch(PING, { method: 'HEAD', cache: 'no-store' })
      .then((r) => {
        const up = r.ok;
        if (!wasUp && up) {
          // 后端刚恢复（服务被重启过）→ 刷新当前页面到最新
          window.location.reload();
        }
        wasUp = up;
      })
      .catch(() => {
        wasUp = false;
      });
  };
  setInterval(tick, 3000);
  tick();
})();

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="data-theme"
        defaultTheme="matin"
        enableSystem={false}
        themes={['matin', 'crepuscule', 'eclat', 'reve', 'lumiere']}
      >
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <ProSidebarProvider>
            <Routes>
              <Route path="/" element={<MainLayout />}>
              <Route index element={<DailyBoardPage />} />
              <Route path="daily" element={<DailyBoardPage />} />
              <Route path="macro" element={<MacroPage />} />
              <Route path="meso" element={<MesoPage />} />
                <Route path="micro" element={<MicroPage />} />
                <Route path="policy" element={<PolicyPage />} />
                <Route path="global" element={<GlobalPage />} />
              </Route>
            </Routes>
          </ProSidebarProvider>
          <VisualTweakPanel />
          <LogDrawer />
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
