import { ArrowLeft, Check, Clock3, LockKeyhole, MessageCircleOff, ShieldCheck, Upload } from 'lucide-react';
import { Link } from 'react-router-dom';
import LaunchPromoBanner from '../components/LaunchPromoBanner';
import './SellLandingPage.css';

const HOW_IT_WORKS = [
  {
    title: 'מעלים את הכרטיס',
    text: 'בוחרים אירוע ומוסיפים את קובץ הכרטיס.',
    Icon: Upload,
  },
  {
    title: 'אנחנו מוצאים קונה',
    text: 'התשלום נשמר באופן מאובטח עד להשלמת העסקה.',
    Icon: LockKeyhole,
  },
  {
    title: 'מקבלים את הכסף',
    text: 'הזיכוי מועבר אליכם בהתאם לתנאי הנאמנות.',
    Icon: Check,
  },
];

export default function SellLandingPage() {
  return (
    <div className="sell-landing" dir="rtl">
      <header className="sell-landing__header">
        <Link to="/" className="sell-landing__brand" aria-label="TradeTix - דף הבית">
          Trade<span>Tix</span>
        </Link>
        <div className="sell-landing__secure">
          <ShieldCheck size={18} aria-hidden="true" />
          תהליך מאובטח
        </div>
      </header>

      <LaunchPromoBanner />

      <main>
        <section className="sell-landing__hero">
          <div className="sell-landing__hero-copy">
            <div className="sell-landing__badge">
              <Clock3 size={17} aria-hidden="true" />
              העלאה פשוטה בכ־2 דקות
            </div>
            <h1>מוכרים כרטיס בבטחה.<br />התשלום מוגן בנאמנות.</h1>
            <p className="sell-landing__lead">
              בלי להתווכח בקבוצות, בלי עשרות הודעות ובלי לנחש אם הקונה באמת ישלם.
              מעלים פעם אחת — TradeTix מטפלת בעסקה המאובטחת.
            </p>
            <Link className="sell-landing__cta" to="/sell/new">
              העלאת כרטיס עכשיו
              <ArrowLeft size={20} aria-hidden="true" />
            </Link>
            <p className="sell-landing__cta-note">
              <Check size={16} aria-hidden="true" />
              ללא עמלת מכירה · הפרטים נשמרים עד לסיום
            </p>
          </div>

          <aside className="sell-landing__relief-card" aria-label="הדרך הקלה למכור כרטיס">
            <div className="sell-landing__pain">
              <MessageCircleOff size={26} aria-hidden="true" />
              <div>
                <strong>לא עוד ״זה עדיין רלוונטי?״</strong>
                <span>לא מנהלים משא ומתן עם זרים בצ׳אט</span>
              </div>
            </div>
            <div className="sell-landing__payment-card">
              <span className="sell-landing__payment-icon"><LockKeyhole size={25} /></span>
              <span>תשלום קונה</span>
              <strong>מוגן בנאמנות</strong>
              <small>אנחנו מחזיקים את התשלום באופן מאובטח עד להשלמת העסקה</small>
            </div>
          </aside>
        </section>

        <section className="sell-landing__steps" aria-labelledby="sell-how-title">
          <p className="sell-landing__section-kicker">פשוט, שקוף ומאובטח</p>
          <h2 id="sell-how-title">איך זה עובד?</h2>
          <div className="sell-landing__steps-grid">
            {HOW_IT_WORKS.map(({ title, text, Icon }, index) => (
              <article className="sell-landing__step" key={title}>
                <span className="sell-landing__step-number">{index + 1}</span>
                <span className="sell-landing__step-icon"><Icon size={25} /></span>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
          <Link className="sell-landing__cta sell-landing__cta--secondary" to="/sell/new">
            העלאת כרטיס עכשיו
            <ArrowLeft size={20} aria-hidden="true" />
          </Link>
        </section>
      </main>
    </div>
  );
}
