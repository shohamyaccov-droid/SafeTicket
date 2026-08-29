import { Link } from 'react-router-dom';
import PageSeo from '../components/PageSeo';
import { getStaticPageMeta, staticPageBreadcrumbs } from '../content/staticPageMeta';
import './Terms.css';

/**
 * הגנת הקונה — נוסח משפטי מיושר עם תקנון + מטריצת החזרים.
 */
const BuyerGuaranteePage = () => {
  const meta = getStaticPageMeta('/buyer-guarantee');
  return (
    <div className="terms-container">
      <PageSeo
        title={meta.title}
        description={meta.description}
        path="/buyer-guarantee"
        breadcrumbs={staticPageBreadcrumbs('/buyer-guarantee')}
      />
      <article className="terms-card">
        <h1 className="terms-title">הגנת הקונה — TradeTix</h1>
        <p style={{ textAlign: 'center', color: '#6b7280', marginBottom: '2rem' }}>
          עודכן לאחרונה: יולי 2026 · כפוף ל
          <Link to="/terms"> תקנון</Link> ול
          <Link to="/refunds">מדיניות ההחזרים</Link>
        </p>

        <section className="terms-section">
          <h2>עקרון הליבה</h2>
          <p>
            עסקאות שנעשו באתר TradeTix מגובות במודל נאמנות (Escrow) ובהליך טיפול במחלוקות. אנחנו בית
            העסק הרשום מול הקונה בתשלום, אך <strong>איננו המפיקים</strong> של האירוע.
          </p>
          <p>
            כספי הקונה מוחזקים בנאמנות ואינם משוחררים למוכר באופן מיידי — אלא רק לאחר{' '}
            <strong>36 שעות מסיום האירוע</strong>, בכפוף לתקינות העסקה ולהיעדר תלונה מבוססת.
          </p>
        </section>

        <section className="terms-section">
          <h2>1) אספקת כרטיס בזמן</h2>
          <p>
            אם לא קיבלתם כרטיס דיגיטלי שניתן לשימוש במועד שנמסר, פנו אלינו לפני האירוע דרך{' '}
            <Link to="/contact">צור קשר</Link>. נפעל להשלמת האספקה או — אם לא ניתן לספק כרטיס תקף —
            להחזר של הסכום ששולם ל-TradeTix (כולל דמי שירות), בהתאם לנסיבות.
          </p>
        </section>

        <section className="terms-section">
          <h2>2) כרטיס שלא עבר בכניסה</h2>
          <ul>
            <li>צרו קשר מיד מהמקום (או עד שעה אחת מסיום האירוע).</li>
            <li>צרפו תיעוד: סרטון/צילום של הסריקה והודעת השגיאה.</li>
            <li>
              במקרה מאומת: <strong>החזר מלא</strong> של הסכום ששולם ל-TradeTix; המוכר לא יקבל תמלוג.
            </li>
          </ul>
        </section>

        <section className="terms-section">
          <h2>3) ביטול אירוע (לא דחייה)</h2>
          <p>
            אם המארגן מבטל את האירוע סופית וללא מועד חדש מחייב — תקבלו{' '}
            <strong>החזר מלא</strong> של מה ששולם ל-TradeTix (או זיכוי שווה ערך, אלא אם הדין מחייב
            החזר כספי). יעד: עד 10 ימי עסקים מאישור הביטול בפלטפורמה.
          </p>
        </section>

        <section className="terms-section">
          <h2>4) דחייה / מועד חדש</h2>
          <p>
            הכרטיס נשאר בתוקף למועד החדש. <strong>אין החזר אוטומטי</strong> בשל דחייה בלבד. ניתן למכור
            מחדש באתר אם אינכם יכולים להגיע.
          </p>
        </section>

        <section className="terms-section">
          <h2>מה לא כלול</h2>
          <ul>
            <li>טעות בבחירת מושבים מצד הקונה.</li>
            <li>אי הגעה לאירוע או שינוי תוכנייה שאינו ביטול סופי.</li>
            <li>נזקים עקיפים (נסיעות, מלון, אובדן הנאה) — בכפוף לדין.</li>
          </ul>
        </section>

        <section className="terms-section">
          <h2>מסמכים מלאים</h2>
          <p>
            <Link to="/refunds">ביטולים והחזרים</Link> · <Link to="/terms">תקנון</Link> ·{' '}
            <Link to="/faq">שאלות נפוצות</Link> · <Link to="/contact">צור קשר</Link>.
          </p>
        </section>
      </article>
    </div>
  );
};

export default BuyerGuaranteePage;
