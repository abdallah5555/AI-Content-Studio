import { Capacitor } from '@capacitor/core';
import { App as CapacitorApp } from '@capacitor/app';
import { Network } from '@capacitor/network';
import { Share } from '@capacitor/share';

export function isNativeApp() {
  return Capacitor.isNativePlatform();
}

export async function installNativeBackHandler(onBack: () => boolean) {
  if (!isNativeApp()) return () => undefined;

  const handle = await CapacitorApp.addListener('backButton', () => {
    const handled = onBack();
    if (!handled) void CapacitorApp.exitApp();
  });

  return () => { void handle.remove(); };
}

export async function shareVideo(url: string, title = 'AI Content Studio') {
  if (isNativeApp()) {
    await Share.share({ title, text: 'الفيديو جاهز من AI Content Studio', url, dialogTitle: 'مشاركة الفيديو' });
    return;
  }

  if (navigator.share) {
    await navigator.share({ title, text: 'الفيديو جاهز من AI Content Studio', url });
    return;
  }

  await navigator.clipboard.writeText(url);
}

export async function readNetworkStatus() {
  return Network.getStatus();
}

export async function installNetworkListener(onChange: (connected: boolean) => void) {
  const current = await Network.getStatus();
  onChange(current.connected);

  const handle = await Network.addListener('networkStatusChange', (status) => onChange(status.connected));
  return () => { void handle.remove(); };
}
