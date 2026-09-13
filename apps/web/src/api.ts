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
  created_at?: string;
  updated_at?: string;
};

export type JobSummary = {
  id: string;
  status: JobStatus['status'];
  stage: string;
  progress: number;
  title?: string | null;
  created_at: string;
  updated_at: string;
};

export type TrendItem = {
  key: string;
  title: string;
  geo: string;
  source: string;
  traffic: number;
  traffic_label?: string;
  published_at?: string | null;
  age_hours: number;
  velocity_score: number;
  saturation_score: number;
  score: number;
  lifecycle: 'early' | 'rising' | 'strong' | 'saturated' | 'cooling' | string;
  related_news?: { title: string; url?: string | null }[];
  source_url?: string;
  watched_at?: string;
};

export type IntelligenceResult = {
  provider?: string;
  content: Record<string, unknown>;
  failover_log?: string[];
};

export type IdeaInboxItem = {
  id: string;
  text: string;
  tags: string[];
  status: string;
  score?: number | null;
  created_at: string;
  updated_at: string;
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
  return parseResponse<UploadedReference>(await fetch(`${workerBaseUrl}/references/${referenceId}/analyze`, { method: 'POST' }));
}

export async function uploadReference(file: File): Promise<UploadedReference> {
  const body = new FormData();
  body.append('file', file);
  const uploaded = await parseResponse<UploadedReference>(await fetch(`${workerBaseUrl}/references`, { method: 'POST', body }));
  try {
    return await analyzeReference(uploaded.id);
  } catch (error) {
    return { ...uploaded, analysis_status: 'failed', analysis_error: error instanceof Error ? error.message : 'Reference analysis failed' };
  }
}

export async function createJob(payload: CreateJobPayload): Promise<JobStatus> {
  return parseResponse<JobStatus>(await fetch(`${workerBaseUrl}/jobs`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  }));
}

export async function listJobs(limit = 50): Promise<JobSummary[]> {
  const result = await parseResponse<{ jobs: JobSummary[] }>(await fetch(`${workerBaseUrl}/jobs?limit=${Math.max(1, Math.min(limit, 200))}`));
  return result.jobs;
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return parseResponse<JobStatus>(await fetch(`${workerBaseUrl}/jobs/${jobId}`));
}

export async function deleteJob(jobId: string): Promise<void> {
  await parseResponse<{ deleted: boolean }>(await fetch(`${workerBaseUrl}/jobs/${jobId}`, { method: 'DELETE' }));
}

export async function approveJob(jobId: string): Promise<JobStatus> {
  return parseResponse<JobStatus>(await fetch(`${workerBaseUrl}/jobs/${jobId}/approve`, { method: 'POST' }));
}

export async function regenerateJobStage(jobId: string, stage: string): Promise<JobStatus> {
  return parseResponse<JobStatus>(await fetch(`${workerBaseUrl}/jobs/${jobId}/stages/${stage}/regenerate`, { method: 'POST' }));
}

export async function editJobStage(jobId: string, stage: string, content: Record<string, unknown>): Promise<JobStatus> {
  return parseResponse<JobStatus>(await fetch(`${workerBaseUrl}/jobs/${jobId}/stages/${stage}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }),
  }));
}

export async function getTrends(geo = 'EG', limit = 30): Promise<TrendItem[]> {
  const result = await parseResponse<{ items: TrendItem[] }>(await fetch(`${workerBaseUrl}/intelligence/trends?geo=${encodeURIComponent(geo)}&limit=${limit}`));
  return result.items;
}

export async function refreshTrends(geo = 'EG', limit = 30): Promise<TrendItem[]> {
  const result = await parseResponse<{ items: TrendItem[] }>(await fetch(`${workerBaseUrl}/intelligence/trends/refresh?geo=${encodeURIComponent(geo)}&limit=${limit}`, { method: 'POST' }));
  return result.items;
}

export async function listTrendWatchlist(): Promise<TrendItem[]> {
  const result = await parseResponse<{ items: TrendItem[] }>(await fetch(`${workerBaseUrl}/intelligence/watchlist`));
  return result.items;
}

export async function watchTrend(trend: TrendItem, geo = 'EG'): Promise<void> {
  await parseResponse(await fetch(`${workerBaseUrl}/intelligence/watchlist`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ trend, geo }),
  }));
}

export async function unwatchTrend(key: string): Promise<void> {
  await parseResponse(await fetch(`${workerBaseUrl}/intelligence/watchlist/${encodeURIComponent(key)}`, { method: 'DELETE' }));
}

export async function runIntelligenceTool(
  tool: string,
  input: string,
  options: { context?: Record<string, unknown>; language?: string; platform?: string; audience?: string } = {},
): Promise<IntelligenceResult> {
  return parseResponse<IntelligenceResult>(await fetch(`${workerBaseUrl}/intelligence/generate/${tool}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input, context: options.context || {}, language: options.language || 'ar-EG', platform: options.platform || null, audience: options.audience || null }),
  }));
}

export async function listIdeaInbox(): Promise<IdeaInboxItem[]> {
  const result = await parseResponse<{ ideas: IdeaInboxItem[] }>(await fetch(`${workerBaseUrl}/intelligence/inbox`));
  return result.ideas;
}

export async function addIdeaInbox(text: string, tags: string[] = []): Promise<IdeaInboxItem> {
  const result = await parseResponse<{ idea: IdeaInboxItem }>(await fetch(`${workerBaseUrl}/intelligence/inbox`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, tags }),
  }));
  return result.idea;
}

export async function deleteIdeaInbox(id: string): Promise<void> {
  await parseResponse(await fetch(`${workerBaseUrl}/intelligence/inbox/${encodeURIComponent(id)}`, { method: 'DELETE' }));
}

export async function getBrandProfile(): Promise<Record<string, unknown>> {
  const result = await parseResponse<{ profile: Record<string, unknown> }>(await fetch(`${workerBaseUrl}/intelligence/brand`));
  return result.profile;
}

export async function saveBrandProfile(profile: Record<string, unknown>): Promise<void> {
  await parseResponse(await fetch(`${workerBaseUrl}/intelligence/brand`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile }),
  }));
}

export async function recordPerformance(payload: Record<string, unknown>): Promise<void> {
  await parseResponse(await fetch(`${workerBaseUrl}/intelligence/performance`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  }));
}
