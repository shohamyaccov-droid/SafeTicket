import { Link } from 'react-router-dom';
import PageSeo from '../components/PageSeo';
import { getStaticPageMeta, staticPageBreadcrumbs } from '../content/staticPageMeta';
import './Terms.css';

const ACCESSIBILITY_EMAIL = 'tradetix.support@gmail.com';

/**
 * הצהרת נגישות — ת״י 5568 / WCAG 2.0 AA.
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
          עודכן לאחרונה: ספטמבר 2026
        </p>

        <section className="terms-section">
          <p>
            אנו בפלטפורמת TradeTix רואים חשיבות עליונה בהנגשת השירות שלנו לאנשים עם מוגבלות, על מנת
            לאפשר לכלל הציבור לגלוש ולסחור בנוחות ובשוויון.
          </p>
        </section>

        <section className="terms-section">
          <h2>התאמות נגישות באתר</h2>
          <p>
            האתר הותאם בהתאם להנחיות הנגישות לתקן הישראלי (ת&quot;י 5568) ולרמת AA. האתר תומך בניווט
            מקלדת, התאמת ניגודיות צבעים, ותגיות תיאור לתמונות וממשקים.
          </p>
          <p>
            בנוסף, בכל עמודי האתר זמין תפריט נגישות (הגדלת טקסט, ניגודיות גבוהה, הדגשת קישורים ועוד)
            וקישור &quot;דלג לתוכן הראשי&quot; למשתמשי מקלדת.
          </p>
        </section>

        <section className="terms-section">
          <h2>יצירת קשר בנושאי נגישות</h2>
          <p>
            אם נתקלתם בקושי כלשהו או בבעיית נגישות באתר, נשמח שתעדכנו אותנו כדי שנפעל לתקן זאת בהקדם.
            ניתן לפנות אלינו דרך עמוד <Link to="/contact">צור קשר</Link> באתר, או בדוא״ל{' '}
            <a href={`mailto:${ACCESSIBILITY_EMAIL}`}>{ACCESSIBILITY_EMAIL}</a>
            {' '}(נא לציין בנושא: &quot;נגישות&quot;).
          </p>
        </section>
      </article>
    </div>
  );
};

export default AccessibilityPage;
