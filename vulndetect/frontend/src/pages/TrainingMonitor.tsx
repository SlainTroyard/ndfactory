import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { fetchExperiments, fetchMetrics, Experiment } from '../lib/api';

const STAGES = [
  { key: '', label: 'All', color: '#8b949e' },
  { key: 'sft', label: 'SFT', color: '#58a6ff' },
  { key: 'dpo', label: 'DPO', color: '#3fb950' },
  { key: 'ppo', label: 'PPO', color: '#f0883e' },
];

export function TrainingMonitor() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [stage, setStage] = useState('');
  const [allMetrics, setAllMetrics] = useState<Record<string, Array<{step: number; loss: number; stage: string}>>>({});

  useEffect(() => {
    fetchExperiments().then(setExperiments);
  }, []);

  useEffect(() => {
    if (selectedId) {
      fetchMetrics(selectedId, stage || undefined).then(data => {
        const sft = data.filter((m: any) => (m.stage || 'sft') === 'sft');
        const dpo = data.filter((m: any) => m.stage === 'dpo');
        setAllMetrics({ sft, dpo });
      });
      const interval = setInterval(() => {
        fetchMetrics(selectedId, stage || undefined).then(data => {
          const sft = data.filter((m: any) => (m.stage || 'sft') === 'sft');
          const dpo = data.filter((m: any) => m.stage === 'dpo');
          setAllMetrics({ sft, dpo });
        });
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [selectedId, stage]);

  const hasData = allMetrics.sft?.length > 0 || allMetrics.dpo?.length > 0;

  return (
    <div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1.5rem' }}>Training Monitor</h1>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
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

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        {STAGES.map((s) => (
          <button
            key={s.key}
            onClick={() => setStage(s.key)}
            style={{
              padding: '0.25rem 0.75rem', borderRadius: '999px', border: `1px solid ${s.color}40`,
              cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600,
              color: stage === s.key ? '#fff' : s.color,
              background: stage === s.key ? s.color : 'transparent',
            }}
          >
            {s.label}
          </button>
        ))}
      </div>

      {hasData && (
        <div style={{ border: '1px solid #30363d', borderRadius: '0.5rem', background: '#161b22', padding: '1rem' }}>
          <h3 style={{ fontSize: '0.875rem', marginBottom: '0.75rem' }}>
            Loss Curves {stage ? `— ${STAGES.find(s => s.key === stage)?.label}` : '— All Stages'}
          </h3>
          <ResponsiveContainer width="100%" height={350}>
            <LineChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
              <XAxis dataKey="step" stroke="#8b949e" allowDuplicatedCategory={false} />
              <YAxis stroke="#8b949e" />
              <Tooltip contentStyle={{ background: '#161b22', border: '1px solid #30363d' }} />
              <Legend />
              {allMetrics.sft?.length > 0 && (!stage || stage === 'sft') && (
                <Line name="SFT" data={allMetrics.sft} dataKey="loss" stroke="#58a6ff" dot={false} strokeWidth={2} />
              )}
              {allMetrics.dpo?.length > 0 && (!stage || stage === 'dpo') && (
                <Line name="DPO" data={allMetrics.dpo} dataKey="loss" stroke="#3fb950" dot={false} strokeWidth={2} />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {selectedId && !hasData && (
        <p style={{ color: '#8b949e' }}>No training metrics yet. Start training to see curves.</p>
      )}
    </div>
  );
}
