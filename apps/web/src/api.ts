export type CreateJobPayload = {
  platform: string;
  aspect_ratio: string;
  duration_seconds: number;
  content_type: string;
  review_each_stage: boolean;
};

export type JobStatus = {
  id: string;
  status: 'queued' | 'running' | 'waiting_review' | 'completed' | 'failed';
  stage: string;
  progress: number;
  message: string;
  input: CreateJobPayload;
};

const workerBaseUrl = (import.meta.env.VITE_WORKER_URL || 'http://localhost:8000').replace(/\/$/, '');

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function createJob(payload: CreateJobPayload): Promise<JobStatus> {
  return parseResponse<JobStatus>(await fetch(`${workerBaseUrl}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }));
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return parseResponse<JobStatus>(await fetch(`${workerBaseUrl}/jobs/${jobId}`));
}

export async function approveJob(jobId: string): Promise<JobStatus> {
  return parseResponse<JobStatus>(await fetch(`${workerBaseUrl}/jobs/${jobId}/approve`, {
    method: 'POST',
  }));
}
