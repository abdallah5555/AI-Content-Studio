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
  tts_voice?: string;
  tts_rate?: string;
  music_volume?: number;
};

export type StageGenerationResult = {
  provider?: string;
  failover_log?: string[];
  content?: Record<string, unknown>;
  status?: string;
  message?: string;
  audio_id?: string;
  audio_url?: string;
  audio_path?: string;
  voice?: string;
  rate?: string;
  format?: string;
  size_bytes?: number;
  text_length?: number;
  video_url?: string;
  video_path?: string;
  download_url?: string;
  filename?: string;
  warning?: string | null;
  music_applied?: boolean;
  track?: string;
  captions_count?: number;
  captions_burned?: boolean;
  fade_applied?: boolean;
  [key: string]: unknown;
};

export type JobStatus = {
  id: string;
  status: 'queued' | 'running' | 'waiting_review' | 'completed' | 'failed';
  stage: string;
  progress: number;
  message: string;
  input: CreateJobPayload;
  reference_summary?: string | null;
  outputs?: Record<string, StageGenerationResult>;
  stage_output?: StageGenerationResult | null;
  active_provider?: string | null;
  provider_failover_log?: string[];
  error?: string | null;
};

const workerBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

export function resolveWorkerUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${workerBaseUrl}${path.startsWith('/') ? '' : '/'}${path}`;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function analyzeReference(referenceId: string): Promise<UploadedReference> {
  return parseResponse<UploadedReference>(await fetch(`${workerBaseUrl}/references/${referenceId}/analyze`, {
    method: 'POST',
  }));
}

export async function uploadReference(file: File): Promise<UploadedReference> {
  const body = new FormData();
  body.append('file', file);
  const uploaded = await parseResponse<UploadedReference>(await fetch(`${workerBaseUrl}/references`, {
    method: 'POST',
    body,
  }));

  try {
    return await analyzeReference(uploaded.id);
  } catch (error) {
    return {
      ...uploaded,
      analysis_status: 'failed',
      analysis_error: error instanceof Error ? error.message : 'Reference analysis failed',
    };
  }
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

export async function regenerateJobStage(jobId: string, stage: string): Promise<JobStatus> {
  return parseResponse<JobStatus>(await fetch(`${workerBaseUrl}/jobs/${jobId}/stages/${stage}/regenerate`, {
    method: 'POST',
  }));
}

export async function editJobStage(jobId: string, stage: string, content: Record<string, unknown>): Promise<JobStatus> {
  return parseResponse<JobStatus>(await fetch(`${workerBaseUrl}/jobs/${jobId}/stages/${stage}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  }));
}
