import { ChangeEvent, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Film,
  ImagePlus,
  KeyRound,
  Lightbulb,
  LoaderCircle,
  Plus,
  Sparkles,
  WandSparkles,
} from 'lucide-react';
import {
  approveJob,
  createJob,
  getJob,
  resolveWorkerUrl,
  uploadReference,
  type JobStatus,
  type ReferencePreferences,
  type UploadedReference,
} from './api';
import { contentTypes, pipelineStages, platforms, type PlatformId } from './contentConfig';

type View = 'dashboard' | 'create';
type PreferenceKey = keyof ReferencePreferences;

const cards = [
  { title: 'فيديو جديد', subtitle: 'ابدأ من فكرة حتى التصدير', icon: Plus, primary: true, action: 'create' as const },
  { title: 'مكتبة الأفكار', subtitle: 'راجع المحتوى السابق ومنع التكرار', icon: Lightbulb },
  { title: 'المحتوى المجدول', subtitle: 'إدارة مواعيد النشر القادمة', icon: CalendarDays },
  { title: 'مصادر الخدمات', subtitle: 'إدارة مزودي الذكاء الاصطناعي وواجهات API', icon: KeyRound },
];

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

function prettySize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function prettyValue(value: unknown): string {
  if (value == null) return '—';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value, null, 2);
}

function GenerationOutput({ job }: { job: JobStatus }) {
  const output = job.stage_output;
  if (!output && !job.error) return null;

  const content = output?.content ?? {};
  const entries = Object.entries(content);

  return (
    <section className={`generation-output ${job.error ? 'generation-output-error' : ''}`}>
      <div className="generation-output-head">
        <div>
          <span className="eyebrow">ناتج المرحلة الحالية</span>
          <strong>{job.stage === 'idea' ? 'الفكرة' : job.stage === 'script' ? 'السكريبت' : job.stage === 'tts' ? 'التعليق الصوتي' : job.stage}</strong>
        </div>
        {job.active_provider && <span className="provider-pill">{job.active_provider}</span>}
      </div>

      {job.error ? (
        <div className="generation-error">{job.error}</div>
      ) : job.stage === 'tts' && output?.audio_url ? (
        <div className="audio-result">
          <audio controls preload="metadata" src={resolveWorkerUrl(output.audio_url)} />
          <div>
            <span>الصوت</span><strong>{output.voice}</strong>
            <span>الحجم</span><strong>{output.size_bytes ? prettySize(output.size_bytes) : '—'}</strong>
          </div>
        </div>
      ) : entries.length ? (
        <div className="generation-fields">
          {entries.map(([key, value]) => (
            <div className="generation-field" key={key}>
              <span>{key}</span>
              <pre>{prettyValue(value)}</pre>
            </div>
          ))}
        </div>
      ) : output?.message ? (
        <p className="generation-message">{output.message}</p>
      ) : null}

      {job.provider_failover_log && job.provider_failover_log.length > 0 && (
        <details className="failover-details">
          <summary>تفاصيل التحويل بين مزودي الذكاء الاصطناعي</summary>
          <ul>
            {job.provider_failover_log.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </details>
      )}
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
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [approving, setApproving] = useState(false);

  const selectedPlatform = useMemo(
    () => platforms.find((platform) => platform.id === platformId) ?? platforms[0],
    [platformId],
  );

  useEffect(() => {
    if (!job || ['completed', 'failed', 'waiting_review'].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      try {
        setJob(await getJob(job.id));
      } catch {
        // Preserve the last known state during temporary worker/network interruptions.
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [job?.id, job?.status]);

  async function handleReferenceFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (!files.length) return;
    setError('');
    setUploading(true);
    try {
      const uploaded = await Promise.all(files.map((file) => uploadReference(file)));
      setReferences((current) => [...current, ...uploaded]);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'تعذر رفع المرجع البصري.');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  }

  function togglePreference(key: PreferenceKey) {
    setPreferences((current) => ({ ...current, [key]: !current[key] }));
  }

  async function startJob() {
    if (!ideaPrompt.trim()) {
      setError('اكتب الفكرة التي تريد تنفيذها أولًا.');
      return;
    }

    const failedReferences = references.filter((reference) => reference.analysis_status === 'failed');
    if (failedReferences.length) {
      setError('يوجد مرجع لم يكتمل تحليله. احذف المرجع أو أصلح إعداد Gemini قبل بدء التوليد.');
      return;
    }

    setError('');
    setSubmitting(true);
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
        tts_rate: '+0%',
      }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'تعذر بدء المهمة. تأكد أن الـ Worker يعمل.');
    } finally {
      setSubmitting(false);
    }
  }

  async function continueAfterReview() {
    if (!job) return;
    setError('');
    setApproving(true);
    try {
      setJob(await approveJob(job.id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'تعذر استكمال المهمة.');
    } finally {
      setApproving(false);
    }
  }

  if (view === 'create') {
    return (
      <main className="page-shell create-page">
        <button className="back-button" onClick={() => { setView('dashboard'); setJob(null); setError(''); }}>
          <ArrowRight size={18} /> العودة للوحة التحكم
        </button>

        <section className="create-heading">
          <div className="brand-badge"><Sparkles size={18} /> إنشاء محتوى جديد</div>
          <h1>اكتب فكرتك، ولو عندك مرجع بصري ارفعه.</h1>
          <p>ممكن ترفع صورة أو فيديو ذكاء اصطناعي عجبك، والأداة تستخدم نفس الروح البصرية على فكرة جديدة أنت تحددها.</p>
        </section>

        <div className="creator-layout">
          <section className="form-card">
            <div className="field-group">
              <div className="field-heading">
                <div><span className="field-index">1</span><strong>المنصة والمقاس</strong></div>
                <span className="auto-pill">المقاس تلقائي</span>
              </div>
              <div className="platform-grid">
                {platforms.map((platform) => (
                  <button type="button" className={`platform-option ${platform.id === platformId ? 'selected' : ''}`} key={platform.id} onClick={() => setPlatformId(platform.id)}>
                    <strong>{platform.label}</strong>
                    <span>{platform.aspectRatio} · {platform.resolution}</span>
                    <small>{platform.hint}</small>
                  </button>
                ))}
              </div>
            </div>

            <div className="field-group">
              <div className="field-heading"><div><span className="field-index">2</span><strong>نوع المحتوى</strong></div></div>
              <div className="chip-row">
                {contentTypes.map((type) => (
                  <button type="button" className={`choice-chip ${contentType === type ? 'selected' : ''}`} key={type} onClick={() => setContentType(type)}>{type}</button>
                ))}
              </div>
            </div>

            <div className="field-group">
              <div className="field-heading"><div><span className="field-index">3</span><strong>الفكرة الجديدة</strong></div></div>
              <textarea
                className="prompt-area"
                value={ideaPrompt}
                onChange={(event) => setIdeaPrompt(event.target.value)}
                rows={5}
                placeholder="مثال: عايز فيديو عن فوائد شرب المياه، لكن بنفس روح وأسلوب المرجع اللي رفعته."
              />
            </div>

            <div className="field-group">
              <div className="field-heading">
                <div><span className="field-index">4</span><strong>مرجع بصري اختياري</strong></div>
                <span className="auto-pill">صورة أو فيديو</span>
              </div>

              <label className="upload-box">
                <input type="file" accept="image/*,video/*" multiple onChange={handleReferenceFiles} disabled={uploading} />
                {uploading ? <LoaderCircle className="spin" size={24} /> : <ImagePlus size={24} />}
                <div>
                  <strong>{uploading ? 'جاري رفع وتحليل المرجع...' : 'ارفع صورة أو فيديو كمرجع'}</strong>
                  <span>الحد الحالي 100MB لكل ملف. الملفات تذهب للـWorker ولا يتم وضعها داخل GitHub.</span>
                </div>
              </label>

              {references.length > 0 && (
                <div className="reference-list">
                  {references.map((reference) => (
                    <div className="reference-item" key={reference.id}>
                      <div>
                        <strong>{reference.name}</strong>
                        <span>
                          {reference.kind === 'video' ? 'فيديو' : 'صورة'} · {prettySize(reference.size_bytes)} · {
                            reference.analysis_status === 'ready' ? 'تم التحليل' :
                            reference.analysis_status === 'failed' ? 'فشل التحليل' : 'جاري التحليل'
                          }
                        </span>
                      </div>
                      {reference.analysis_status === 'ready' && <CheckCircle2 size={18} />}
                    </div>
                  ))}
                </div>
              )}

              <div className="preferences-grid">
                {preferenceOptions.map((option) => (
                  <button
                    type="button"
                    key={option.key}
                    className={`preference-card ${preferences[option.key] ? 'selected' : ''}`}
                    onClick={() => togglePreference(option.key)}
                  >
                    <strong>{option.label}</strong>
                    <span>{option.hint}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="field-group">
              <div className="field-heading">
                <div><span className="field-index">5</span><strong>مدة الفيديو</strong></div>
                <span className="duration-value">{duration < 60 ? `${duration} ثانية` : `${Math.floor(duration / 60)}:${String(duration % 60).padStart(2, '0')} دقيقة`}</span>
              </div>
              <input className="duration-slider" type="range" min="15" max="300" step="15" value={duration} onChange={(event) => setDuration(Number(event.target.value))} />
              <div className="range-labels"><span>15 ثانية</span><span>5 دقائق</span></div>
            </div>

            <div className="field-group">
              <div className="field-heading"><div><span className="field-index">6</span><strong>الصوت</strong></div><span className="auto-pill">مجاني</span></div>
              <div className="voice-grid">
                {voiceOptions.map((voice) => (
                  <button
                    type="button"
                    key={voice.id}
                    className={`voice-card ${ttsVoice === voice.id ? 'selected' : ''}`}
                    onClick={() => setTtsVoice(voice.id)}
                  >
                    <strong>{voice.label}</strong>
                    <span>{voice.hint}</span>
                  </button>
                ))}
              </div>
            </div>

            <label className="review-toggle">
              <div>
                <strong>مراجعة كل مرحلة قبل الاستمرار</strong>
                <span>عند التفعيل، يتوقف خط الإنتاج بعد كل مرحلة حتى توافق أو تعدّل النتيجة.</span>
              </div>
              <input type="checkbox" checked={reviewEachStage} onChange={(event) => setReviewEachStage(event.target.checked)} />
            </label>

            {error && <div className="error-box">{error}</div>}

            <button className="cta wide-cta" onClick={startJob} disabled={submitting || uploading || Boolean(job && !['completed', 'failed'].includes(job.status))}>
              {submitting ? <LoaderCircle className="spin" size={19} /> : <Film size={19} />}
              {job ? 'المهمة قيد التنفيذ' : 'ابدأ صناعة الفيديو'}
            </button>
          </section>

          <aside className="summary-card">
            <span className="eyebrow">ملخص الإعداد</span>
            <h2>{selectedPlatform.label}</h2>
            <div className="preview-frame" data-ratio={selectedPlatform.aspectRatio}>
              <Film size={28} />
              <span>{selectedPlatform.aspectRatio}</span>
            </div>
            <dl className="summary-list">
              <div><dt>الدقة</dt><dd>{selectedPlatform.resolution}</dd></div>
              <div><dt>نوع المحتوى</dt><dd>{contentType}</dd></div>
              <div><dt>المدة</dt><dd>{duration} ثانية</dd></div>
              <div><dt>الصوت</dt><dd>{voiceOptions.find((voice) => voice.id === ttsVoice)?.label}</dd></div>
              <div><dt>المراجعة</dt><dd>{reviewEachStage ? 'مفعّلة' : 'تلقائي بالكامل'}</dd></div>
              <div><dt>المراجع</dt><dd>{references.length ? `${references.length} ملف` : 'بدون'}</dd></div>
            </dl>
            <div className="reference-mode-card">
              <WandSparkles size={18} />
              <div><strong>Reference-to-Idea</strong><span>نفس الروح البصرية على فكرة مختلفة.</span></div>
            </div>
          </aside>
        </div>

        {job && (
          <section className="job-card">
            <div className="job-head">
              <div>
                <span className="eyebrow">المهمة {job.id.slice(0, 8)}</span>
                <h2>{job.message}</h2>
              </div>
              <strong className="progress-number">{job.progress}%</strong>
            </div>

            {job.reference_summary && <div className="reference-summary">{job.reference_summary}</div>}
            <div className="progress-track"><span style={{ width: `${job.progress}%` }} /></div>

            <div className="pipeline live-pipeline">
              {pipelineStages.map((stage, index) => {
                const currentIndex = pipelineStages.findIndex((item) => item.key === job.stage);
                const done = index < currentIndex || job.status === 'completed' || (job.status === 'waiting_review' && index === currentIndex);
                const active = index === currentIndex && !done;
                return (
                  <div className={`step ${done ? 'done' : ''} ${active ? 'active' : ''}`} key={stage.key}>
                    <span>{done ? <CheckCircle2 size={15} /> : index + 1}</span>
                    <strong>{stage.label}</strong>
                  </div>
                );
              })}
            </div>

            <GenerationOutput job={job} />

            {job.status === 'waiting_review' && (
              <div className="review-action">
                <div><strong>المرحلة الحالية جاهزة للمراجعة</strong><span>راجع الناتج بالأعلى، ثم وافق للاستمرار للمرحلة التالية.</span></div>
                <button className="cta" onClick={continueAfterReview} disabled={approving}>
                  {approving ? <LoaderCircle className="spin" size={18} /> : <CheckCircle2 size={18} />}
                  موافقة والاستمرار
                </button>
              </div>
            )}
          </section>
        )}
      </main>
    );
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="brand-badge"><Sparkles size={18} /> AI Content Studio</div>
        <h1>حوّل فكرة واحدة إلى فيديو جاهز للنشر.</h1>
        <p>من السكربت والصوت إلى المشاهد والمونتاج، ومع إمكانية الاستلهام من صورة أو فيديو مرجعي.</p>
        <button className="cta" onClick={() => setView('create')}><Film size={19} /> إنشاء فيديو جديد</button>
      </section>

      <section className="grid">
        {cards.map(({ title, subtitle, icon: Icon, primary, action }) => (
          <button type="button" className={`card ${primary ? 'card-primary' : ''}`} key={title} onClick={() => action === 'create' && setView('create')}>
            <div className="icon-wrap"><Icon size={24} /></div>
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </button>
        ))}
      </section>

      <section className="pipeline-card">
        <div><span className="eyebrow">خط الإنتاج</span><h2>٩ مراحل من الفكرة للنشر</h2></div>
        <div className="pipeline">
          {pipelineStages.map((step, index) => (
            <div className="step" key={step.key}><span>{index + 1}</span><strong>{step.label}</strong></div>
          ))}
        </div>
      </section>
    </main>
  );
}
