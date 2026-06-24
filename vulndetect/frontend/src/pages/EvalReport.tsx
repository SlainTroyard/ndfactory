import { useState, useEffect } from 'react';
import { fetchExperiments, fetchEvaluations, Experiment } from '../lib/api';

export function EvalReport() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [evaluations, setEvaluations] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchExperiments().then(setExperiments);
  }, []);

  useEffect(() => {
    if (selectedId) {
      setLoading(true);
      fetchEvaluations(selectedId)
        .then(setEvaluations)
        .catch(() => setEvaluations([]))
        .finally(() => setLoading(false));
    }
  }, [selectedId]);

  return (
    <div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1.5rem' }}>Evaluation Report</h1>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        {experiments.map((exp) => (
          <button
            key={exp.id}
            onClick={() => setSelectedId(exp.id)}
            style={{
              padding: '0.375rem 0.75rem', borderRadius: '0.375rem', border: 'none', cursor: 'pointer',
              fontSize: '0.875rem', color: selectedId === exp.id ? '#fff' : '#8b949e',
              background: selectedId === exp.id ? '#a371f7' : '#161b22',
            }}
          >
            {exp.name}
          </button>
        ))}
      </div>

      {loading && <p style={{ color: '#8b949e' }}>Loading...</p>}

      {!loading && evaluations.length > 0 && (
        <div style={{ border: '1px solid #30363d', borderRadius: '0.5rem', background: '#161b22', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left' }}>
                <th style={{ padding: '0.75rem 1rem', color: '#8b949e', fontWeight: 600 }}>Benchmark</th>
                <th style={{ padding: '0.75rem 1rem', color: '#8b949e', fontWeight: 600 }}>Score</th>
                <th style={{ padding: '0.75rem 1rem', color: '#8b949e', fontWeight: 600 }}>Checkpoint Step</th>
              </tr>
            </thead>
            <tbody>
              {evaluations.map((e, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #30363d' }}>
                  <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: '#58a6ff' }}>{e.benchmark}</td>
                  <td style={{ padding: '0.75rem 1rem', fontWeight: 700, color: e.score > 0.7 ? '#3fb950' : '#d2991d' }}>
                    {(e.score * 100).toFixed(1)}%
                  </td>
                  <td style={{ padding: '0.75rem 1rem', color: '#8b949e' }}>Step {e.checkpoint_step}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && evaluations.length === 0 && selectedId && (
        <p style={{ color: '#8b949e' }}>
          No evaluation results yet. Run evaluation against checkpoints to populate this page.
        </p>
      )}

      {!selectedId && (
        <p style={{ color: '#8b949e' }}>Select an experiment above to view its evaluation results.</p>
      )}
    </div>
  );
}
