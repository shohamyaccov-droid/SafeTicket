import { Link } from 'react-router-dom';
import PageSeo from '../components/PageSeo';
import { DEFAULT_SITE_TITLE } from '../utils/siteSeo';
import './Terms.css';

const HOW_IT_WORKS_DESCRIPTION =
  'איך קונים ומוכרים כרטיסים ב-TradeTix: בחירת אירוע, תשלום מאובטח, נאמנות כספית ומסירת PDF.';

const HowItWorksPage = () => {
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'HowTo',
    name: 'איך זה עובד ב-TradeTix',
    description: HOW_IT_WORKS_DESCRIPTION,
    step: [
      {
        '@type': 'HowToStep',
        name: 'בחירת אירוע',
        text: 'מחפשים הופעה או משחק ובוחרים מודעה עם מושב ומחיר.',
      },
      {
        '@type': 'HowToStep',
        name: 'תשלום מאובטח',
        text: 'משלמים ב-PayMe. הכסף נשמר בנאמנות עד לאחר האירוע.',
      },
      {
        '@type': 'HowToStep',
        name: 'קבלת הכרטיס',
        text: 'הקובץ הדיגיטלי נמסר למייל ולאזור האישי לאחר אישור התשלום.',
      },
    ],
  };

  return (
    <div className="terms-container">
      <PageSeo
        title={`איך זה עובד | ${DEFAULT_SITE_TITLE}`}
        description={HOW_IT_WORKS_DESCRIPTION}
        path="/how-it-works"
        jsonLd={jsonLd}
      />
      <article className="terms-card">
        <h1>איך זה עובד</h1>
        <p>
          TradeTix היא זירת מסחר משנית לכרטיסים בישראל. הקונים רוכשים ממוכרים מאומתים, והתשלום
          מוגן בנאמנות עד לאחר האירוע. העמוד הזה מסביר את התהליך לקונים ולמוכרים.
        </p>

        <section>
          <h2>קנייה של כרטיס</h2>
          <p>
            בוחרים אירוע, בודקים את המפה והמושבים, וממשיכים לתשלום מאובטח. לאחר האישור מתקבל קובץ
            PDF או ברקוד לשימוש בכניסה — בהתאם למודעה.
          </p>
          <p>
            אם המודעה כוללת כמה מושבים שנמכרים יחד, יש לרכוש את הכמות המוצגת. פירוט נוסף ב
            <Link to="/faq">שאלות ותשובות</Link>.
          </p>
        </section>

        <section>
          <h2>מכירת כרטיס</h2>
          <p>
            המוכר מעלה את הכרטיס, מאמת זהות וממתין לאישור המודעה. כשקונה משלם, הכסף לא מועבר מיד —
            הוא משוחרר רק 36 שעות לאחר האירוע, בכפוף לתקינות העסקה.
          </p>
          <p>
            להתחלת מכירה:{' '}
            <Link to="/sell/new">מכירת כרטיסים</Link>.
          </p>
        </section>

        <section>
          <h2>הגנה על הכסף</h2>
          <p>
            TradeTix אינה המפיקה של האירוע. אנחנו בית העסק הרשום מול הקונה, עם מדיניות החזרים ברורה
            לביטול סופי או לכרטיס שלא עבר בכניסה. ראו{' '}
            <Link to="/buyer-guarantee">הגנת הקונה</Link> ו־
            <Link to="/refunds">ביטולים והחזרים</Link>.
          </p>
        </section>
      </article>
    </div>
  );
};

export default HowItWorksPage;
