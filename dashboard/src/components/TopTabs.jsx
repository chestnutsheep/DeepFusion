import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../store/index.js';
import { useTheme } from 'next-themes';
import { useEffect } from 'react';

const TABS = [
  { key: 'daily', label: '每日', theme: 'reve', path: '/' },
  { key: 'macro', label: '宏观', theme: 'matin', path: '/macro' },
  { key: 'meso', label: '中观', theme: 'crepuscule', path: '/meso' },
  { key: 'micro', label: '微观', theme: 'eclat', path: '/micro' },
  { key: 'policy', label: '政策', theme: 'reve', path: '/policy' },
  { key: 'global', label: '国际', theme: 'lumiere', path: '/global' },
];

export default function TopTabs() {
  const navigate = useNavigate();
  const activeTab = useAppStore((s) => s.activeTab);
  const setActiveTab = useAppStore((s) => s.setActiveTab);
  const storeTheme = useAppStore((s) => s.theme);
  const setStoreTheme = useAppStore((s) => s.setTheme);
  const { theme, setTheme } = useTheme();

  // store 主题变化时同步到 next-themes
  useEffect(() => {
    if (storeTheme && storeTheme !== theme) setTheme(storeTheme);
  }, [storeTheme]);

  // next-themes 变化（ThemeToggle 点击）时同步回 store
  useEffect(() => {
    if (theme && theme !== storeTheme) setStoreTheme(theme);
  }, [theme]);

  const handleTabClick = (tab) => {
    setActiveTab(tab.key);
    setStoreTheme(tab.theme);
    navigate(tab.path);
  };

  return (
    <div className="top-tab-track">
      {TABS.map((tab) => {
        const active = activeTab === tab.key;
        return (
          <button
            key={tab.key}
            onClick={() => handleTabClick(tab)}
            className={`top-tab${active ? ' active' : ''}`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
