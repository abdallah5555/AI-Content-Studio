import { expect, test, type Page } from '@playwright/test';

const completedJob = {
  id: 'job-complete-1',
  status: 'completed',
  stage: 'seo',
  progress: 100,
  message: 'اكتمل خط الإنتاج',
  input: {
    platform: 'tiktok',
    aspect_ratio: '9:16',
    duration_seconds: 30,
    content_type: 'تعليمي',
    review_each_stage: false,
    idea_prompt: 'فكرة تجريبية',
    reference_mode: 'none',
    reference_ids: [],
    reference_preferences: {},
    tts_voice: 'ar-EG-SalmaNeural',
    tts_rate: '+0%',
    music_volume: 0.12,
  },
  outputs: {
    export: { provider: 'ffmpeg', download_url: '/media/exports/test.mp4', filename: 'test.mp4' },
    seo: { content: { title: 'فيديو تجريبي' } },
  },
  stage_output: { content: { title: 'فيديو تجريبي' } },
  active_provider: 'gemini',
  provider_failover_log: [],
  error: null,
};

async function mockWorker(page: Page) {
  await page.route('http://localhost:8000/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path === '/jobs' && route.request().method() === 'GET') {
      return route.fulfill({ json: { jobs: [{ id: completedJob.id, status: 'completed', stage: 'seo', progress: 100, title: 'فيديو تجريبي', created_at: new Date().toISOString(), updated_at: new Date().toISOString() }] } });
    }
    if (path === `/jobs/${completedJob.id}`) return route.fulfill({ json: completedJob });
    if (path === '/intelligence/trends' || path === '/intelligence/trends/refresh') return route.fulfill({ json: { items: [] } });
    if (path === '/intelligence/watchlist') return route.fulfill({ json: { items: [] } });
    if (path === '/intelligence/inbox') return route.fulfill({ json: { ideas: [] } });
    if (path === '/intelligence/brand') return route.fulfill({ json: { profile: {} } });
    if (path === '/references/avatar-library') return route.fulfill({ json: { avatars: [] } });
    if (path === '/schedule') return route.fulfill({ json: { items: [] } });
    if (path === '/providers/status') {
      return route.fulfill({ json: {
        providers: [
          { id: 'gemini', label: 'Google Gemini', capability: 'text', priority: 1, configured: true },
          { id: 'pexels', label: 'Pexels', capability: 'media', priority: 1, configured: true },
        ],
        failover_order: { text: ['gemini'], media: ['pexels'] },
        ready: { text: true, media: true },
        active: { text: 'gemini', media: 'pexels' },
      } });
    }
    if (path === '/music/library') return route.fulfill({ json: { count: 0, tracks: [] } });
    if (path.startsWith('/media/')) return route.fulfill({ status: 204, body: '' });

    return route.fulfill({ status: 200, json: {} });
  });
}

test.beforeEach(async ({ page }) => {
  await mockWorker(page);
  await page.goto('/');
});

test('dashboard exposes all activated product areas', async ({ page }) => {
  await expect(page.getByRole('heading', { name: /اكتشف فكرة قابلة للتنفيذ/ })).toBeVisible();
  for (const label of ['فيديو جديد', 'رادار فرص الفيديو', 'مكتبة الأفاتارات', 'مكتبة الأفكار', 'المحتوى المجدول', 'مصادر الخدمات']) {
    await expect(page.getByRole('button', { name: new RegExp(label) })).toBeVisible();
  }
});

test('video opportunity radar opens and returns to dashboard', async ({ page }) => {
  await page.getByRole('button', { name: /رادار فرص الفيديو/ }).click();
  await expect(page.getByRole('heading', { name: /مش أي تريند/ })).toBeVisible();
  await expect(page.getByText('Video Opportunity Radar').first()).toBeVisible();
  await expect(page.getByText('مناسب للأداة فقط')).toBeVisible();
  await page.getByRole('button', { name: /العودة للوحة التحكم/ }).click();
  await expect(page.getByRole('heading', { name: /اكتشف فكرة قابلة للتنفيذ/ })).toBeVisible();
});

test('avatar library opens and exposes upload flow', async ({ page }) => {
  await page.getByRole('button', { name: /مكتبة الأفاتارات/ }).click();
  await expect(page.getByRole('heading', { name: /اعمل شخصيتك مرة/ })).toBeVisible();
  await expect(page.getByText('ارفع صورة واضحة').first()).toBeVisible();
  await expect(page.getByRole('button', { name: /حفظ الأفاتار/ })).toBeVisible();
});

test('history exposes completed final video preview action', async ({ page }) => {
  await page.getByRole('button', { name: /مكتبة الأفكار/ }).click();
  await expect(page.getByRole('heading', { name: /المشاريع والأفكار السابقة/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /عرض الفيديو/ })).toBeVisible();
});

test('scheduler loads completed projects and scheduling controls', async ({ page }) => {
  await page.getByRole('button', { name: /المحتوى المجدول/ }).click();
  await expect(page.getByRole('heading', { name: /المحتوى المجدول/ })).toBeVisible();
  await expect(page.getByText('أضف موعد نشر')).toBeVisible();
  await expect(page.getByRole('combobox').first()).toContainText('فيديو تجريبي');
});

test('service center reports provider readiness and music library', async ({ page }) => {
  await page.getByRole('button', { name: /مصادر الخدمات/ }).click();
  await expect(page.getByRole('heading', { name: /مصادر الخدمات/ })).toBeVisible();
  await expect(page.getByText('Google Gemini', { exact: true })).toBeVisible();
  await expect(page.getByText('Pexels', { exact: true })).toBeVisible();
  await expect(page.getByText(/المكتبة فاضية/)).toBeVisible();
});

test('create page exposes real voice speed and music controls', async ({ page }) => {
  await page.getByRole('button', { name: /فيديو جديد/ }).click();
  await expect(page.getByRole('heading', { name: /من فكرة إلى فيديو كامل/ })).toBeVisible();
  await expect(page.getByText('سرعة التعليق الصوتي')).toBeVisible();
  await expect(page.getByText('مستوى موسيقى الخلفية')).toBeVisible();
  await expect(page.getByRole('button', { name: /مكتبة الأفاتارات/ })).toBeVisible();
  await expect(page.locator('input[type="range"]')).toHaveCount(3);
});

test('PWA manifest is served', async ({ request }) => {
  const response = await request.get('/manifest.webmanifest');
  expect(response.ok()).toBeTruthy();
  const manifest = await response.json();
  expect(manifest.name).toBe('AI Content Studio');
  expect(manifest.display).toBe('standalone');
});
