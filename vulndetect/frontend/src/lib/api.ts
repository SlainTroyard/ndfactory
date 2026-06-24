const BASE_URL = '/api';

export interface Experiment {
  id: number; name: string; description: string;
  status: string; created_at: string;
}

export interface TrainingMetrics {
  step: number; loss: number | null;
  learning_rate: number | null; gpu_memory_mb: number | null;
  timestamp: string;
}

export async function fetchExperiments(): Promise<Experiment[]> {
  const res = await fetch(`${BASE_URL}/experiments`);
  if (!res.ok) throw new Error('Failed to fetch experiments');
  return res.json();
}

export async function fetchExperiment(id: number): Promise<Experiment> {
  const res = await fetch(`${BASE_URL}/experiments/${id}`);
  if (!res.ok) throw new Error('Experiment not found');
  return res.json();
}

export async function fetchMetrics(id: number, stage?: string): Promise<TrainingMetrics[]> {
  const url = stage ? `${BASE_URL}/experiments/${id}/metrics?stage=${stage}` : `${BASE_URL}/experiments/${id}/metrics`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch metrics');
  return res.json();
}

export async function fetchEvaluations(id: number) {
  const res = await fetch(`${BASE_URL}/experiments/${id}/evaluations`);
  if (!res.ok) throw new Error('Failed to fetch evaluations');
  return res.json();
}

export async function createExperiment(data: { name: string; description: string; config_yaml: string }): Promise<Experiment> {
  const res = await fetch(`${BASE_URL}/experiments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create experiment');
  return res.json();
}

export async function startExperiment(id: number): Promise<void> {
  await fetch(`${BASE_URL}/experiments/${id}/start`, { method: 'POST' });
}
