import { Capacitor } from '@capacitor/core';
import { App as CapacitorApp } from '@capacitor/app';
import { FileTransfer } from '@capacitor/file-transfer';
import { Directory, Filesystem } from '@capacitor/filesystem';
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

function safeFilename(value: string) {
  const cleaned = value.replace(/[\\/:*?"<>|]+/g, '-').replace(/\s+/g, ' ').trim();
  return cleaned.toLowerCase().endsWith('.mp4') ? cleaned : `${cleaned || 'ai-content-studio'}.mp4`;
}

export async function saveVideoToDevice(url: string, filename = 'ai-content-studio.mp4') {
  if (!isNativeApp()) {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = safeFilename(filename);
    anchor.click();
    return { uri: url };
  }

  try {
    await Filesystem.mkdir({ directory: Directory.Documents, path: 'AI Content Studio', recursive: true });
  } catch {
    // Existing folder is fine.
  }

  const target = `AI Content Studio/${safeFilename(filename)}`;
  const fileInfo = await Filesystem.getUri({ directory: Directory.Documents, path: target });
  await FileTransfer.downloadFile({ url, path: fileInfo.uri, progress: false });
  return { uri: fileInfo.uri };
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
