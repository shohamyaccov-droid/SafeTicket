import { Link } from 'react-router-dom';
import PageSeo from '../components/PageSeo';
import { getStaticPageMeta, staticPageBreadcrumbs } from '../content/staticPageMeta';
import './Terms.css';

/**
 * הצהרת נגישות — ציפייה מקובלת באתרים בישראל.
 */
const AccessibilityPage = () => {
  const meta = getStaticPageMeta('/accessibility');
  return (
    <div className="terms-container">
      <PageSeo
        title={meta.title}
        description={meta.description}
        path="/accessibility"
        breadcrumbs={staticPageBreadcrumbs('/accessibility')}
      />
      <article className="terms-card">
        <h1 className="terms-title">הצהרת נגישות</h1>
        <p style={{ textAlign: 'center', color: '#6b7280', marginBottom: '2rem' }}>
          עודכן לאחרונה: יולי 2026
        </p>

        <section className="terms-section">
          <h2>מחויבותנו</h2>
          <p>
            TradeTix שואפת להנגיש את האתר לכלל המשתמשים, לרבות אנשים עם מוגבלויות, בהתאם לעקרונות
            הנגישות המקובלים בישראל וליעדי WCAG ככל האפשר מבחינה טכנולוגית ועסקית.
          </p>
        </section>

        <section className="terms-section">
          <h2>פעולות שבוצעו / בתהליך</h2>
          <ul>
            <li>ממשק בעברית ובכיוון RTL.</li>
            <li>שמות נגישים (aria-label) לרכיבים מרכזיים ככל האפשר.</li>
            <li>יעדי גודל אזור לחיצה במובייל (כ-44×44 פיקסלים) ברכיבים מרכזיים.</li>
            <li>שיפורים מתמשכים בניגודיות, מקלדת וטקסט חלופי לתמונות.</li>
          </ul>
        </section>

        <section className="terms-section">
          <h2>ידועים מגבלות</h2>
          <p>
            חלקים מהאתר (למשל מפות אינטראקטיביות של אולמות, מסכי סליקה של ספק צד שלישי) עשויים להיות
            מוגבלים בנגישות. אנו פועלים לשיפור הדרגתי ולחלופות סבירות במקרים אלה.
          </p>
        </section>

        <section className="terms-section">
          <h2>פניות נגישות</h2>
          <p>
            נתקלתם בבעיית נגישות? דווחו לנו דרך עמוד <Link to="/contact">צור קשר</Link> וציינו
            &quot;נגישות&quot; בנושא הפנייה. נשתדל לחזור אליכם בהקדם ולתת מענה או חלופה סבירה.
          </p>
          <p>
            פרטי העסק: <Link to="/about">אודות TradeTix</Link>.
          </p>
        </section>
      </article>
    </div>
  );
};

export default AccessibilityPage;
