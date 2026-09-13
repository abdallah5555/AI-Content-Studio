export type PlatformId = 'tiktok' | 'instagram' | 'facebook' | 'youtube-shorts' | 'youtube' | 'snapchat' | 'x';

export type PlatformOption = {
  id: PlatformId;
  label: string;
  aspectRatio: '9:16' | '1:1' | '4:5' | '16:9';
  resolution: string;
  hint: string;
};

export const platforms: PlatformOption[] = [
  { id: 'tiktok', label: 'تيك توك', aspectRatio: '9:16', resolution: '1080×1920', hint: 'فيديو عمودي قصير' },
  { id: 'instagram', label: 'إنستجرام Reels', aspectRatio: '9:16', resolution: '1080×1920', hint: 'ريلز عمودي' },
  { id: 'facebook', label: 'فيسبوك Reels', aspectRatio: '9:16', resolution: '1080×1920', hint: 'ريلز عمودي' },
  { id: 'youtube-shorts', label: 'YouTube Shorts', aspectRatio: '9:16', resolution: '1080×1920', hint: 'شورتس عمودي' },
  { id: 'youtube', label: 'YouTube', aspectRatio: '16:9', resolution: '1920×1080', hint: 'فيديو أفقي' },
  { id: 'snapchat', label: 'سناب شات', aspectRatio: '9:16', resolution: '1080×1920', hint: 'فيديو عمودي' },
  { id: 'x', label: 'X / تويتر', aspectRatio: '16:9', resolution: '1920×1080', hint: 'فيديو أفقي' },
];

export const contentTypes = [
  'تعليمي',
  'ترفيهي',
  'تحفيزي',
  'ديني',
  'أخبار',
  'قصصي',
  'تقني',
  'معلومات عامة',
];

export const pipelineStages = [
  { key: 'idea', label: 'توليد الفكرة' },
  { key: 'script', label: 'كتابة السكربت' },
  { key: 'tts', label: 'تحويل النص لصوت' },
  { key: 'media', label: 'اختيار المشاهد' },
  { key: 'edit', label: 'المونتاج' },
  { key: 'effects', label: 'المؤثرات' },
  { key: 'music', label: 'الموسيقى' },
  { key: 'export', label: 'التصدير' },
  { key: 'seo', label: 'SEO والنشر' },
] as const;
