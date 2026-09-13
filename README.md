# AI Content Studio

Personal AI-powered social media content production studio.

## Goal
Create complete social videos from idea discovery through script, voice, media selection, captions, editing, export, SEO, project history and future scheduled publishing.

## Current architecture
- `apps/web` — React + TypeScript + Vite web app / future PWA
- `services/worker` — FastAPI worker for AI orchestration and media processing
- SQLite — durable jobs, references, Trend Radar snapshots, watchlist, Idea Inbox, Brand DNA and performance memory
- FFmpeg — video normalization, montage, captions/effects, audio mixing, MP4 output
- AI text failover — Gemini → Groq → OpenRouter
- Visual reference analysis — Gemini multimodal
- TTS — Edge TTS with Egyptian Arabic voices
- Stock video failover — Pexels → Pixabay
- Local royalty-free music library — optional uploaded tracks mixed at low volume

## Content Intelligence Suite
The Dashboard now includes a **Content Intelligence** workspace before the video pipeline.

### Trend Radar
- free-first live trend discovery with no paid API required for the core radar
- Google Trends public trending feed as the primary live signal
- region presets for Egypt, Saudi Arabia, UAE and US/global discovery
- opportunity score from 0–100
- freshness, velocity, saturation and trend lifecycle states
- lifecycle states: early, rising, strong, saturated and cooling
- persistent trend snapshots so repeated refreshes can compare movement over time
- persistent Trend Watchlist
- one-click **Trend Remix** that turns the cultural/trend mechanic into original content ideas instead of copying an existing video

TikTok Creative Center remains a free public inspiration source, but the production backend does not depend on undocumented scraping or a paid TikTok trend API.

### Intelligence tools
The same provider failover layer powers:
- **Content Gap Finder**
- **Viral Hook Lab**
- **Content Series Generator**
- **Repurpose Engine**
- **Evergreen Radar**
- **Audience Persona Mode**
- **Content Calendar AI**
- **Idea Score**
- **A/B Version Generator**
- **Comment-to-Content**
- **Research Mode** using free GDELT article discovery as source context
- **Winning Pattern Memory**
- **Trend Remix**

### Idea Inbox
Quick ideas can be saved to SQLite, reopened later, scored with Idea Score, or sent directly to the video creator.

### Brand DNA
A persistent Brand DNA profile stores voice, tone, visual traits, hook patterns, CTAs, content pillars and do/avoid rules. Intelligence tools can use that saved profile as context.

### Winning Pattern Memory
The creator can record real performance numbers for published content (views, likes, comments, shares and hook). The Winning Patterns tool analyzes only the stored performance data and suggests repeatable patterns and next tests.

## Implemented video pipeline
1. **Idea** — generates an original concept from the user's request and optional visual reference.
2. **Script** — generates title, hook, narration, CTA and a timed scene plan.
3. **TTS** — converts narration to MP3 with Egyptian Arabic voice selection.
4. **Media** — searches Pexels/Pixabay for each scene with provider failover.
5. **Edit** — downloads selected clips, crops/scales them to the target aspect ratio, concatenates them and adds narration.
6. **Effects** — burns timed captions where supported and adds basic fade effects.
7. **Music** — mixes an optional royalty-free track from the local music library at voice-safe volume; skips safely if the library is empty.
8. **Export** — creates the final downloadable MP4.
9. **SEO** — generates upload-ready title, description, hashtags and keywords.

Content Intelligence results can be sent directly into the Idea stage of this pipeline.

## Reference-to-Idea mode
The creator can upload an AI-generated image or video as a visual reference and then describe a completely different idea. The system analyzes observable visual traits such as style, color palette, composition, motion and object/character design, then uses only the selected reusable traits as guidance for the new work instead of copying the original content literally.

Reference metadata and completed visual analysis are persisted in SQLite so a worker restart does not erase the project's reference context. Uploaded media itself remains in runtime storage and is never committed to GitHub.

## Review mode
When **Review each stage** is enabled, the pipeline pauses after each stage. The user can approve and continue, regenerate the current stage, or manually edit JSON results for idea, script and SEO stages.

Changing an earlier stage invalidates later outputs automatically so downstream video assets are not silently based on stale content.

## Project library and persistence
Jobs are checkpointed to SQLite after important state changes and after each pipeline stage. The Dashboard's **Idea Library** opens a real project-history view where previous jobs can be reopened or deleted.

If the worker restarts while a job is actively running, completed outputs remain stored and that job is marked as interrupted instead of disappearing. The interrupted stage can then be regenerated.

Default local data files:
- `data/ai_content_studio.db` — jobs
- `data/references.db` — visual reference metadata
- `data/content_intelligence.db` — trends, watchlist, Idea Inbox, Brand DNA and performance memory

Database/WAL files, runtime uploads and generated outputs are excluded from Git.

## Environment variables
Copy `.env.example` and configure only the providers you want to use.

Important server-side variables:
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `PEXELS_API_KEY`
- `PIXABAY_API_KEY`
- `GEMINI_TEXT_MODEL`, `GEMINI_VISION_MODEL`, `GROQ_TEXT_MODEL`, `OPENROUTER_TEXT_MODEL`
- `JOB_DB_PATH`, `REFERENCE_DB_PATH`, `INTELLIGENCE_DB_PATH`
- `MUSIC_LIBRARY_DIR`
- `FFMPEG_BINARY`, `FFPROBE_BINARY`
- `ALLOWED_ORIGINS`, `PUBLIC_APP_URL`

The web app uses `VITE_API_BASE_URL`.

## Development
### Web
```bash
npm install
npm run dev
```

### Worker
FFmpeg must be installed on the machine running the worker.

```bash
cd services/worker
python -m venv .venv
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Music library
Upload royalty-free tracks through the worker's `/music/library` endpoint or place approved tracks in `assets/music`. If the library is empty, the pipeline continues without background music instead of failing.

## Security and cost rules
- Never commit API keys.
- Provider secrets stay server-side.
- The core Trend Radar does not require a paid API subscription.
- YouTube/TikTok paid APIs are not required for trend discovery.
- Uploaded references and generated media are stored in runtime/output folders, not GitHub.
- Media processing happens outside the browser.
- SQLite runtime data is excluded from Git.

## CI
GitHub Actions verifies:
- React/TypeScript production build
- Python dependencies and syntax
- FastAPI application import and intelligence route registration
- SQLite job/reference/content-intelligence persistence
- Trend scoring/parser smoke test
- FFmpeg availability
- FFmpeg subtitle/ASS filter availability
