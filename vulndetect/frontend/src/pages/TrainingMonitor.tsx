import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { fetchExperiments, fetchMetrics, Experiment, TrainingMetrics } from '../lib/api';

export function TrainingMonitor() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [metrics, setMetrics] = useState<TrainingMetrics[]>([]);

  useEffect(() => {
    fetchExperiments().then(setExperiments);
  }, []);

  useEffect(() => {
    if (selectedId) {
      fetchMetrics(selectedId).then(setMetrics);
      const interval = setInterval(() => fetchMetrics(selectedId).then(setMetrics), 3000);
      return () => clearInterval(interval);
    }
  }, [selectedId]);

  return (
    <div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1.5rem' }}>Training Monitor</h1>
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        {experiments.map((exp) => (
          <button
            key={exp.id}
            onClick={() => setSelectedId(exp.id)}
            style={{
              padding: '0.375rem 0.75rem', borderRadius: '0.375rem', border: 'none', cursor: 'pointer',
              fontSize: '0.875rem', color: selectedId === exp.id ? '#fff' : '#8b949e',
              background: selectedId === exp.id ? '#58a6ff' : '#161b22',
            }}
          >
            {exp.name}
          </button>
        ))}
      </div>
      {metrics.length > 0 && (
        <div style={{ border: '1px solid #30363d', borderRadius: '0.5rem', background: '#161b22', padding: '1rem' }}>
          <h3 style={{ fontSize: '0.875rem', marginBottom: '0.75rem' }}>Loss Curve</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={metrics}>
              <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
              <XAxis dataKey="step" stroke="#8b949e" />
              <YAxis stroke="#8b949e" />
              <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d' }} />
              <Line type="monotone" dataKey="loss" stroke="#58a6ff" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {selectedId && metrics.length === 0 && (
        <p style={{ color: '#8b949e' }}>No training metrics yet for this experiment.</p>
      )}
    </div>
  );
}
