import { Link } from 'react-router-dom';
import PageSeo from '../components/PageSeo';
import { getStaticPageMeta, staticPageBreadcrumbs } from '../content/staticPageMeta';
import './Terms.css';

/**
 * אודות — שקיפות עסקית (פרטי רישום לעדכון בעת קבלת ח.פ. סופי).
 */
const AboutPage = () => {
  const meta = getStaticPageMeta('/about');
  return (
    <div className="terms-container">
      <PageSeo
        title={meta.title}
        description={meta.description}
        path="/about"
        breadcrumbs={staticPageBreadcrumbs('/about')}
      />
      <article className="terms-card">
        <h1 className="terms-title">אודות TradeTix</h1>
        <p style={{ textAlign: 'center', color: '#6b7280', marginBottom: '2rem' }}>
          זירת מסחר מאובטחת לכרטיסים בישראל
        </p>

        <section className="terms-section">
          <h2>מי אנחנו</h2>
          <p>
            TradeTix (טריידטיקס) היא זירת מסחר דיגיטלית מאובטחת לרכישה ומכירה של כרטיסים לאירועים
            בישראל — <strong>שוק משני (marketplace)</strong>. אנו מחברים בין מוכרים מאומתים לבין קונים,
            וגובים תשלום כבית העסק הרשום (Merchant of Record) באמצעות ספקי סליקה מורשים.
          </p>
          <p>
            <strong>מה אנחנו לא:</strong> TradeTix אינה המפיקה של האירוע, אינה בעלת האולם, ואינה מחליפה
            את הקופה הרשמית של המארגן. פרטי האירוע נקבעים על ידי המארגן הרשמי בלבד.
          </p>
        </section>

        <section className="terms-section">
          <h2>פרטי העסק (Business Identifiers)</h2>
          <ul>
            <li>
              <strong>שם מסחרי:</strong> TradeTix · טריידטיקס
            </li>
            <li>
              <strong>שם משפטי / עוסק:</strong> TradeTix (טריידטיקס) — פעילות בישראל
            </li>
            <li>
              <strong>מספר מזהה (ח.פ. / עוסק מורשה):</strong> יעודכן בפרסום הרשמי עם השלמת הרישום —
              לפניות דחופות:{' '}
              <Link to="/contact">צור קשר</Link>
            </li>
            <li>
              <strong>מדינה:</strong> ישראל
            </li>
            <li>
              <strong>סמכות שיפוט:</strong> בתי המשפט במחוז תל אביב-יפו (כמפורט בתקנון)
            </li>
            <li>
              <strong>תמיכה:</strong> עמוד <Link to="/contact">צור קשר</Link> · WhatsApp באתר
            </li>
          </ul>
          <p style={{ fontSize: '0.9rem', color: '#6b7280' }}>
            הערה: עם קבלת מספר ח.פ. / עוסק מורשה סופי, יעודכן סעיף זה באופן מיידי. עדכון זה נועד לשקיפות
            מול לקוחות בהתאם לציפיות הגנת הצרכן.
          </p>
        </section>

        <section className="terms-section">
          <h2>איך אנחנו מגנים על קונים ומוכרים</h2>
          <ul>
            <li>
              <strong>נאמנות (Escrow):</strong> כסף הקונה משוחרר למוכר רק 36 שעות לאחר האירוע, בכפוף
              לתקינות.
            </li>
            <li>
              <strong>הגנת הקונה:</strong> תהליך ברור להחזר בביטול אירוע או בכרטיס לא תקף —{' '}
              <Link to="/buyer-guarantee">למדיניות המלאה</Link>.
            </li>
            <li>
              <strong>שקיפות מחיר:</strong> דמי שירות לקונה מוצגים בקופה לפני התשלום.
            </li>
          </ul>
        </section>

        <section className="terms-section">
          <h2>מסמכים משפטיים</h2>
          <p>
            <Link to="/terms">תקנון ותנאי שימוש</Link> · <Link to="/privacy">מדיניות פרטיות</Link> ·{' '}
            <Link to="/refunds">ביטולים והחזרים</Link> ·{' '}
            <Link to="/buyer-guarantee">הגנת הקונה</Link> ·{' '}
            <Link to="/accessibility">הצהרת נגישות</Link> · <Link to="/faq">שאלות נפוצות</Link>.
          </p>
        </section>
      </article>
    </div>
  );
};

export default AboutPage;
