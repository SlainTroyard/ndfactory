import { ReactNode } from 'react';

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: '◉' },
  { path: '/training', label: 'Training', icon: '⚡' },
  { path: '/evaluation', label: 'Evaluation', icon: '📊' },
  { path: '/data', label: 'Data', icon: '📦' },
  { path: '/playground', label: 'Playground', icon: '💬' },
];

export function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = window.location.pathname;
  return (
    <div style={{ display: 'flex', height: '100vh', background: '#0d1117' }}>
      <aside style={{ width: 224, borderRight: '1px solid #30363d', background: '#161b22', padding: '1rem' }}>
        <div style={{ marginBottom: '1.5rem', fontSize: '1.125rem', fontWeight: 700, color: '#58a6ff' }}>
          VulnDetect
        </div>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {NAV_ITEMS.map((item) => (
            <a
              key={item.path}
              href={item.path}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                padding: '0.5rem 0.75rem', borderRadius: '0.375rem',
                fontSize: '0.875rem', textDecoration: 'none',
                color: pathname === item.path ? '#58a6ff' : '#8b949e',
                background: pathname === item.path ? '#1f2937' : 'transparent',
              }}
            >
              <span>{item.icon}</span>
              {item.label}
            </a>
          ))}
        </nav>
      </aside>
      <main style={{ flex: 1, overflow: 'auto', padding: '1.5rem' }}>
        {children}
      </main>
    </div>
  );
}
