# AI Content Studio — Product Requirements

This repository implements the personal AI social-media content studio defined in the project requirements.

## Product goal
A browser-based application that can take a user from content settings to a finished social video with minimal intervention: idea generation, script, text-to-speech, media selection, captions, editing, effects, royalty-safe music, export, SEO metadata, scheduling and publishing.

## Main user flow
1. Sign in.
2. Dashboard with New Video, idea history, scheduled videos and API/service settings.
3. Choose target platform/aspect ratio, content type and duration (15–300 seconds).
4. Run a nine-stage pipeline: idea → script → TTS → media → edit → effects → music → export → SEO.
5. Optional review mode can pause after stages for approve, regenerate or manual edit.
6. After export, allow partial timeline edits instead of rebuilding the entire video.
7. Download MP4 or schedule/publish to connected platforms.

## Supported formats
- 9:16 — TikTok, Facebook/Instagram Reels, YouTube Shorts, Snapchat.
- 1:1 — square Instagram/Facebook posts.
- 4:5 — vertical Instagram posts.
- 16:9 — standard YouTube and long-form Facebook video.
- Architecture must permit adding formats later.

## Core requirements
- Semantic duplicate detection against each user's previous ideas/scripts.
- Hook-first scripts with retention structure and CTA, sized to selected duration.
- TTS voice, language/accent, speed and tone controls.
- Royalty-safe stock image/video selection.
- Automatically timed captions.
- Automatic transitions/effects and background music with dialogue-safe volume.
- Live named progress for each pipeline stage.
- Optional approval checkpoints.
- Provider/API settings with automatic failover when a free-tier provider is unavailable or rate-limited.
- MP4 export.
- Direct/scheduled publishing where official platform APIs permit it.
- Automatic title, description and tags/hashtags.

## Non-functional requirements
- Long video/media work runs as background jobs rather than blocking the browser.
- Provider secrets must not be exposed in the browser bundle and must be stored securely/encrypted.
- Providers and social platforms must be replaceable/extensible without rebuilding the product architecture.
- UI should be simple for a non-technical user.
- Apple-like visual direction with rounded surfaces, calm spacing, clear large controls, visible gradient progress and light/dark modes.

## Preferred service strategy
- LLM: Gemini primary, Groq/OpenRouter fallback, with provider abstraction.
- Stock media: Pexels + Pixabay.
- Editing/export: FFmpeg.
- Captions/alignment: Whisper-compatible local pipeline + FFmpeg.
- Publishing: official YouTube, Meta and TikTok APIs where available.
- Prioritize free/open-source options because this is initially a single-user personal tool.

## Delivery roadmap
1. Core: platform/ratio/duration + script + voice + simple export.
2. Full automatic editing + media/effects/music + live progress + review mode.
3. Partial post-export editing + provider/API management.
4. Scheduling/publishing + SEO.
5. Analytics, templates, repurposing, optional voice cloning, translation, best-time suggestions, rights checks, thumbnails and batch mode.
