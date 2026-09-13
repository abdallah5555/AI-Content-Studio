import { useEffect, useState } from 'react';
import { ArrowRight, Clock3, Film, LoaderCircle, RefreshCw, Trash2 } from 'lucide-react';
import { deleteJob, getJob, listJobs, type JobStatus, type JobSummary } from './api';

type Props = {
  onBack: () => void;
  onOpen: (job: JobStatus) => void;
};

const statusLabels: Record<JobSummary['status'], string> = {
  queued: 'في الانتظار',
  running: 'جاري التنفيذ',
  waiting_review: 'بانتظار المراجعة',
  completed: 'مكتمل',
  failed: 'متوقف / فشل',
};

function formatDate(value: string) {
  try {
    return new Intl.DateTimeFormat('ar-EG', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export function JobHistory({ onBack, onOpen }: Props) {
  const [items, setItems] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [error, setError] = useState('');

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      setItems(await listJobs(100));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'تعذر تحميل سجل المشاريع.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function openJob(id: string) {
    setOpeningId(id);
    setError('');
    try {
      onOpen(await getJob(id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'تعذر فتح المشروع.');
    } finally {
      setOpeningId(null);
    }
  }

  async function removeJob(id: string) {
    setError('');
    try {
      await deleteJob(id);
      setItems((current) => current.filter((item) => item.id !== id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'تعذر حذف المشروع.');
    }
  }

  return (
    <main className="page-shell history-page">
      <button className="back-button" onClick={onBack}><ArrowRight size={18} /> العودة للوحة التحكم</button>

      <section className="history-heading">
        <div>
          <span className="eyebrow">المكتبة</span>
          <h1>المشاريع والأفكار السابقة</h1>
          <p>كل Job محفوظ في SQLite، بما فيه المرحلة الحالية والنواتج التي تم إنشاؤها.</p>
        </div>
        <button className="history-refresh" onClick={() => void refresh()} disabled={loading}>
          {loading ? <LoaderCircle className="spin" size={18} /> : <RefreshCw size={18} />}
          تحديث
        </button>
      </section>

      {error && <div className="error-box">{error}</div>}

      {loading ? (
        <div className="history-empty"><LoaderCircle className="spin" size={24} /> جاري تحميل المشاريع...</div>
      ) : items.length === 0 ? (
        <div className="history-empty"><Film size={28} /><strong>لسه مفيش مشاريع محفوظة</strong><span>أول فيديو تنشئه هيظهر هنا تلقائيًا.</span></div>
      ) : (
        <section className="history-grid">
          {items.map((item) => (
            <article className="history-card" key={item.id}>
              <div className="history-card-head">
                <div>
                  <span className={`history-status status-${item.status}`}>{statusLabels[item.status]}</span>
                  <h2>{item.title || `مشروع ${item.id.slice(0, 8)}`}</h2>
                </div>
                <strong>{item.progress}%</strong>
              </div>

              <div className="history-progress"><span style={{ width: `${item.progress}%` }} /></div>

              <div className="history-meta">
                <span><Clock3 size={14} /> {formatDate(item.updated_at)}</span>
                <span>المرحلة: {item.stage}</span>
              </div>

              <div className="history-actions">
                <button className="history-open" onClick={() => void openJob(item.id)} disabled={openingId === item.id}>
                  {openingId === item.id ? <LoaderCircle className="spin" size={16} /> : <Film size={16} />}
                  فتح المشروع
                </button>
                <button className="history-delete" onClick={() => void removeJob(item.id)} aria-label="حذف المشروع"><Trash2 size={16} /></button>
              </div>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
