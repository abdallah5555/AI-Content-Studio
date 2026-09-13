# Architecture v0.1

## Components
1. Web client: React + TypeScript + Vite, Arabic-first responsive UI.
2. Database/Auth: Supabase (planned next).
3. Worker: Python FastAPI for long-running media tasks.
4. Media engine: FFmpeg.
5. Captions/timing: Whisper-compatible local pipeline.
6. Provider layer: pluggable LLM/TTS/media providers with ordered failover.

## Pipeline state machine
`idea -> script -> tts -> media -> edit -> effects -> music -> export -> seo -> completed`

Each stage stores status, progress, output metadata, retry count, provider used, and optional approval state.

## Core safety rule
Secrets never ship to the browser bundle. Provider keys are handled server-side and later stored encrypted.
