-- AI Content Studio durable storage schema
-- Apply ONLY to a dedicated AI Content Studio Supabase project.
-- Never apply this migration to Talbak/Talabatk Delivery.

create extension if not exists pgcrypto;

create table if not exists public.content_studio_jobs (
  id uuid primary key,
  status text not null,
  stage text not null,
  progress integer not null default 0 check (progress between 0 and 100),
  title text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists content_studio_jobs_updated_idx
  on public.content_studio_jobs (updated_at desc);

create table if not exists public.content_studio_references (
  id uuid primary key,
  name text not null,
  kind text not null check (kind in ('image','video')),
  mime_type text not null,
  size_bytes bigint not null default 0,
  sha256 text not null,
  storage_path text,
  analysis_status text not null default 'queued',
  analysis jsonb,
  analysis_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists content_studio_references_sha_idx
  on public.content_studio_references (sha256);

create table if not exists public.content_studio_ideas (
  id uuid primary key default gen_random_uuid(),
  text text not null,
  tags jsonb not null default '[]'::jsonb,
  status text not null default 'inbox',
  score numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.content_studio_brand_profile (
  singleton boolean primary key default true check (singleton),
  profile jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.content_studio_performance (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  platform text,
  views bigint not null default 0,
  likes bigint not null default 0,
  comments bigint not null default 0,
  shares bigint not null default 0,
  duration_seconds numeric,
  hook text,
  content_type text,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.content_studio_trend_snapshots (
  id bigint generated always as identity primary key,
  trend_key text not null,
  geo text not null,
  observed_at timestamptz not null default now(),
  payload jsonb not null
);

create index if not exists content_studio_trend_lookup_idx
  on public.content_studio_trend_snapshots (trend_key, geo, observed_at desc);

create table if not exists public.content_studio_watchlist (
  trend_key text primary key,
  geo text not null,
  trend jsonb not null,
  watched_at timestamptz not null default now()
);

create table if not exists public.content_studio_schedule (
  id uuid primary key default gen_random_uuid(),
  job_id uuid not null,
  platform text not null,
  scheduled_at timestamptz not null,
  title text not null default '',
  notes text not null default '',
  status text not null default 'planned' check (status in ('planned','ready','published','cancelled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists content_studio_schedule_time_idx
  on public.content_studio_schedule (scheduled_at asc);

-- Server-only tables. The backend uses the service-role key and bypasses RLS.
-- No anon/authenticated browser policy is intentionally created.
alter table public.content_studio_jobs enable row level security;
alter table public.content_studio_references enable row level security;
alter table public.content_studio_ideas enable row level security;
alter table public.content_studio_brand_profile enable row level security;
alter table public.content_studio_performance enable row level security;
alter table public.content_studio_trend_snapshots enable row level security;
alter table public.content_studio_watchlist enable row level security;
alter table public.content_studio_schedule enable row level security;

-- Private buckets used by the server-side worker. Service-role access only.
insert into storage.buckets (id, name, public, file_size_limit)
values
  ('content-studio-references', 'content-studio-references', false, 104857600),
  ('content-studio-renders', 'content-studio-renders', false, 536870912),
  ('content-studio-music', 'content-studio-music', false, 83886080),
  ('content-studio-exports', 'content-studio-exports', false, 536870912)
on conflict (id) do nothing;
