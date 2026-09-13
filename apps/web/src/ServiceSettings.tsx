import { ChangeEvent, useEffect, useState } from 'react';
import { ArrowRight, CheckCircle2, KeyRound, LoaderCircle, Music2, RefreshCw, UploadCloud, XCircle } from 'lucide-react';
import { getMusicLibrary, getProviderStatus, uploadMusic, type MusicTrack, type ProviderStatusResponse } from './api';

type Props = { onBack: () => void };

function prettySize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ServiceSettings({ onBack }: Props) {
  const [providers, setProviders] = useState<ProviderStatusResponse | null>(null);
  const [tracks, setTracks] = useState<MusicTrack[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  async function refresh() {
    setLoading(true); setError('');
    try {
      const [status, library] = await Promise.all([getProviderStatus(), getMusicLibrary()]);
      setProviders(status); setTracks(library);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'تعذر قراءة إعدادات الخدمات.');
    } finally { setLoading(false); }
  }

  useEffect(() => { void refresh(); }, []);

  async function handleMusic(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true); setError('');
    try {
      await uploadMusic(file);
      setTracks(await getMusicLibrary());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'تعذر رفع الملف الصوتي.');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  }

  return (
    <main className="page-shell settings-page">
      <button className="back-button" onClick={onBack}><ArrowRight size={18} /> العودة للوحة التحكم</button>
      <section className="settings-heading">
        <div><span className="eyebrow">Service Center</span><h1>مصادر الخدمات</h1><p>راقب المزود النشط وFailover ومكتبة الموسيقى بدون كشف أي API key في المتصفح.</p></div>
        <button className="settings-refresh" onClick={() => void refresh()} disabled={loading}>{loading ? <LoaderCircle className="spin" size={18} /> : <RefreshCw size={18} />} تحديث</button>
      </section>
      {error && <div className="error-box">{error}</div>}

      <section className="settings-grid">
        <article className="settings-card">
          <div className="settings-card-title"><KeyRound size={20} /><div><span className="eyebrow">Providers</span><h2>حالة الـAI والميديا</h2></div></div>
          {!providers ? <div className="settings-empty">جاري قراءة الحالة...</div> : (
            <div className="provider-list">
              {providers.providers.map((provider) => (
                <div className="provider-row" key={provider.id}>
                  <div>{provider.configured ? <CheckCircle2 size={18} /> : <XCircle size={18} />}<span><strong>{provider.label}</strong><small>{provider.capability} · أولوية {provider.priority}</small></span></div>
                  <span className={provider.configured ? 'provider-ready' : 'provider-missing'}>{provider.configured ? 'جاهز' : 'غير مضبوط'}</span>
                </div>
              ))}
              <div className="provider-summary"><span>Text active</span><strong>{providers.active.text || '—'}</strong><span>Media active</span><strong>{providers.active.media || '—'}</strong></div>
            </div>
          )}
        </article>

        <article className="settings-card">
          <div className="settings-card-title"><Music2 size={20} /><div><span className="eyebrow">Royalty-free library</span><h2>مكتبة الموسيقى</h2></div></div>
          <label className="music-upload"><input type="file" accept="audio/*,.mp3,.wav,.m4a,.aac,.ogg" onChange={handleMusic} disabled={uploading} />{uploading ? <LoaderCircle className="spin" size={22} /> : <UploadCloud size={22} />}<span><strong>ارفع موسيقى مرخصة أو من مكتبتك</strong><small>MP3 / WAV / M4A / AAC / OGG — بحد أقصى 80MB</small></span></label>
          <div className="music-list">
            {tracks.length === 0 ? <div className="settings-empty">المكتبة فاضية؛ مرحلة الموسيقى هتتخطى بأمان.</div> : tracks.map((track) => <div key={track.name}><span>{track.name}</span><small>{prettySize(track.size_bytes)}</small></div>)}
          </div>
        </article>
      </section>
    </main>
  );
}
