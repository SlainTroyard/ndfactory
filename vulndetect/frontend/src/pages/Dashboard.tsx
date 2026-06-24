import { useState, useEffect } from 'react';
import { fetchExperiments, Experiment } from '../lib/api';

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: '#3fb950', paused: '#d2991d', completed: '#58a6ff',
    failed: '#f85149', created: '#8b949e',
  };
  return (
    <span style={{
      background: colors[status] || '#8b949e', color: '#fff',
      borderRadius: '999px', padding: '0.125rem 0.5rem', fontSize: '0.75rem',
      display: 'inline-block',
    }}>
      {status}
    </span>
  );
}

function Card({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div style={{ border: '1px solid #30363d', borderRadius: '0.5rem', background: '#161b22', padding: '1rem' }}>
      {title && <h3 style={{ margin: '0 0 0.75rem 0', fontSize: '0.875rem', color: '#e6edf3' }}>{title}</h3>}
      {children}
    </div>
  );
}

export function Dashboard() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchExperiments().then(setExperiments).catch(console.error).finally(() => setLoading(false));
    const interval = setInterval(() => fetchExperiments().then(setExperiments).catch(() => {}), 5000);
    return () => clearInterval(interval);
  }, []);

  const running = experiments.filter((e) => e.status === 'running').length;
  const completed = experiments.filter((e) => e.status === 'completed').length;

  return (
    <div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1.5rem' }}>Dashboard</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
        <Card>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: '#58a6ff' }}>{experiments.length}</div>
          <div style={{ fontSize: '0.875rem', color: '#8b949e' }}>Total Experiments</div>
        </Card>
        <Card>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: '#3fb950' }}>{running}</div>
          <div style={{ fontSize: '0.875rem', color: '#8b949e' }}>Running</div>
        </Card>
        <Card>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: '#a371f7' }}>{completed}</div>
          <div style={{ fontSize: '0.875rem', color: '#8b949e' }}>Completed</div>
        </Card>
      </div>
      <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '1rem' }}>Recent Experiments</h2>
      {loading ? (
        <p style={{ color: '#8b949e' }}>Loading...</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
          {experiments.map((exp) => (
            <Card key={exp.id} title={exp.name}>
              <StatusBadge status={exp.status} />
              <p style={{ fontSize: '0.75rem', color: '#8b949e', marginTop: '0.5rem' }}>{exp.description || 'No description'}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
