import { Link } from 'react-router-dom';
import PageSeo from '../components/PageSeo';
import { getStaticPageMeta, staticPageBreadcrumbs } from '../content/staticPageMeta';
import './Terms.css';

const ACCESSIBILITY_EMAIL = 'tradetix.support@gmail.com';

/**
 * הצהרת נגישות — בהתאם לתקנות שוויון זכויות לאנשים עם מוגבלות (התאמות נגישות לשירות)
 * ולתקן הישראלי ת״י 5568 (מבוסס WCAG 2.0 AA).
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
          <h2>1. מחויבותנו לנגישות</h2>
          <p>
            TradeTix (טריידטיקס) רואה חשיבות עליונה במתן שירות שוויוני, מכובד ונגיש לכלל ציבור
            המשתמשים, לרבות אנשים עם מוגבלויות. אנו פועלים להנגשת האתר בהתאם לחוק שוויון זכויות
            לאנשים עם מוגבלות, התשנ&quot;ח–1998, לתקנות שוויון זכויות לאנשים עם מוגבלות (התאמות נגישות
            לשירות), התשע&quot;ג–2013, ולתקן הישראלי ת&quot;י 5568, המבוסס על הנחיות WCAG 2.0 ברמת AA.
          </p>
          <p>
            המטרה היא לאפשר רכישה ומכירה של כרטיסים בשוק המשני באופן עצמאי, ברור ובטוח ככל האפשר —
            במחשב, בטאבלט ובטלפון נייד.
          </p>
        </section>

        <section className="terms-section">
          <h2>2. התאמות שבוצעו באתר</h2>
          <ul>
            <li>ממשק בעברית ובכיוון RTL, לרבות טפסים, תפריטים ועמודי מידע משפטי.</li>
            <li>
              תפריט נגישות קבוע בכל עמודי האתר, המאפשר בין היתר: הגדלת טקסט, ניגודיות גבוהה, גווני
              אפור, הדגשת קישורים, גופן קריא ועצירת אנימציות.
            </li>
            <li>קישור &quot;דלג לתוכן הראשי&quot; למשתמשי מקלדת.</li>
            <li>שמות נגישים (aria-label) לרכיבים מרכזיים, לרבות כפתורי רכישה ותמיכה.</li>
            <li>יעדי לחיצה מותאמים למובייל (כ־44×44 פיקסלים) ברכיבים מרכזיים.</li>
            <li>שיפורים מתמשכים בניגודיות, ניווט במקלדת וטקסט חלופי לתמונות.</li>
          </ul>
        </section>

        <section className="terms-section">
          <h2>3. רמת הנגישות ומגבלות ידועות</h2>
          <p>
            האתר שואף לעמוד בדרישות WCAG 2.0 ברמת AA. עם זאת, חלקים מסוימים עשויים להיות מוגבלים
            בנגישות, ובכלל זה:
          </p>
          <ul>
            <li>מפות אינטראקטיביות של אולמות ויציעים.</li>
            <li>מסכי סליקה של ספק תשלומים חיצוני (צד שלישי), שאינם בשליטתנו המלאה.</li>
            <li>קבצי כרטיס (PDF) שהועלו על ידי מוכרים.</li>
          </ul>
          <p>
            במקרים אלה נשתדל לספק חלופה סבירה (למשל סיוע טלפוני/דוא״ל בהשלמת רכישה) לפי פנייה
            לתיאום נגישות.
          </p>
        </section>

        <section className="terms-section">
          <h2>4. תאימות ושימוש מומלץ</h2>
          <p>
            האתר נבדק בדפדפנים עדכניים נפוצים (Chrome, Safari, Edge, Firefox) במחשב ובמובייל. לחוויית
            נגישות מיטבית מומלץ להשתמש בדפדפן מעודכן. ניתן גם להפעיל את אפשרויות הנגישות המובנות
            במערכת ההפעלה ובדפדפן.
          </p>
        </section>

        <section className="terms-section">
          <h2>5. פניות בנושא נגישות</h2>
          <p>
            נתקלתם בבעיית נגישות, חסם או צורך בהתאמה? נשמח לתקן בהקדם. אנא פנו לרכז/ת הנגישות של
            TradeTix:
          </p>
          <ul>
            <li>
              דוא״ל:{' '}
              <a href={`mailto:${ACCESSIBILITY_EMAIL}`}>{ACCESSIBILITY_EMAIL}</a>
              {' '}(נא לציין בנושא: &quot;נגישות&quot;)
            </li>
            <li>
              טופס פנייה: עמוד <Link to="/contact">צור קשר</Link>
            </li>
          </ul>
          <p>
            נשתדל לחזור אליכם בהקדם סביר ולתת מענה, תיקון או חלופה. פרטי העסק מופיעים בעמוד{' '}
            <Link to="/about">אודות TradeTix</Link>.
          </p>
        </section>

        <section className="terms-section">
          <h2>6. עדכון ההצהרה</h2>
          <p>
            הצהרה זו תעודכן מעת לעת בהתאם לשיפורים באתר, לשינויי דין או למשוב משתמשים. תאריך העדכון
            האחרון מופיע בראש העמוד.
          </p>
        </section>
      </article>
    </div>
  );
};

export default AccessibilityPage;
