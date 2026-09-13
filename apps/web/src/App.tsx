import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Film,
  KeyRound,
  Lightbulb,
  LoaderCircle,
  Plus,
  Sparkles,
} from 'lucide-react';
import { approveJob, createJob, getJob, type JobStatus } from './api';
import { contentTypes, pipelineStages, platforms, type PlatformId } from './contentConfig';

type View = 'dashboard' | 'create';

const cards = [
  { title: 'فيديو جديد', subtitle: 'ابدأ من فكرة حتى التصدير', icon: Plus, primary: true, action: 'create' as const },
  { title: 'مكتبة الأفكار', subtitle: 'راجع المحتوى السابق ومنع التكرار', icon: Lightbulb },
  { title: 'المحتوى المجدول', subtitle: 'إدارة مواعيد النشر القادمة', icon: CalendarDays },
  { title: 'مصادر الخدمات', subtitle: 'إدارة مزودي الذكاء الاصطناعي وواجهات API', icon: KeyRound },
];

export function App() {
  const [view, setView] = useState<View>('dashboard');
  const [platformId, setPlatformId] = useState<PlatformId>('tiktok');
  const [contentType, setContentType] = useState('تعليمي');
  const [duration, setDuration] = useState(60);
  const [reviewEachStage, setReviewEachStage] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
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

  async function startJob() {
    setError('');
    setSubmitting(true);
    try {
      setJob(await createJob({
        platform: selectedPlatform.id,
        aspect_ratio: selectedPlatform.aspectRatio,
        duration_seconds: duration,
        content_type: contentType,
        review_each_stage: reviewEachStage,
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
          <h1>جهّز الفيديو، وسيبدأ خط الإنتاج تلقائيًا.</h1>
          <p>اختر المنصة ونوع المحتوى والمدة. المقاس المناسب يُحدد تلقائيًا حسب المنصة.</p>
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
                  <button className={`platform-option ${platform.id === platformId ? 'selected' : ''}`} key={platform.id} onClick={() => setPlatformId(platform.id)}>
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
                  <button className={`choice-chip ${contentType === type ? 'selected' : ''}`} key={type} onClick={() => setContentType(type)}>{type}</button>
                ))}
              </div>
            </div>

            <div className="field-group">
              <div className="field-heading">
                <div><span className="field-index">3</span><strong>مدة الفيديو</strong></div>
                <span className="duration-value">{duration < 60 ? `${duration} ثانية` : `${Math.floor(duration / 60)}:${String(duration % 60).padStart(2, '0')} دقيقة`}</span>
              </div>
              <input className="duration-slider" type="range" min="15" max="300" step="15" value={duration} onChange={(event) => setDuration(Number(event.target.value))} />
              <div className="range-labels"><span>15 ثانية</span><span>5 دقائق</span></div>
            </div>

            <label className="review-toggle">
              <div>
                <strong>مراجعة كل مرحلة قبل الاستمرار</strong>
                <span>عند التفعيل، يتوقف خط الإنتاج بعد كل مرحلة حتى توافق أو تعدّل النتيجة.</span>
              </div>
              <input type="checkbox" checked={reviewEachStage} onChange={(event) => setReviewEachStage(event.target.checked)} />
            </label>

            {error && <div className="error-box">{error}</div>}

            <button className="cta wide-cta" onClick={startJob} disabled={submitting || Boolean(job && !['completed', 'failed'].includes(job.status))}>
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
              <div><dt>المراجعة</dt><dd>{reviewEachStage ? 'مفعّلة' : 'تلقائي بالكامل'}</dd></div>
            </dl>
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
            {job.status === 'waiting_review' && (
              <div className="review-action">
                <div>
                  <strong>المرحلة الحالية جاهزة للمراجعة</strong>
                  <span>في المرحلة التالية سنعرض ناتج كل خطوة نفسه للتعديل أو إعادة التوليد.</span>
                </div>
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
        <p>من السكربت والصوت إلى المشاهد والترجمة والمونتاج — في مسار واحد واضح.</p>
        <button className="cta" onClick={() => setView('create')}><Film size={19} /> إنشاء فيديو جديد</button>
      </section>

      <section className="grid">
        {cards.map(({ title, subtitle, icon: Icon, primary, action }) => (
          <button className={`card ${primary ? 'card-primary' : ''}`} key={title} onClick={() => action === 'create' && setView('create')}>
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
