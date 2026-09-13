import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  Bookmark,
  BookmarkCheck,
  BrainCircuit,
  CalendarRange,
  ChartNoAxesCombined,
  Flame,
  Inbox,
  Lightbulb,
  LoaderCircle,
  Radar,
  RefreshCw,
  Save,
  Sparkles,
  Trash2,
  WandSparkles,
} from 'lucide-react';
import {
  addIdeaInbox,
  deleteIdeaInbox,
  getBrandProfile,
  getTrends,
  listIdeaInbox,
  listTrendWatchlist,
  recordPerformance,
  refreshTrends,
  runIntelligenceTool,
  saveBrandProfile,
  unwatchTrend,
  watchTrend,
  type IdeaInboxItem,
  type IntelligenceResult,
  type TrendItem,
} from './api';

type Tab = 'radar' | 'tools' | 'inbox' | 'brand' | 'learn';

type Props = {
  onBack: () => void;
  onUseIdea: (idea: string) => void;
};

const lifecycleLabels: Record<string, string> = {
  early: '🟢 بدري جدًا',
  rising: '🔥 صاعد بسرعة',
  strong: '⚡ قوي الآن',
  saturated: '🔴 متشبع',
  cooling: '🟡 بيهدأ',
};

const tools = [
  { id: 'content_gap', label: 'Content Gap Finder', hint: 'اكتشف المواضيع اللي عليها طلب والمحتوى فيها ضعيف.', icon: Radar },
  { id: 'competitor', label: 'Competitor Analyzer', hint: 'حلل أنماط المنافسين واستخرج فجوات وأفكار أصلية بدون نسخ.', icon: BrainCircuit },
  { id: 'hooks', label: 'Viral Hook Lab', hint: 'ولّد Hooks كثيرة وقيمها قبل التصوير.', icon: Flame },
  { id: 'series', label: 'Content Series', hint: 'حوّل موضوع واحد لسلسلة 7–30 حلقة.', icon: CalendarRange },
  { id: 'repurpose', label: 'Repurpose Engine', hint: 'حوّل محتوى طويل إلى Shorts وPosts وQuotes.', icon: RefreshCw },
  { id: 'evergreen', label: 'Evergreen Radar', hint: 'أفكار تعيش وتجيب مشاهدات بعيدًا عن الترند.', icon: Lightbulb },
  { id: 'audience', label: 'Audience Persona', hint: 'خصص المحتوى حسب الجمهور واللهجة والمنصة.', icon: BrainCircuit },
  { id: 'calendar', label: 'Content Calendar', hint: 'ابنِ خطة أسبوعية أو شهرية موزونة.', icon: CalendarRange },
  { id: 'idea_score', label: 'Idea Score', hint: 'قيم الفكرة قبل ما تصرف وقت على إنتاجها.', icon: ChartNoAxesCombined },
  { id: 'ab_variants', label: 'A/B Generator', hint: 'اعمل نسخ مختلفة من أول ثواني والعنوان والـHook.', icon: Sparkles },
  { id: 'comments', label: 'Comment-to-Content', hint: 'حوّل تعليقات وأسئلة الجمهور لأفكار فيديوهات.', icon: Inbox },
  { id: 'research', label: 'Research Mode', hint: 'ابحث عن مصادر وميّز بين المعلومة المؤكدة والأسئلة المفتوحة.', icon: BrainCircuit },
  { id: 'winning_patterns', label: 'Winning Patterns', hint: 'اتعلم من نتائج فيديوهاتك السابقة واقترح الاختبار التالي.', icon: ChartNoAxesCombined },
  { id: 'trend_remix', label: 'Trend Remix', hint: 'حوّل ميكانيكية الترند لفكرة أصلية خاصة بيك من غير نسخ التنفيذ.', icon: Flame },
];

function formatNumber(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value || 0);
}

function TrendCard({ trend, watched, onToggleWatch, onRemix }: { trend: TrendItem; watched: boolean; onToggleWatch: (trend: TrendItem) => void; onRemix: (trend: TrendItem) => void }) {
  return (
    <article className="trend-card">
      <div className="trend-card-head">
        <span className={`trend-score score-${Math.floor(trend.score / 20)}`}>{trend.score}/100</span>
        <button className="icon-button" onClick={() => onToggleWatch(trend)} aria-label={watched ? 'إزالة من المتابعة' : 'إضافة للمتابعة'}>{watched ? <BookmarkCheck size={19} /> : <Bookmark size={19} />}</button>
      </div>
      <h3>{trend.title}</h3>
      <span className="trend-life">{lifecycleLabels[trend.lifecycle] || trend.lifecycle}</span>
      <div className="trend-metrics">
        <div><span>بحث</span><strong>{trend.traffic_label || formatNumber(trend.traffic)}</strong></div>
        <div><span>السرعة</span><strong>{trend.velocity_score}</strong></div>
        <div><span>التشبع</span><strong>{trend.saturation_score}</strong></div>
        <div><span>العمر</span><strong>{trend.age_hours} س</strong></div>
      </div>
      <button className="intel-primary" onClick={() => onRemix(trend)}><Sparkles size={17} /> اركب التريند بفكرة أصلية</button>
    </article>
  );
}

function ResultViewer({ result, onUseIdea }: { result: IntelligenceResult | null; onUseIdea: (idea: string) => void }) {
  if (!result) return null;
  const pretty = JSON.stringify(result.content, null, 2);
  const content = result.content as Record<string, unknown>;
  let suggested = '';
  if (typeof content.recommended_idea === 'string') suggested = content.recommended_idea;
  else if (typeof content.improved_idea === 'string') suggested = content.improved_idea;
  else if (typeof content.best_hook === 'string') suggested = content.best_hook;
  else if (typeof content.series_title === 'string') suggested = content.series_title;

  return (
    <section className="intel-result">
      <div className="intel-result-head"><div><span>الناتج</span><strong>{result.provider || 'AI'}</strong></div>{suggested && <button className="intel-primary small" onClick={() => onUseIdea(suggested)}>استخدم كفكرة فيديو</button>}</div>
      <pre>{pretty}</pre>
      {result.failover_log && result.failover_log.length > 0 && <details><summary>تفاصيل التحويل بين المزودين</summary><ul>{result.failover_log.map((entry) => <li key={entry}>{entry}</li>)}</ul></details>}
    </section>
  );
}

export function ContentIntelligence({ onBack, onUseIdea }: Props) {
  const [tab, setTab] = useState<Tab>('radar');
  const [geo, setGeo] = useState('EG');
  const [trends, setTrends] = useState<TrendItem[]>([]);
  const [watchlist, setWatchlist] = useState<TrendItem[]>([]);
  const [trendBusy, setTrendBusy] = useState(false);
  const [error, setError] = useState('');
  const [selectedTool, setSelectedTool] = useState('content_gap');
  const [toolInput, setToolInput] = useState('');
  const [audience, setAudience] = useState('');
  const [platform, setPlatform] = useState('TikTok / Reels');
  const [toolBusy, setToolBusy] = useState(false);
  const [result, setResult] = useState<IntelligenceResult | null>(null);
  const [ideas, setIdeas] = useState<IdeaInboxItem[]>([]);
  const [newIdea, setNewIdea] = useState('');
  const [brandText, setBrandText] = useState('{}');
  const [brandDescription, setBrandDescription] = useState('');
  const [brandBusy, setBrandBusy] = useState(false);
  const [performance, setPerformance] = useState({ title: '', views: '', likes: '', comments: '', shares: '', hook: '' });

  const watchedKeys = useMemo(() => new Set(watchlist.map((item) => item.key)), [watchlist]);
  const selectedToolMeta = tools.find((tool) => tool.id === selectedTool) || tools[0];

  useEffect(() => { void loadRadar(); void loadInbox(); void loadBrand(); }, []);

  async function loadRadar(force = false) {
    setTrendBusy(true); setError('');
    try {
      const [trendItems, watched] = await Promise.all([force ? refreshTrends(geo, 30) : getTrends(geo, 30), listTrendWatchlist()]);
      setTrends(trendItems); setWatchlist(watched);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'تعذر تحميل التريندات.'); }
    finally { setTrendBusy(false); }
  }

  async function toggleWatch(trend: TrendItem) {
    try {
      if (watchedKeys.has(trend.key)) await unwatchTrend(trend.key); else await watchTrend(trend, geo);
      setWatchlist(await listTrendWatchlist());
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'تعذر تحديث قائمة المتابعة.'); }
  }

  async function remixTrend(trend: TrendItem) {
    setSelectedTool('trend_remix'); setToolInput(trend.title); setToolBusy(true); setResult(null); setError('');
    try { setResult(await runIntelligenceTool('trend_remix', trend.title, { context: { trend }, platform, audience })); setTab('tools'); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'تعذر تحليل التريند.'); }
    finally { setToolBusy(false); }
  }

  async function runTool() {
    if (!toolInput.trim() && selectedTool !== 'winning_patterns') { setError('اكتب الموضوع أو المحتوى اللي عايز الأداة تشتغل عليه.'); return; }
    setToolBusy(true); setResult(null); setError('');
    try { setResult(await runIntelligenceTool(selectedTool, toolInput.trim() || 'حلل نتائج المحتوى المسجلة', { platform, audience })); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'تعذر تشغيل أداة الذكاء المحتوائي.'); }
    finally { setToolBusy(false); }
  }

  async function loadInbox() { try { setIdeas(await listIdeaInbox()); } catch { /* optional */ } }
  async function saveIdea() { if (!newIdea.trim()) return; try { await addIdeaInbox(newIdea.trim()); setNewIdea(''); await loadInbox(); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'تعذر حفظ الفكرة.'); } }
  async function removeIdea(id: string) { await deleteIdeaInbox(id); await loadInbox(); }
  async function loadBrand() { try { setBrandText(JSON.stringify(await getBrandProfile(), null, 2)); } catch { /* optional */ } }

  async function persistBrand() {
    setBrandBusy(true); setError('');
    try { await saveBrandProfile(JSON.parse(brandText) as Record<string, unknown>); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'تأكد إن Brand DNA مكتوب بصيغة JSON صحيحة.'); }
    finally { setBrandBusy(false); }
  }

  async function learnBrandFromDescription() {
    if (!brandDescription.trim()) { setError('اكتب وصف أسلوبك أو أمثلة من محتواك الأول.'); return; }
    setBrandBusy(true); setError('');
    try {
      const generated = await runIntelligenceTool('brand_dna', brandDescription.trim(), { platform, audience });
      setBrandText(JSON.stringify(generated.content, null, 2)); setResult(generated); await saveBrandProfile(generated.content);
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'تعذر استخراج Brand DNA.'); }
    finally { setBrandBusy(false); }
  }

  async function savePerformance() {
    if (!performance.title.trim()) { setError('اكتب اسم الفيديو أو وصفه.'); return; }
    try {
      await recordPerformance({ title: performance.title, views: Number(performance.views || 0), likes: Number(performance.likes || 0), comments: Number(performance.comments || 0), shares: Number(performance.shares || 0), hook: performance.hook || null, platform });
      setPerformance({ title: '', views: '', likes: '', comments: '', shares: '', hook: '' }); setError('');
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : 'تعذر حفظ نتيجة الفيديو.'); }
  }

  return (
    <main className="page-shell intel-page">
      <button className="back-button" onClick={onBack}><ArrowRight size={18} /> العودة للوحة التحكم</button>
      <section className="intel-hero"><div className="brand-badge"><Radar size={18} /> Content Intelligence Suite</div><h1>اعرف تعمل إيه، إمتى، ولمين — قبل ما تبدأ الإنتاج.</h1><p>رادار تريندات مجاني + فجوات محتوى + منافسين + Hooks + سلاسل + تخطيط + ذاكرة تتعلم من نتائجك.</p></section>
      <nav className="intel-tabs">
        <button className={tab === 'radar' ? 'active' : ''} onClick={() => setTab('radar')}><Radar size={17} /> رادار التريند</button>
        <button className={tab === 'tools' ? 'active' : ''} onClick={() => setTab('tools')}><WandSparkles size={17} /> أدوات الأفكار</button>
        <button className={tab === 'inbox' ? 'active' : ''} onClick={() => setTab('inbox')}><Inbox size={17} /> Idea Inbox</button>
        <button className={tab === 'brand' ? 'active' : ''} onClick={() => setTab('brand')}><BrainCircuit size={17} /> Brand DNA</button>
        <button className={tab === 'learn' ? 'active' : ''} onClick={() => setTab('learn')}><ChartNoAxesCombined size={17} /> يتعلم من أدائك</button>
      </nav>
      {error && <div className="error-box intel-error">{error}</div>}

      {tab === 'radar' && <section className="intel-section">
        <div className="intel-toolbar"><div><span className="eyebrow">Trend Radar</span><h2>الفرص اللي بتتحرك دلوقتي</h2></div><div className="intel-toolbar-actions"><select value={geo} onChange={(event) => setGeo(event.target.value)}><option value="EG">مصر</option><option value="SA">السعودية</option><option value="AE">الإمارات</option><option value="US">عالمي/US</option></select><button className="intel-secondary" onClick={() => void loadRadar(true)} disabled={trendBusy}>{trendBusy ? <LoaderCircle className="spin" size={17} /> : <RefreshCw size={17} />} تحديث</button></div></div>
        <div className="trend-grid">{trends.map((trend) => <TrendCard key={trend.key} trend={trend} watched={watchedKeys.has(trend.key)} onToggleWatch={(item) => void toggleWatch(item)} onRemix={(item) => void remixTrend(item)} />)}</div>
        {!trendBusy && trends.length === 0 && <div className="intel-empty">مفيش بيانات تريند متاحة من المصدر المجاني حاليًا. جرّب تحديث الصفحة بعد قليل.</div>}
        <div className="watchlist-section"><div className="intel-toolbar compact"><div><span className="eyebrow">Watchlist</span><h2>متابَع الآن</h2></div><span className="watch-count">{watchlist.length} تريند</span></div>{watchlist.length > 0 ? <div className="trend-grid watch-grid">{watchlist.map((trend) => <TrendCard key={`watch-${trend.key}`} trend={trend} watched onToggleWatch={(item) => void toggleWatch(item)} onRemix={(item) => void remixTrend(item)} />)}</div> : <div className="intel-empty">احفظ أي تريند بعلامة الـBookmark وهتلاقيه هنا حتى لو خرج من القائمة الحالية.</div>}</div>
      </section>}

      {tab === 'tools' && <section className="intel-tools-layout"><aside className="intel-tool-list">{tools.map(({ id, label, hint, icon: Icon }) => <button className={selectedTool === id ? 'active' : ''} key={id} onClick={() => { setSelectedTool(id); setResult(null); }}><Icon size={18} /><div><strong>{label}</strong><span>{hint}</span></div></button>)}</aside><section className="intel-workbench"><span className="eyebrow">{selectedToolMeta.label}</span><h2>{selectedToolMeta.hint}</h2><textarea value={toolInput} onChange={(event) => setToolInput(event.target.value)} rows={7} placeholder={selectedTool === 'competitor' ? 'الصق أمثلة عناوين أو Hooks أو Transcript أو وصف حساب المنافس...' : 'اكتب الفكرة، المجال، السكربت، التعليقات، أو المحتوى اللي عايز تحلله...'} /><div className="intel-inline-fields"><input value={audience} onChange={(event) => setAudience(event.target.value)} placeholder="الجمهور: مثال شباب مصر 18–30" /><input value={platform} onChange={(event) => setPlatform(event.target.value)} placeholder="المنصة" /></div><div className="intel-actions"><button className="intel-primary" onClick={() => void runTool()} disabled={toolBusy}>{toolBusy ? <LoaderCircle className="spin" size={17} /> : <WandSparkles size={17} />} تشغيل الأداة</button>{toolInput.trim() && <button className="intel-secondary" onClick={() => onUseIdea(toolInput.trim())}>ابدأ فيديو من النص الحالي</button>}</div><ResultViewer result={result} onUseIdea={onUseIdea} /></section></section>}

      {tab === 'inbox' && <section className="intel-section"><div className="intel-toolbar"><div><span className="eyebrow">Idea Inbox</span><h2>ارمي أي فكرة قبل ما تنساها</h2></div></div><div className="idea-capture"><textarea value={newIdea} onChange={(event) => setNewIdea(event.target.value)} rows={3} placeholder="فكرة سريعة..." /><button className="intel-primary" onClick={() => void saveIdea()}><Save size={17} /> حفظ</button></div><div className="idea-list">{ideas.map((idea) => <article key={idea.id}><div><strong>{idea.text}</strong><span>{new Date(idea.created_at).toLocaleString('ar-EG')}</span></div><div className="idea-actions"><button onClick={() => onUseIdea(idea.text)}>حوّل لفيديو</button><button onClick={() => { setToolInput(idea.text); setSelectedTool('idea_score'); setTab('tools'); }}>قيّمها</button><button className="danger" onClick={() => void removeIdea(idea.id)}><Trash2 size={15} /></button></div></article>)}</div></section>}

      {tab === 'brand' && <section className="intel-tools-layout brand-layout"><section className="intel-workbench"><span className="eyebrow">Brand DNA</span><h2>خلي كل فيديو له نفس شخصيتك حتى لو الموضوع مختلف.</h2><p className="intel-note">اكتب وصف أسلوبك، أمثلة Hooks بتحبها، لهجتك، نوع جمهورك، والألوان أو شكل الفيديو. الذكاء الاصطناعي يحول الوصف لـDNA محفوظ.</p><textarea className="brand-description" value={brandDescription} onChange={(event) => setBrandDescription(event.target.value)} rows={5} placeholder="مثال: بتكلم بالمصري البسيط، أحب بداية صادمة من غير مبالغة، الفيديو سريع، والألوان غامقة مع بنفسجي..." /><div className="intel-actions"><button className="intel-secondary" onClick={() => void learnBrandFromDescription()} disabled={brandBusy}>{brandBusy ? <LoaderCircle className="spin" size={17} /> : <BrainCircuit size={17} />} استخرج Brand DNA من الوصف</button></div><textarea className="brand-editor" value={brandText} onChange={(event) => setBrandText(event.target.value)} rows={18} spellCheck={false} /><div className="intel-actions"><button className="intel-primary" onClick={() => void persistBrand()} disabled={brandBusy}>{brandBusy ? <LoaderCircle className="spin" size={17} /> : <Save size={17} />} حفظ Brand DNA</button></div></section></section>}

      {tab === 'learn' && <section className="intel-tools-layout brand-layout"><section className="intel-workbench"><span className="eyebrow">Winning Pattern Memory</span><h2>سجل نتيجة كل فيديو، وسيبدأ التطبيق يتعلم إيه اللي بينجح عندك.</h2><div className="performance-grid"><input value={performance.title} onChange={(e) => setPerformance((v) => ({ ...v, title: e.target.value }))} placeholder="اسم/موضوع الفيديو" /><input value={performance.views} onChange={(e) => setPerformance((v) => ({ ...v, views: e.target.value }))} placeholder="Views" inputMode="numeric" /><input value={performance.likes} onChange={(e) => setPerformance((v) => ({ ...v, likes: e.target.value }))} placeholder="Likes" inputMode="numeric" /><input value={performance.comments} onChange={(e) => setPerformance((v) => ({ ...v, comments: e.target.value }))} placeholder="Comments" inputMode="numeric" /><input value={performance.shares} onChange={(e) => setPerformance((v) => ({ ...v, shares: e.target.value }))} placeholder="Shares" inputMode="numeric" /><input value={performance.hook} onChange={(e) => setPerformance((v) => ({ ...v, hook: e.target.value }))} placeholder="الـHook المستخدم" /></div><div className="intel-actions"><button className="intel-primary" onClick={() => void savePerformance()}><Save size={17} /> سجل النتيجة</button><button className="intel-secondary" onClick={() => { setSelectedTool('winning_patterns'); setToolInput('حلل كل نتائج المحتوى المسجلة واستخرج الأنماط الفائزة والاختبارات القادمة'); setTab('tools'); }}>حلل الأنماط الفائزة</button></div></section></section>}
    </main>
  );
}
