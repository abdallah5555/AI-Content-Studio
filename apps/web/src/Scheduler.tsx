import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, CalendarDays, CheckCircle2, LoaderCircle, Trash2 } from 'lucide-react';
import { createSchedule, deleteSchedule, listJobs, listSchedule, updateScheduleStatus, type JobSummary, type ScheduledItem } from './api';

type Props = { onBack: () => void };

const platformOptions = ['tiktok', 'instagram', 'facebook', 'youtube', 'x'];

export function Scheduler({ onBack }: Props) {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [items, setItems] = useState<ScheduledItem[]>([]);
  const [jobId, setJobId] = useState('');
  const [platform, setPlatform] = useState('tiktok');
  const [scheduledAt, setScheduledAt] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function refresh() {
    setLoading(true); setError('');
    try {
      const [allJobs, scheduled] = await Promise.all([listJobs(100), listSchedule()]);
      const completed = allJobs.filter((job) => job.status === 'completed');
      setJobs(completed); setItems(scheduled);
      if (!jobId && completed[0]) setJobId(completed[0].id);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'تعذر تحميل جدول النشر.');
    } finally { setLoading(false); }
  }

  useEffect(() => { void refresh(); }, []);

  const selectedJob = useMemo(() => jobs.find((job) => job.id === jobId), [jobs, jobId]);

  async function addSchedule() {
    if (!jobId || !scheduledAt) { setError('اختار مشروع مكتمل وموعد النشر.'); return; }
    setSaving(true); setError('');
    try {
      await createSchedule({ job_id: jobId, platform, scheduled_at: new Date(scheduledAt).toISOString(), title: selectedJob?.title || '', notes });
      setNotes(''); setScheduledAt('');
      setItems(await listSchedule());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'تعذر حفظ الموعد.');
    } finally { setSaving(false); }
  }

  async function markPublished(item: ScheduledItem) {
    await updateScheduleStatus(item.id, 'published');
    setItems(await listSchedule());
  }

  async function remove(item: ScheduledItem) {
    await deleteSchedule(item.id);
    setItems((current) => current.filter((candidate) => candidate.id !== item.id));
  }

  return (
    <main className="page-shell scheduler-page">
      <button className="back-button" onClick={onBack}><ArrowRight size={18} /> العودة للوحة التحكم</button>
      <section className="settings-heading"><div><span className="eyebrow">Publishing Planner</span><h1>المحتوى المجدول</h1><p>جدول داخلي مجاني يحفظ مواعيد النشر للمشاريع المكتملة. النشر التلقائي للمنصات يفضل اختياريًا عند إضافة OAuth الرسمي.</p></div></section>
      {error && <div className="error-box">{error}</div>}

      <section className="settings-grid scheduler-grid">
        <article className="settings-card">
          <div className="settings-card-title"><CalendarDays size={20} /><div><span className="eyebrow">New schedule</span><h2>أضف موعد نشر</h2></div></div>
          {loading ? <div className="settings-empty"><LoaderCircle className="spin" size={20} /> جاري التحميل...</div> : jobs.length === 0 ? <div className="settings-empty">لا يوجد فيديو مكتمل بعد. أنشئ فيديو أولًا ثم ارجع هنا.</div> : (
            <div className="schedule-form">
              <label><span>المشروع</span><select value={jobId} onChange={(event) => setJobId(event.target.value)}>{jobs.map((job) => <option key={job.id} value={job.id}>{job.title || job.id.slice(0, 8)}</option>)}</select></label>
              <label><span>المنصة</span><select value={platform} onChange={(event) => setPlatform(event.target.value)}>{platformOptions.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
              <label><span>الموعد</span><input type="datetime-local" value={scheduledAt} onChange={(event) => setScheduledAt(event.target.value)} /></label>
              <label><span>ملاحظات</span><textarea rows={4} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="CTA، هاشتاجات، أو ملاحظات النشر..." /></label>
              <button className="cta" onClick={() => void addSchedule()} disabled={saving}>{saving ? <LoaderCircle className="spin" size={17} /> : <CalendarDays size={17} />} حفظ الموعد</button>
            </div>
          )}
        </article>

        <article className="settings-card">
          <div className="settings-card-title"><CalendarDays size={20} /><div><span className="eyebrow">Queue</span><h2>المواعيد القادمة</h2></div></div>
          <div className="schedule-list">
            {items.length === 0 ? <div className="settings-empty">لسه مفيش مواعيد محفوظة.</div> : items.map((item) => (
              <div className="schedule-row" key={item.id}>
                <div><strong>{item.title || `مشروع ${item.job_id.slice(0, 8)}`}</strong><span>{item.platform} · {new Date(item.scheduled_at).toLocaleString('ar-EG')}</span><small>{item.notes}</small></div>
                <div><span className={`schedule-status status-${item.status}`}>{item.status}</span>{item.status !== 'published' && <button onClick={() => void markPublished(item)} title="تم النشر"><CheckCircle2 size={16} /></button>}<button className="danger" onClick={() => void remove(item)}><Trash2 size={16} /></button></div>
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
