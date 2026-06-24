import { useState, useEffect } from 'react';

interface DatasetInfo {
  name: string;
  path: string;
  samples: number;
  size: string;
}

export function DataManager() {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([
    { name: 'vulndetect', path: 'data/vulndetect', samples: 401, size: '~500 KB' },
  ]);

  return (
    <div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1.5rem' }}>Data Manager</h1>

      {datasets.map((ds) => (
        <div key={ds.name} style={{ border: '1px solid #30363d', borderRadius: '0.5rem', background: '#161b22', padding: '1rem', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#58a6ff', margin: 0 }}>{ds.name}</h3>
            <span style={{ fontSize: '0.75rem', padding: '0.125rem 0.5rem', borderRadius: '999px', background: '#23863620', color: '#3fb950', border: '1px solid #23863640' }}>
              Ready
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.8rem', color: '#8b949e' }}>
            <div>Path: <span style={{ color: '#e6edf3', fontFamily: 'monospace' }}>{ds.path}</span></div>
            <div>Samples: <span style={{ color: '#e6edf3' }}>{ds.samples} (train: 360 + val: 41)</span></div>
            <div>Format: <span style={{ color: '#e6edf3' }}>OpenRLHF conversation (JSONL)</span></div>
            <div>Size: <span style={{ color: '#e6edf3' }}>{ds.size}</span></div>
          </div>
        </div>
      ))}

      <div style={{ border: '1px solid #30363d', borderRadius: '0.5rem', background: '#161b22', padding: '1rem' }}>
        <h3 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem' }}>Collect More Data</h3>
        <code style={{ display: 'block', padding: '0.5rem', background: '#0d1117', borderRadius: '0.25rem', color: '#58a6ff', fontSize: '0.8rem', fontFamily: 'monospace' }}>
          python -m vulndetect.data_pipeline.pipeline --output-dir data/vulndetect --days-back 30 --nvd-pages 10
        </code>
      </div>
    </div>
  );
}
