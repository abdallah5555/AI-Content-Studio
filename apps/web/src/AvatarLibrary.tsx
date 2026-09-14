import { ChangeEvent, useEffect, useState } from 'react';
import { ArrowRight, CheckCircle2, ImagePlus, LoaderCircle, RefreshCw, Save, UserRound } from 'lucide-react';
import { resolveWorkerUrl, uploadReference, type UploadedReference } from './api';

type AvatarProfile = {
  name: string;
  description: string;
  persona_type: 'self' | 'creator' | 'brand_mascot' | 'character';
  style: string;
  default_wardrobe: string;
  speaking_style: string;
  reference_id?: string;
  identity_anchor?: string;
};

type AvatarItem = {
  reference_id: string;
  reference_name: string;
  kind: string;
  analysis_status: string;
  profile: AvatarProfile;
  visual_identity?: Record<string, unknown>;
};

type Props = {
  onBack: () => void;
  onUseAvatar?: (avatar: AvatarItem) => void;
};

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(await response.text() || `Request failed with ${response.status}`);
  return response.json() as Promise<T>;
}

export function AvatarLibrary({ onBack, onUseAvatar }: Props) {
  const [avatars, setAvatars] = useState<AvatarItem[]>([]);
  const [reference, setReference] = useState<UploadedReference | null>(null);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [profile, setProfile] = useState<AvatarProfile>({
    name: '', description: '', persona_type: 'self', style: 'natural', default_wardrobe: '', speaking_style: 'مصري بسيط وطبيعي',
  });

  async function loadAvatars() {
    setError('');
    try {
      const result = await parseResponse<{ avatars: AvatarItem[] }>(await fetch(resolveWorkerUrl('/references/avatar-library')));
      setAvatars(result.avatars || []);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'تعذر تحميل مكتبة الأفاتارات.');
    }
  }

  useEffect(() => { void loadAvatars(); }, []);

  async function handleImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true); setError('');
    try {
      const uploaded = await uploadReference(file);
      setReference(uploaded);
      if (!profile.name.trim()) setProfile((current) => ({ ...current, name: file.name.replace(/\.[^.]+$/, '') }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'تعذر رفع صورة الأفاتار.');
    } finally {
      setUploading(false); event.target.value = '';
    }
  }

  async function saveAvatar() {
    if (!reference) { setError('ارفع صورة واضحة للأفاتار الأول.'); return; }
    if (!profile.name.trim()) { setError('اكتب اسم للأفاتار.'); return; }
    setSaving(true); setError('');
    try {
      await parseResponse(await fetch(resolveWorkerUrl(`/references/${reference.id}/avatar-profile`), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...profile, name: profile.name.trim() }),
      }));
      setReference(null);
      setProfile({ name: '', description: '', persona_type: 'self', style: 'natural', default_wardrobe: '', speaking_style: 'مصري بسيط وطبيعي' });
      await loadAvatars();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'تعذر حفظ الأفاتار.');
    } finally { setSaving(false); }
  }

  return (
    <main className="page-shell avatar-page">
      <button className="back-button" onClick={onBack}><ArrowRight size={18} /> العودة للوحة التحكم</button>
      <section className="create-heading"><div className="brand-badge"><UserRound size={18} /> Avatar Library</div><h1>اعمل شخصيتك مرة واستخدمها في فيديوهاتك بعد كده.</h1><p>ارفع صورة واضحة، احفظ هوية الشخصية، وبعدها نستخدم نفس المرجع وCharacter DNA كأساس للمشاهد المولدة بالذكاء الاصطناعي.</p></section>

      <div className="creator-layout avatar-layout">
        <section className="form-card">
          <div className="field-group"><div className="field-heading"><div><span className="field-index">1</span><strong>الصورة الأساسية</strong></div></div>
            <label className="upload-box"><input type="file" accept="image/*" onChange={handleImage} disabled={uploading} />{uploading ? <LoaderCircle className="spin" size={24} /> : <ImagePlus size={24} />}<div><strong>ارفع صورة واضحة</strong><span>يفضل الوجه واضح وإضاءة جيدة ومن غير فلتر قوي.</span></div></label>
            {reference && <div className="reference-item"><div><strong>{reference.name}</strong><span>{reference.analysis_status === 'ready' ? 'تم تحليل الهوية البصرية' : reference.analysis_status}</span></div>{reference.analysis_status === 'ready' && <CheckCircle2 size={18} />}</div>}
          </div>

          <div className="field-group"><div className="field-heading"><div><span className="field-index">2</span><strong>هوية الأفاتار</strong></div></div>
            <div className="avatar-form-grid">
              <input value={profile.name} onChange={(e) => setProfile((v) => ({ ...v, name: e.target.value }))} placeholder="اسم الأفاتار: عبدالله مثلاً" />
              <select value={profile.persona_type} onChange={(e) => setProfile((v) => ({ ...v, persona_type: e.target.value as AvatarProfile['persona_type'] }))}><option value="self">أنا شخصيًا</option><option value="creator">مقدم محتوى</option><option value="brand_mascot">ماسكوت براند</option><option value="character">شخصية AI</option></select>
              <input value={profile.style} onChange={(e) => setProfile((v) => ({ ...v, style: e.target.value }))} placeholder="الستايل: واقعي / 3D / سينمائي..." />
              <input value={profile.default_wardrobe} onChange={(e) => setProfile((v) => ({ ...v, default_wardrobe: e.target.value }))} placeholder="ملابس افتراضية" />
            </div>
            <textarea className="prompt-area" rows={4} value={profile.description} onChange={(e) => setProfile((v) => ({ ...v, description: e.target.value }))} placeholder="وصف الشخصية وطريقتها وشكل الفيديو اللي تحبه..." />
            <input className="avatar-wide-input" value={profile.speaking_style} onChange={(e) => setProfile((v) => ({ ...v, speaking_style: e.target.value }))} placeholder="طريقة الكلام" />
          </div>
          {error && <div className="error-box">{error}</div>}
          <button className="cta wide-cta" onClick={() => void saveAvatar()} disabled={saving || uploading}>{saving ? <LoaderCircle className="spin" size={19} /> : <Save size={19} />} حفظ الأفاتار</button>
        </section>

        <aside className="summary-card avatar-summary"><div className="generation-output-head"><span className="eyebrow">المحفوظ</span><button className="icon-button" onClick={() => void loadAvatars()} aria-label="تحديث"><RefreshCw size={16} /></button></div><h2>{avatars.length} أفاتار</h2><p>الصور محفوظة في التخزين الخاص، والملف الشخصي مرتبط بالمرجع نفسه.</p></aside>
      </div>

      <section className="avatar-library-grid">
        {avatars.map((avatar) => <article className="avatar-card" key={avatar.reference_id}><div className="avatar-card-icon"><UserRound size={28} /></div><div><span className="eyebrow">{avatar.profile.persona_type}</span><h3>{avatar.profile.name}</h3><p>{avatar.profile.description || 'أفاتار محفوظ وجاهز للاستخدام في خط الإنتاج.'}</p><div className="avatar-tags"><span>{avatar.profile.style}</span>{avatar.profile.default_wardrobe && <span>{avatar.profile.default_wardrobe}</span>}</div></div>{onUseAvatar && <button className="intel-primary" onClick={() => onUseAvatar(avatar)}>استخدم في فيديو جديد</button>}</article>)}
        {avatars.length === 0 && <div className="intel-empty">لسه مفيش أفاتارات محفوظة. ارفع أول صورة من فوق.</div>}
      </section>
    </main>
  );
}
