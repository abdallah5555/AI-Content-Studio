import { ChangeEvent, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Download,
  Film,
  ImagePlus,
  KeyRound,
  Lightbulb,
  LoaderCircle,
  Plus,
  Radar,
  Sparkles,
  WandSparkles,
} from 'lucide-react';
import {
  approveJob,
  createJob,
  editJobStage,
  getJob,
  regenerateJobStage,
  resolveWorkerUrl,
  uploadReference,
  type JobStatus,
  type ReferencePreferences,
  type UploadedReference,
} from './api';
import { ContentIntelligence } from './ContentIntelligence';
import { contentTypes, pipelineStages, platforms, type PlatformId } from './contentConfig';
import { JobHistory } from './JobHistory';
import { Scheduler } from './Scheduler';
import { ServiceSettings } from './ServiceSettings';

type View = 'dashboard' | 'create' | 'history' | 'intelligence' | 'schedule' | 'settings';
type PreferenceKey = keyof ReferencePreferences;

const defaultPreferences: ReferencePreferences = {
  preserve_style: true,
  preserve_colors: true,
  preserve_composition: false,
  preserve_motion: false,
  preserve_character_shape: true,
};

const preferenceOptions: { key: PreferenceKey; label: string; hint: string }[] = [
  { key: 'preserve_style', label: 'الستايل العام', hint: 'نفس الروح وطريقة التنفيذ.' },
  { key: 'preserve_colors', label: 'الألوان', hint: 'نفس الإحساس اللوني.' },
  { key: 'preserve_composition', label: 'التكوين', hint: 'تقارب في توزيع العناصر والكادرات.' },
  { key: 'preserve_motion', label: 'الحركة', hint: 'إيقاع وحركة مشابهة لو المرجع فيديو.' },
  { key: 'preserve_character_shape', label: 'شكل العناصر', hint: 'هوية شكل قريبة بدون نسخ المحتوى.' },
];

const voiceOptions = [
  { id: 'ar-EG-SalmaNeural', label: 'سلمى', hint: 'صوت أنثى عربي مصري' },
  { id: 'ar-EG-ShakirNeural', label: 'شاكر', hint: 'صوت ذكر عربي مصري' },
];

function prettySize(bytes?: number) {
  if (!bytes) return '—';
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function OutputView({ job }: { job: JobStatus }) {
  const completedExport = job.status === 'completed' ? job.outputs?.export : null;
  const output = completedExport || job.stage_output;
  if (!output && !job.error) return null;

  if (job.error) return <section className="generation-output generation-output-error"><div className="generation-error">{job.error}</div></section>;

  if (!completedExport && job.stage === 'tts' && output?.audio_url) {
    return <section className="generation-output"><audio controls preload="metadata" src={resolveWorkerUrl(output.audio_url)} /></section>;
  }

  if (completedExport || ['edit', 'effects', 'music', 'export'].includes(job.stage)) {
    const path = (output?.video_url || output?.download_url) as string | undefined;
    if (path) {
      const url = resolveWorkerUrl(path);
      return (
        <section className="generation-output video-output">
          {completedExport && <div className="generation-output-head"><span className="eyebrow">الفيديو النهائي</span><span className="provider-pill">جاهز للنشر</span></div>}
          <video controls preload="metadata" src={url} />
          <a className="download-link" href={url} download={output?.filename as string | undefined}><Download size={16} /> تنزيل MP4</a>
        </section>
      );
    }
  }

  return (
    <section className="generation-output">
      <div className="generation-output-head"><span className="eyebrow">ناتج المرحلة الحالية</span>{job.active_provider && <span className="provider-pill">{job.active_provider}</span>}</div>
      <pre>{JSON.stringify(output?.content || output || {}, null, 2)}</pre>
    </section>
  );
}

export function App() {
  const [view, setView] = useState<View>('dashboard');
  const [platformId, setPlatformId] = useState<PlatformId>('tiktok');
  const [contentType, setContentType] = useState('تعليمي');
  const [duration, setDuration] = useState(60);
  const [reviewEachStage, setReviewEachStage] = useState(false);
  const [ideaPrompt, setIdeaPrompt] = useState('');
  const [references, setReferences] = useState<UploadedReference[]>([]);
  const [preferences, setPreferences] = useState<ReferencePreferences>(defaultPreferences);
  const [ttsVoice, setTtsVoice] = useState('ar-EG-SalmaNeural');
  const [ttsRate, setTtsRate] = useState(0);
  const [musicVolume, setMusicVolume] = useState(12);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [manualEditOpen, setManualEditOpen] = useState(false);
  const [manualEditText, setManualEditText] = useState('{}');

  const selectedPlatform = useMemo(() => platforms.find((platform) => platform.id === platformId) ?? platforms[0], [platformId]);

  useEffect(() => {
    if (!job || ['completed', 'failed', 'waiting_review'].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      try { setJob(await getJob(job.id)); } catch { /* keep last known state */ }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [job?.id, job?.status]);

  useEffect(() => { setManualEditOpen(false); }, [job?.stage, job?.id]);

  function useIntelligenceIdea(idea: string) {
    setIdeaPrompt(idea);
    setJob(null);
    setError('');
    setView('create');
  }

  function openHistoricalJob(restored: JobStatus) {
    setJob(restored);
    if (platforms.some((platform) => platform.id === restored.input.platform)) setPlatformId(restored.input.platform as PlatformId);
    setContentType(restored.input.content_type || 'تعليمي');
    setDuration(restored.input.duration_seconds || 60);
    setReviewEachStage(Boolean(restored.input.review_each_stage));
    setIdeaPrompt(restored.input.idea_prompt || '');
    setPreferences(restored.input.reference_preferences || defaultPreferences);
    setTtsVoice(restored.input.tts_voice || 'ar-EG-SalmaNeural');
    setTtsRate(Number(String(restored.input.tts_rate || '0').replace(/[+%]/g, '')) || 0);
    setMusicVolume(Math.round(Number(restored.input.music_volume ?? 0.12) * 100));
    setReferences([]);
    setView('create');
  }

  async function handleReferenceFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (!files.length) return;
    setUploading(true); setError('');
    try {
      const uploaded = await Promise.all(files.map((file) => uploadReference(file)));
      setReferences((current) => [...current, ...uploaded]);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'تعذر رفع المرجع.'); }
    finally { setUploading(false); event.target.value = ''; }
  }

  async function startJob() {
    if (!ideaPrompt.trim()) { setError('اكتب الفكرة أولًا.'); return; }
    if (references.some((reference) => reference.analysis_status === 'failed')) { setError('في مرجع فشل تحليله. احذفه أو أصلح إعداد Gemini.'); return; }
    setSubmitting(true); setError('');
    try {
      setJob(await createJob({
        platform: selectedPlatform.id,
        aspect_ratio: selectedPlatform.aspectRatio,
        duration_seconds: duration,
        content_type: contentType,
        review_each_stage: reviewEachStage,
        idea_prompt: ideaPrompt.trim(),
        reference_mode: references.length ? 'adapt_style_to_new_idea' : 'none',
        reference_ids: references.map((reference) => reference.id),
        reference_preferences: preferences,
        tts_voice: ttsVoice,
        tts_rate: `${ttsRate >= 0 ? '+' : ''}${ttsRate}%`,
        music_volume: musicVolume / 100,
      }));
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'تعذر بدء المهمة.'); }
    finally { setSubmitting(false); }
  }

  async function continueAfterReview() {
    if (!job) return;
    setReviewBusy(true); setError('');
    try { setJob(await approveJob(job.id)); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'تعذر الاستمرار.'); }
    finally { setReviewBusy(false); }
  }

  async function regenerateCurrentStage() {
    if (!job) return;
    setReviewBusy(true); setError('');
    try { setJob(await regenerateJobStage(job.id, job.stage)); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'تعذر إعادة التوليد.'); }
    finally { setReviewBusy(false); }
  }

  function openManualEdit() {
    if (!job?.stage_output?.content) return;
    setManualEditText(JSON.stringify(job.stage_output.content, null, 2));
    setManualEditOpen(true);
  }

  async function saveManualEdit() {
    if (!job) return;
    try {
      const parsed = JSON.parse(manualEditText) as Record<string, unknown>;
      setReviewBusy(true); setError('');
      setJob(await editJobStage(job.id, job.stage, parsed));
      setManualEditOpen(false);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'JSON غير صحيح أو تعذر الحفظ.'); }
    finally { setReviewBusy(false); }
  }

  if (view === 'history') return <JobHistory onBack={() => setView('dashboard')} onOpen={openHistoricalJob} />;
  if (view === 'intelligence') return <ContentIntelligence onBack={() => setView('dashboard')} onUseIdea={useIntelligenceIdea} />;
  if (view === 'schedule') return <Scheduler onBack={() => setView('dashboard')} />;
  if (view === 'settings') return <ServiceSettings onBack={() => setView('dashboard')} />;

  if (view === 'create') {
    const editable = job && ['idea', 'script', 'seo'].includes(job.stage);
    return (
      <main className="page-shell create-page">
        <button className="back-button" onClick={() => setView('dashboard')}><ArrowRight size={18} /> العودة للوحة التحكم</button>
        <section className="create-heading"><div className="brand-badge"><Sparkles size={18} /> إنشاء محتوى جديد</div><h1>من فكرة إلى فيديو كامل.</h1><p>اكتب فكرتك أو ابعتها من Content Intelligence، وارفع مرجع بصري لو عايز نفس الروح.</p></section>

        <div className="creator-layout">
          <section className="form-card">
            <div className="field-group"><div className="field-heading"><div><span className="field-index">1</span><strong>المنصة</strong></div></div><div className="platform-grid">{platforms.map((platform) => <button key={platform.id} className={`platform-option ${platform.id === platformId ? 'selected' : ''}`} onClick={() => setPlatformId(platform.id)}><strong>{platform.label}</strong><span>{platform.aspectRatio}</span><small>{platform.hint}</small></button>)}</div></div>
            <div className="field-group"><div className="field-heading"><div><span className="field-index">2</span><strong>نوع المحتوى</strong></div></div><div className="chip-row">{contentTypes.map((type) => <button key={type} className={`choice-chip ${contentType === type ? 'selected' : ''}`} onClick={() => setContentType(type)}>{type}</button>)}</div></div>
            <div className="field-group"><div className="field-heading"><div><span className="field-index">3</span><strong>الفكرة</strong></div></div><textarea className="prompt-area" value={ideaPrompt} onChange={(event) => setIdeaPrompt(event.target.value)} rows={6} placeholder="اكتب الفكرة أو استخدم رادار التريندات..." /></div>

            <div className="field-group">
              <div className="field-heading"><div><span className="field-index">4</span><strong>مرجع بصري</strong></div><span className="auto-pill">اختياري</span></div>
              <label className="upload-box"><input type="file" accept="image/*,video/*" multiple onChange={handleReferenceFiles} disabled={uploading} />{uploading ? <LoaderCircle className="spin" size={24} /> : <ImagePlus size={24} />}<div><strong>ارفع صورة أو فيديو</strong><span>نستخلص السمات البصرية ونطبقها على فكرة جديدة.</span></div></label>
              {references.length > 0 && <div className="reference-list">{references.map((reference) => <div className="reference-item" key={reference.id}><div><strong>{reference.name}</strong><span>{prettySize(reference.size_bytes)} · {reference.analysis_status}</span></div>{reference.analysis_status === 'ready' && <CheckCircle2 size={18} />}</div>)}</div>}
              <div className="preferences-grid">{preferenceOptions.map((option) => <button key={option.key} className={`preference-card ${preferences[option.key] ? 'selected' : ''}`} onClick={() => setPreferences((current) => ({ ...current, [option.key]: !current[option.key] }))}><strong>{option.label}</strong><span>{option.hint}</span></button>)}</div>
            </div>

            <div className="field-group"><div className="field-heading"><div><span className="field-index">5</span><strong>المدة</strong></div><span className="duration-value">{duration} ثانية</span></div><input className="duration-slider" type="range" min="15" max="300" step="15" value={duration} onChange={(event) => setDuration(Number(event.target.value))} /></div>
            <div className="field-group">
              <div className="field-heading"><div><span className="field-index">6</span><strong>الصوت والموسيقى</strong></div></div>
              <div className="voice-grid">{voiceOptions.map((voice) => <button key={voice.id} className={`voice-card ${ttsVoice === voice.id ? 'selected' : ''}`} onClick={() => setTtsVoice(voice.id)}><strong>{voice.label}</strong><span>{voice.hint}</span></button>)}</div>
              <div className="field-heading control-heading"><div><strong>سرعة التعليق الصوتي</strong></div><span className="duration-value">{ttsRate >= 0 ? '+' : ''}{ttsRate}%</span></div>
              <input className="duration-slider" type="range" min="-30" max="40" step="5" value={ttsRate} onChange={(event) => setTtsRate(Number(event.target.value))} />
              <div className="field-heading control-heading"><div><strong>مستوى موسيقى الخلفية</strong></div><span className="duration-value">{musicVolume}%</span></div>
              <input className="duration-slider" type="range" min="0" max="35" step="1" value={musicVolume} onChange={(event) => setMusicVolume(Number(event.target.value))} />
            </div>
            <label className="review-toggle"><div><strong>مراجعة كل مرحلة</strong><span>موافقة، إعادة توليد، أو تعديل يدوي.</span></div><input type="checkbox" checked={reviewEachStage} onChange={(event) => setReviewEachStage(event.target.checked)} /></label>
            {error && <div className="error-box">{error}</div>}
            <button className="cta wide-cta" onClick={startJob} disabled={submitting || uploading}>{submitting ? <LoaderCircle className="spin" size={19} /> : <Film size={19} />} ابدأ صناعة الفيديو</button>
          </section>

          <aside className="summary-card"><span className="eyebrow">ملخص</span><h2>{selectedPlatform.label}</h2><div className="preview-frame" data-ratio={selectedPlatform.aspectRatio}><Film size={28} /><span>{selectedPlatform.aspectRatio}</span></div><dl className="summary-list"><div><dt>الدقة</dt><dd>{selectedPlatform.resolution}</dd></div><div><dt>المدة</dt><dd>{duration} ث</dd></div><div><dt>الصوت</dt><dd>{ttsRate >= 0 ? '+' : ''}{ttsRate}%</dd></div><div><dt>الموسيقى</dt><dd>{musicVolume}%</dd></div><div><dt>المراجع</dt><dd>{references.length}</dd></div></dl><div className="reference-mode-card"><WandSparkles size={18} /><div><strong>Reference-to-Idea</strong><span>روح مشابهة، فكرة أصلية.</span></div></div></aside>
        </div>

        {job && <section className="job-card">
          <div className="job-head"><div><span className="eyebrow">المهمة {job.id.slice(0, 8)}</span><h2>{job.message}</h2></div><strong className="progress-number">{job.progress}%</strong></div>
          <div className="progress-track"><span style={{ width: `${job.progress}%` }} /></div>
          <div className="pipeline live-pipeline">{pipelineStages.map((stage, index) => { const current = pipelineStages.findIndex((item) => item.key === job.stage); const done = index < current || job.status === 'completed' || (job.status === 'waiting_review' && index === current); return <div className={`step ${done ? 'done' : ''} ${index === current && !done ? 'active' : ''}`} key={stage.key}><span>{done ? <CheckCircle2 size={15} /> : index + 1}</span><strong>{stage.label}</strong></div>; })}</div>
          <OutputView job={job} />
          {job.status === 'waiting_review' && <div className="review-panel"><div className="review-action"><div><strong>راجع المرحلة الحالية</strong><span>وافق أو أعد التوليد أو عدّل البيانات لو متاح.</span></div><div className="review-buttons"><button className="cta" onClick={continueAfterReview} disabled={reviewBusy}>موافقة والاستمرار</button><button className="review-secondary" onClick={regenerateCurrentStage} disabled={reviewBusy}>إعادة توليد</button>{editable && <button className="review-secondary" onClick={openManualEdit}>تعديل يدوي</button>}</div></div>{manualEditOpen && <div className="manual-editor"><textarea value={manualEditText} onChange={(event) => setManualEditText(event.target.value)} /><div className="review-buttons"><button className="cta" onClick={saveManualEdit}>حفظ</button><button className="review-secondary" onClick={() => setManualEditOpen(false)}>إلغاء</button></div></div>}</div>}
        </section>}
      </main>
    );
  }

  const cards = [
    { title: 'فيديو جديد', subtitle: 'ابدأ من فكرة حتى التصدير', icon: Plus, action: () => setView('create'), primary: true },
    { title: 'Content Intelligence', subtitle: 'تريندات، فجوات، Hooks، تخطيط وذاكرة تعلم', icon: Radar, action: () => setView('intelligence'), primary: true },
    { title: 'مكتبة الأفكار', subtitle: 'راجع المشاريع السابقة والنواتج المحفوظة', icon: Lightbulb, action: () => setView('history') },
    { title: 'المحتوى المجدول', subtitle: 'إدارة مواعيد النشر القادمة', icon: CalendarDays, action: () => setView('schedule') },
    { title: 'مصادر الخدمات', subtitle: 'حالة مزودي الذكاء الاصطناعي ومكتبة الموسيقى', icon: KeyRound, action: () => setView('settings') },
  ];

  return (
    <main className="page-shell">
      <section className="hero"><div className="brand-badge"><Sparkles size={18} /> AI Content Studio</div><h1>اكتشف الفكرة، قيّمها، وبعدها حوّلها لفيديو.</h1><p>الاستوديو يجمع Content Intelligence وخط إنتاج الفيديو والمكتبة والجدولة في واجهة واحدة.</p><div className="review-buttons"><button className="cta" onClick={() => setView('intelligence')}><Radar size={19} /> اكتشف الفرص</button><button className="review-secondary" onClick={() => setView('create')}><Film size={19} /> إنشاء فيديو</button></div></section>
      <section className="grid">{cards.map(({ title, subtitle, icon: Icon, action, primary }) => <button type="button" className={`card ${primary ? 'card-primary' : ''}`} key={title} onClick={action}><div className="icon-wrap"><Icon size={24} /></div><h2>{title}</h2><p>{subtitle}</p></button>)}</section>
      <section className="pipeline-card"><div><span className="eyebrow">خط الإنتاج</span><h2>٩ مراحل من الفكرة للنشر</h2></div><div className="pipeline">{pipelineStages.map((step, index) => <div className="step" key={step.key}><span>{index + 1}</span><strong>{step.label}</strong></div>)}</div></section>
    </main>
  );
}
