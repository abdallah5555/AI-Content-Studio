import type { CapacitorConfig } from '@capacitor/cli';

const PRODUCTION_WEB_URL = 'https://ai-content-studio-web-production.up.railway.app';

const config: CapacitorConfig = {
  appId: 'com.aicontentstudio.app',
  appName: 'AI Content Studio',
  webDir: 'apps/web/dist',
  server: {
    // The Android shell loads the production web app directly. Normal UI,
    // workflow, copy, and API-client changes are therefore delivered from the
    // hosted app without requiring users to install a new APK.
    // A new APK is only required when native Capacitor/plugins/config change.
    url: PRODUCTION_WEB_URL,
    cleartext: false,
    allowNavigation: ['ai-content-studio-web-production.up.railway.app'],
  },
  android: {
    backgroundColor: '#070b17',
  },
};

export default config;
