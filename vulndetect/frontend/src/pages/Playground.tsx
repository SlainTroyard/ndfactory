import { useState } from 'react';

export function Playground() {
  const [input, setInput] = useState('');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);
  const checkpoint = 'experiments/qwen3b-sft-v1/checkpoints/final';

  const handleSend = async () => {
    if (!input.trim()) return;
    setLoading(true);
    try {
      const res = await fetch('/api/inference/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ checkpoint_path: checkpoint, prompt: input }),
      });
      const data = await res.json();
      setResponse(data.text);
    } catch (e) {
      setResponse(`Error: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1.5rem' }}>Model Playground</h1>
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ fontSize: '0.75rem', color: '#8b949e', display: 'block', marginBottom: '0.25rem' }}>Checkpoint</label>
        <input value={checkpoint} readOnly style={{
          width: '100%', padding: '0.5rem 0.75rem', borderRadius: '0.375rem',
          border: '1px solid #30363d', background: '#0d1117', color: '#e6edf3', fontFamily: 'monospace', fontSize: '0.875rem',
        }} />
      </div>
      <div style={{ border: '1px solid #30363d', borderRadius: '0.5rem', background: '#161b22', padding: '1rem', marginBottom: '1rem' }}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Paste code or ask a security question..."
          style={{
            width: '100%', height: 192, resize: 'vertical', padding: '0.75rem',
            borderRadius: '0.375rem', border: '1px solid #30363d', background: '#0d1117',
            color: '#e6edf3', fontFamily: 'monospace', fontSize: '0.875rem',
          }}
        />
        <button onClick={handleSend} disabled={loading} style={{
          marginTop: '0.75rem', padding: '0.5rem 1rem', borderRadius: '0.375rem', border: 'none',
          cursor: 'pointer', fontSize: '0.875rem', fontWeight: 500, color: '#fff', background: '#238636',
          opacity: loading ? 0.5 : 1,
        }}>
          {loading ? 'Analyzing...' : 'Send'}
        </button>
      </div>
      {response && (
        <div style={{ border: '1px solid #30363d', borderRadius: '0.5rem', background: '#161b22', padding: '1rem' }}>
          <h3 style={{ fontSize: '0.875rem', marginBottom: '0.75rem' }}>Response</h3>
          <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.875rem', color: '#e6edf3', margin: 0 }}>
            {response}
          </pre>
        </div>
      )}
    </div>
  );
}
