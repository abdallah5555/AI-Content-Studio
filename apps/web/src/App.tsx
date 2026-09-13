import { CalendarDays, Film, KeyRound, Lightbulb, Plus, Sparkles } from 'lucide-react';

const cards = [
  { title: 'فيديو جديد', subtitle: 'ابدأ من فكرة حتى التصدير', icon: Plus, primary: true },
  { title: 'مكتبة الأفكار', subtitle: 'راجع المحتوى السابق ومنع التكرار', icon: Lightbulb },
  { title: 'المحتوى المجدول', subtitle: 'إدارة مواعيد النشر القادمة', icon: CalendarDays },
  { title: 'مصادر الخدمات', subtitle: 'إدارة مزودي الذكاء الاصطناعي وواجهات API', icon: KeyRound },
];

const pipeline = [
  'توليد الفكرة', 'كتابة السكربت', 'تحويل النص لصوت', 'اختيار المشاهد',
  'المونتاج', 'المؤثرات', 'الموسيقى', 'التصدير', 'SEO والنشر'
];

export function App() {
  return (
    <main className="page-shell">
      <section className="hero">
        <div className="brand-badge"><Sparkles size={18} /> AI Content Studio</div>
        <h1>حوّل فكرة واحدة إلى فيديو جاهز للنشر.</h1>
        <p>من السكربت والصوت إلى المشاهد والترجمة والمونتاج — في مسار واحد واضح.</p>
        <button className="cta"><Film size={19} /> إنشاء فيديو جديد</button>
      </section>

      <section className="grid">
        {cards.map(({ title, subtitle, icon: Icon, primary }) => (
          <article className={`card ${primary ? 'card-primary' : ''}`} key={title}>
            <div className="icon-wrap"><Icon size={24} /></div>
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </article>
        ))}
      </section>

      <section className="pipeline-card">
        <div>
          <span className="eyebrow">خط الإنتاج</span>
          <h2>٩ مراحل من الفكرة للنشر</h2>
        </div>
        <div className="pipeline">
          {pipeline.map((step, index) => (
            <div className="step" key={step}>
              <span>{index + 1}</span>
              <strong>{step}</strong>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
