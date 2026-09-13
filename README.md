# AI Content Studio

Personal AI-powered social media content production studio.

## Goal
Create complete social videos from idea generation through script, voice, media selection, captions, editing, export, SEO, and scheduled publishing.

## Architecture
- `apps/web` — React + TypeScript + Vite web app / future PWA
- `services/worker` — Python background worker API for media processing, FFmpeg, Whisper, and TTS orchestration
- `docs/PRD.md` — source product requirements

## Phase 1 scope
1. Dashboard and new-video flow
2. Platform / aspect ratio / duration selection
3. Pipeline job model and live progress UI
4. Script provider abstraction with automatic failover
5. Background worker contract
6. Simple video export foundation

## Development
### Web
```bash
npm install
npm run dev
```

### Worker
```bash
cd services/worker
python -m venv .venv
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Security rules
- Never commit API keys.
- Provider secrets belong in server-side environment variables or encrypted user settings.
- Media processing happens outside the browser.
