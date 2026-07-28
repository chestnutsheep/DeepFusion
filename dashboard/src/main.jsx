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
import './styles/global.css';

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
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
