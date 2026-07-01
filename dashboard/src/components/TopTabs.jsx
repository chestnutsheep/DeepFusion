import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../store/index.js';
import { useTheme } from 'next-themes';
import { useEffect } from 'react';

const TABS = [
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
    <div
      style={{
        display: 'flex',
        gap: 4,
        borderBottom: '1px solid var(--border-subtle)',
        paddingBottom: 0,
        marginBottom: 'var(--sp-md)',
      }}
    >
      {TABS.map((tab) => (
        <button
          key={tab.key}
          onClick={() => handleTabClick(tab)}
          style={{
            flex: 1,
            padding: 'var(--sp-md) 0',
            fontSize: 'var(--fs-base)',
            fontWeight: activeTab === tab.key ? 700 : 500,
            color: activeTab === tab.key ? 'var(--accent-gold)' : 'var(--text-secondary)',
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === tab.key ? '2px solid var(--accent-gold)' : '2px solid transparent',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            letterSpacing: 1,
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
