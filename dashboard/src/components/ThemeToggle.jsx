import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';

const themes = [
  { value: 'matin', label: '晨晓' },
  { value: 'crepuscule', label: '暮光' },
  { value: 'eclat', label: '晨光' },
  { value: 'reve', label: '梦境' },
  { value: 'lumiere', label: '光韵' },
];

export default function ThemeToggle() {
  const [mounted, setMounted] = useState(false);
  const { theme, setTheme } = useTheme();

  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {themes.map((t) => (
        <button
          key={t.value}
          onClick={() => setTheme(t.value)}
          style={{
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: theme === t.value ? 'var(--accent-gold)' : `var(--bg-deep)`,
            border: theme === t.value ? '2px solid var(--text-primary)' : '1px solid var(--border-subtle)',
            cursor: 'pointer',
            transition: '0.2s',
          }}
          aria-label={t.label}
        />
      ))}
    </div>
  );
}