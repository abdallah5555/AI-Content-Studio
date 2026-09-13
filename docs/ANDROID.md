# Android build

AI Content Studio now supports Android through Capacitor 8 while keeping the existing React/Vite application as the single UI codebase.

## Architecture

- React/Vite remains the shared web UI.
- Capacitor provides the Android native shell.
- The FastAPI/FFmpeg worker stays server-side; the APK does not run FFmpeg or AI generation locally.
- Android package id: `com.aicontentstudio.app`.
- App name: `AI Content Studio`.

## Free APK builds

GitHub Actions workflow: `.github/workflows/android-apk.yml`.

Every push to `main` builds a debug APK and uploads it as the artifact:

`AI-Content-Studio-Android-debug`

The build uses Node 22, Java 21, Capacitor Android, and the Android SDK available on the GitHub runner.

## Backend URL

The mobile app needs a reachable HTTPS worker URL. Set the GitHub repository variable:

`VITE_API_BASE_URL=https://your-worker.example.com`

The Android workflow injects this value into the Vite build. If it is not set, the web code falls back to `http://localhost:8000`, which is useful only for local browser development and will not reach a remote worker from an installed phone.

The worker must allow the deployed app/web origins through its CORS configuration. Native Capacitor requests originate from the app WebView, so production networking should use HTTPS.

## Local Android development

From the repository root:

```bash
npm install
npm run build
npm run android:add
npm run android:sync
npm run android:open
```

After the Android project exists locally, use `npm run android:sync` after web changes.

## Native helpers already available

`apps/web/src/native.ts` includes helpers for:

- Android hardware back handling
- Native share sheet
- Network connectivity status/listening

These helpers fall back safely when running as a normal website.
