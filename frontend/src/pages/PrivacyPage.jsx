import { Link } from 'react-router-dom';
import PageSeo from '../components/PageSeo';
import { getStaticPageMeta, staticPageBreadcrumbs } from '../content/staticPageMeta';
import './Terms.css';

const PrivacyPage = () => {
  const meta = getStaticPageMeta('/privacy');
  return (
    <div className="terms-container">
      <PageSeo
        title={meta.title}
        description={meta.description}
        path="/privacy"
        breadcrumbs={staticPageBreadcrumbs('/privacy')}
      />
      <article className="terms-card">
        <h1 className="terms-title">מדיניות פרטיות</h1>
        <p style={{ textAlign: 'center', color: '#6b7280', marginBottom: '2rem' }}>
          עודכן לאחרונה: יולי 2026 · בהתאם לחוק הגנת הפרטיות, התשמ&quot;א–1981 (לרבות תיקון 13)
        </p>

        <section className="terms-section">
          <h2>1. בעל השליטה ופרטי קשר</h2>
          <p>
            בעל השליטה במידע האישי שנאסף באתר הוא מפעיל פלטפורמת TradeTix (טריידטיקס). פרטי זיהוי
            העסק מופיעים בעמוד <Link to="/about">אודות</Link>.
          </p>
          <p>
            לפניות בנושא פרטיות (עיון, תיקון, מחיקה בכפוף לדין): דרך עמוד{' '}
            <Link to="/contact">צור קשר</Link> — נא לציין בנושא הפנייה &quot;פרטיות&quot;.
          </p>
        </section>

        <section className="terms-section">
          <h2>2. כללי — מתי נאסף מידע</h2>
          <p>
            מדיניות זו מתארת כיצד TradeTix אוספת, משתמשת, מעבדת ושומרת מידע במסגרת שימוש באתר, לרבות
            רכישת כרטיסים, מכירה, הרשמה, יצירת קשר ושירות לקוחות. השימוש באתר מהווה הסכמה למדיניות זו,
            בכפוף לדין החל בישראל ולתנאי השימוש.
          </p>
          <p>
            <strong>מסירת מידע:</strong> פרטים הנדרשים להשלמת רכישה, מכירה או יצירת חשבון הם תנאי
            לביצוע השירות. סירוב למסרם ימנע השלמת הפעולה. דיוור שיווקי — אם יוצע — ייעשה בהסכמה נפרדת
            וברורה, עם אפשרות הסרה.
          </p>
        </section>

        <section className="terms-section">
          <h2>3. מידע שאנו עשויים לאסוף</h2>
          <ul>
            <li>פרטי חשבון וקשר: שם, אימייל, מספר טלפון.</li>
            <li>מידע לעסקאות: פרטי הזמנה, סטטוס תשלום, סכומים ועמלות.</li>
            <li>מסמכים לאימות: קבצי כרטיס PDF, אסמכתאות רכישה, פרטי זיהוי/בנק למוכרים (ככל שנדרש).</li>
            <li>מידע טכני: כתובת IP, סוג דפדפן, זמני גישה, פעולות באתר.</li>
            <li>עוגיות וכלי מדידה (ראו סעיף 7).</li>
          </ul>
        </section>

        <section className="terms-section">
          <h2>4. מטרות השימוש</h2>
          <ul>
            <li>הפעלת השירות, ניהול הזמנות, אימות כרטיסים ותמיכה.</li>
            <li>מניעת הונאות, שימוש לרעה ומכירת כרטיסים לא תקינים.</li>
            <li>שיפור חוויית המשתמש, איתור תקלות ואבטחת המערכת.</li>
            <li>עמידה בדרישות דין, רגולציה, ספקי תשלום ורשויות מוסמכות.</li>
          </ul>
        </section>

        <section className="terms-section">
          <h2>5. נמענים וספקים חיצוניים</h2>
          <p>המידע עשוי להיות משותף, בהיקף הנדרש, עם:</p>
          <ul>
            <li>
              <strong>ספקי סליקה</strong> (לרבות PayMe) — עיבוד תשלומים, מניעת הונאות, חיובים וזיכויים.
              פרטי כרטיס אשראי אינם נשמרים בשרתי TradeTix.
            </li>
            <li>ספקי אירוח, אבטחה ותשתית ענן.</li>
            <li>כלי אנליטיקה ומדידה (לרבות Google Tag Manager / כלי מדידה דומים), ככל שפעילים באתר.</li>
            <li>ערוצי תמיכה (למשל WhatsApp / דוא״ל) לצורך מענה לפניות.</li>
            <li>רשויות מוסמכות כאשר הדבר נדרש על פי דין.</li>
          </ul>
        </section>

        <section className="terms-section">
          <h2>6. שמירה, אבטחה וזכויות</h2>
          <p>
            אנו נוקטים באמצעים סבירים להגנה על המידע. מידע נשמר כל עוד הוא נדרש להפעלת השירות, עמידה
            בחובות משפטיות, מניעת הונאות, תיעוד עסקאות או טיפול בפניות — ובהתאם לתקופות שמירה מקובלות
            בענף הסליקה.
          </p>
          <p>
            ניתן לפנות בבקשה לעיון, תיקון או מחיקת מידע אישי, בכפוף לדין ולצרכי אבטחה ותיעוד עסקאות —
            דרך <Link to="/contact">צור קשר</Link>.
          </p>
        </section>

        <section className="terms-section">
          <h2>7. עוגיות (Cookies) ומדידה</h2>
          <p>
            האתר עשוי להשתמש בעוגיות חיוניות לתפקוד (התחברות, אבטחה, סליקה) ובעוגיות/תגיות מדידה
            לשיפור השירות ולניתוח שימוש. ניתן לנהל העדפות עוגיות בהגדרות הדפדפן; חסימת עוגיות חיוניות
            עלולה לפגוע בתפקוד האתר.
          </p>
        </section>

        <section className="terms-section">
          <h2>8. מסמכים קשורים</h2>
          <p>
            <Link to="/terms">תקנון ותנאי שימוש</Link> · <Link to="/refunds">ביטולים והחזרים</Link> ·{' '}
            <Link to="/about">אודות</Link> · <Link to="/accessibility">הצהרת נגישות</Link>.
          </p>
        </section>
      </article>
    </div>
  );
};

export default PrivacyPage;
