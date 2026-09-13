# AI Content Studio

Personal AI-powered social media content production studio.

## Goal
Create complete social videos from idea generation through script, voice, media selection, captions, editing, export, SEO, and scheduled publishing.

## Current architecture
- `apps/web` — React + TypeScript + Vite web app / future PWA
- `services/worker` — FastAPI worker for AI orchestration and media processing
- FFmpeg — video normalization, montage, captions/effects, audio mixing, MP4 output
- AI text failover — Gemini → Groq → OpenRouter
- Visual reference analysis — Gemini multimodal
- TTS — Edge TTS with Egyptian Arabic voices
- Stock video failover — Pexels → Pixabay
- Local royalty-free music library — optional uploaded tracks mixed at low volume

## Implemented pipeline
1. **Idea** — generates an original concept from the user's request and optional visual reference.
2. **Script** — generates title, hook, narration, CTA and a timed scene plan.
3. **TTS** — converts narration to MP3 with Egyptian Arabic voice selection.
4. **Media** — searches Pexels/Pixabay for each scene with provider failover.
5. **Edit** — downloads selected clips, crops/scales them to the target aspect ratio, concatenates them and adds narration.
6. **Effects** — burns timed captions where supported and adds basic fade effects.
7. **Music** — mixes an optional royalty-free track from the local music library at voice-safe volume; skips safely if the library is empty.
8. **Export** — creates the final downloadable MP4.
9. **SEO** — generates upload-ready title, description, hashtags and keywords.

## Reference-to-Idea mode
The creator can upload an AI-generated image or video as a visual reference and then describe a completely different idea. The system analyzes observable visual traits such as style, color palette, composition, motion and object/character design, then uses only the selected reusable traits as guidance for the new work instead of copying the original content literally.

## Review mode
When **Review each stage** is enabled, the pipeline pauses after each stage so the user can inspect the idea, script, audio, media choices and rendered video before continuing.

## Environment variables
Copy `.env.example` and configure only the providers you want to use.

Important server-side variables:
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `PEXELS_API_KEY`
- `PIXABAY_API_KEY`
- optional model overrides such as `GEMINI_TEXT_MODEL` and `GEMINI_VISION_MODEL`
- optional `MUSIC_LIBRARY_DIR`
- optional `FFMPEG_BINARY` / `FFPROBE_BINARY`

The web app uses:
- `VITE_API_BASE_URL`

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

## Security rules
- Never commit API keys.
- Provider secrets stay server-side.
- Uploaded references and generated media are stored in runtime/output folders, not GitHub.
- Media processing happens outside the browser.

## CI
GitHub Actions verifies:
- React/TypeScript production build
- Python syntax
- FFmpeg availability
- FFmpeg subtitle/ASS filter availability
