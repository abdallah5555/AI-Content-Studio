export type ReferencePreferences = {
  preserve_style: boolean;
  preserve_colors: boolean;
  preserve_composition: boolean;
  preserve_motion: boolean;
  preserve_character_shape: boolean;
};

export type ReferenceAnalysis = {
  style_summary?: string;
  palette?: string[];
  composition?: string;
  lighting?: string;
  texture_materials?: string;
  character_object_design?: string;
  motion?: string;
  editing_rhythm?: string;
  typography?: string;
  reusable_traits?: string[];
  avoid_copying?: string[];
  generation_guidance?: string;
};

export type UploadedReference = {
  id: string;
  name: string;
  kind: 'image' | 'video';
  mime_type: string;
  size_bytes: number;
  sha256: string;
  analysis_status: 'queued' | 'analyzing' | 'ready' | 'failed';
  analysis?: ReferenceAnalysis | null;
  analysis_error?: string | null;
};

export type CreateJobPayload = {
  platform: string;
  aspect_ratio: string;
  duration_seconds: number;
  content_type: string;
  review_each_stage: boolean;
  idea_prompt: string;
  reference_mode: 'none' | 'adapt_style_to_new_idea';
  reference_ids: string[];
  reference_preferences: ReferencePreferences;
};

export type JobStatus = {
  id: string;
  status: 'queued' | 'running' | 'waiting_review' | 'completed' | 'failed';
  stage: string;
  progress: number;
  message: string;
  input: CreateJobPayload;
  reference_summary?: string | null;
};

const workerBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function uploadReference(file: File): Promise<UploadedReference> {
  const body = new FormData();
  body.append('file', file);
  return parseResponse<UploadedReference>(await fetch(`${workerBaseUrl}/references`, {
    method: 'POST',
    body,
  }));
}

export async function analyzeReference(referenceId: string): Promise<UploadedReference> {
  return parseResponse<UploadedReference>(await fetch(`${workerBaseUrl}/references/${referenceId}/analyze`, {
    method: 'POST',
  }));
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
