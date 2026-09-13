import { installNativeBackHandler, installNetworkListener, isNativeApp, saveVideoToDevice, shareVideo } from './native';

type Cleanup = () => void;

function ensureNetworkBanner() {
  let banner = document.getElementById('runtime-network-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'runtime-network-banner';
    banner.className = 'runtime-network-banner';
    banner.setAttribute('role', 'status');
    banner.textContent = 'لا يوجد اتصال بالإنترنت — هترجع المزايا أونلاين تلقائيًا عند رجوع الشبكة.';
    document.body.appendChild(banner);
  }
  return banner;
}

function installNativeDownloadButtons(): Cleanup {
  const enhance = () => {
    document.querySelectorAll<HTMLAnchorElement>('a.download-link').forEach((link) => {
      if (link.dataset.nativeEnhanced === 'true') return;
      link.dataset.nativeEnhanced = 'true';

      const save = document.createElement('button');
      save.type = 'button';
      save.className = 'native-share-button';
      save.textContent = 'حفظ على الجهاز';
      save.addEventListener('click', async () => {
        const original = save.textContent;
        save.disabled = true;
        save.textContent = 'جاري الحفظ...';
        try {
          await saveVideoToDevice(link.href, link.download || 'ai-content-studio.mp4');
          save.textContent = 'تم الحفظ ✓';
        } catch {
          save.textContent = 'تعذر الحفظ';
        } finally {
          window.setTimeout(() => {
            save.disabled = false;
            save.textContent = original;
          }, 2200);
        }
      });

      const share = document.createElement('button');
      share.type = 'button';
      share.className = 'native-share-button';
      share.textContent = 'مشاركة الفيديو';
      share.addEventListener('click', () => {
        void shareVideo(link.href, link.download || 'AI Content Studio').catch(() => undefined);
      });

      link.insertAdjacentElement('afterend', share);
      link.insertAdjacentElement('afterend', save);
    });
  };

  enhance();
  const observer = new MutationObserver(enhance);
  observer.observe(document.body, { childList: true, subtree: true });
  return () => observer.disconnect();
}

async function registerPwa() {
  if (isNativeApp() || !('serviceWorker' in navigator)) return;
  try {
    await navigator.serviceWorker.register('/sw.js');
  } catch {
    // The app remains fully usable online if service worker registration fails.
  }
}

export async function bootstrapRuntime() {
  void registerPwa();

  const banner = ensureNetworkBanner();
  let removeNetwork: Cleanup = () => {};
  let removeBack: Cleanup = () => {};
  let removeNativeDownloads: Cleanup = () => {};

  try {
    removeNetwork = await installNetworkListener((connected) => {
      banner.classList.toggle('visible', !connected);
      document.documentElement.dataset.network = connected ? 'online' : 'offline';
    });
  } catch {
    // Browser/native plugin availability should never block rendering.
  }

  if (isNativeApp()) {
    removeNativeDownloads = installNativeDownloadButtons();
    try {
      removeBack = await installNativeBackHandler(() => {
        const back = document.querySelector<HTMLButtonElement>('button.back-button');
        if (back) {
          back.click();
          return true;
        }
        if (window.history.length > 1) {
          window.history.back();
          return true;
        }
        return false;
      });
    } catch {
      // Native back falls back to Android default behavior.
    }
  }

  return () => {
    removeNetwork();
    removeBack();
    removeNativeDownloads();
  };
}
