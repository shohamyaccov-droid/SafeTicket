import { useState } from 'react';
import { Link } from 'react-router-dom';
import './FAQ.css';

const FAQ = () => {
  const [openIndex, setOpenIndex] = useState(null);

  const faqs = [
    {
      question: 'האם הרכישה בטוחה? מהי הגנת הקונה?',
      answer: (
        <>
          כן. כספי הרכישה מוחזקים בנאמנות (Escrow) ואינם מועברים למוכר מיד. שחרור למוכר מתבצע רק{' '}
          <strong>36 שעות לאחר סיום האירוע</strong>, בכפוף לתקינות העסקה. פירוט מלא בעמוד{' '}
          <Link to="/buyer-guarantee">הגנת הקונה</Link> וב־
          <Link to="/refunds">ביטולים והחזרים</Link>.
        </>
      ),
    },
    {
      question: 'מה קורה אם המופע מבוטל?',
      answer: (
        <>
          אם המארגן מבטל את האירוע <strong>סופית</strong> (ללא מועד חדש מחייב) — אתם זכאים להחזר מלא
          של הסכום ששולם ל-TradeTix (מחיר הכרטיס + דמי שירות), בהתאם לתקנון ולעמוד ההחזרים. יעד טיפול:
          עד 10 ימי עסקים מאישור הביטול בפלטפורמה. ראו{' '}
          <Link to="/refunds">מטריצת החזרים</Link>.
        </>
      ),
    },
    {
      question: 'מה קורה אם המופע נדחה למועד חדש?',
      answer: (
        <>
          הכרטיס <strong>נשאר בתוקף</strong> למועד החדש. <strong>אין החזר אוטומטי</strong> רק בשל
          דחייה. אם אינכם יכולים להגיע — ניתן לנסות למכור מחדש באתר. אם בהמשך יוכרז ביטול סופי — תחול
          מדיניות הביטול (החזר מלא).
        </>
      ),
    },
    {
      question: 'מדיניות כרטיס מזויף / לא תקף (Fake Ticket Policy)',
      answer: (
        <>
          אם הכרטיס נדחה בכניסה: (1) פנו לתמיכה <strong>מיד מהמקום</strong> או לכל המאוחר תוך שעה
          מסיום האירוע; (2) צרפו תיעוד (סרטון/צילום של הסריקה והודעת השגיאה); (3) במקרה מאומת — החזר
          מלא של מה ששולם ל-TradeTix, והמוכר לא יקבל תמלוג ועשוי להיחסם. פרטים:{' '}
          <Link to="/refunds">החזרים</Link> · <Link to="/buyer-guarantee">הגנת הקונה</Link> ·{' '}
          <Link to="/terms">תקנון</Link>.
        </>
      ),
    },
    {
      question: 'מתי אקבל את הכרטיסים?',
      answer:
        'כרטיסים דיגיטליים נמסרים בדרך כלל מיד או זמן קצר לאחר השלמת הרכישה (קובץ PDF / ברקוד במייל או באזור האישי). ודאו שפרטי האימייל נכונים ושמרו גיבוי לטלפון לפני ההגעה לאירוע.',
    },
    {
      question: 'מהן העמלות? (דמי שירות)',
      answer: (
        <>
          לקונים: דמי שירות ותפעול של <strong>12%</strong> ממחיר הבסיס של הכרטיס (או שיעור מופחת אם
          מוצג קופון בקופה). למוכרים: עמלת מכירה <strong>0%</strong> בעת זו. המחיר הסופי כולל עמלות
          מוצג במסך התשלום לפני אישור העסקה — בהתאם לתקנון סעיף שקיפות עמלות.
        </>
      ),
    },
    {
      question: 'מתי המוכר מקבל את הכסף? (Escrow 36 שעות)',
      answer: (
        <>
          הכסף אינו מועבר מיד עם המכירה. הוא נשמר בנאמנות ומשתחרר למוכר רק לאחר{' '}
          <strong>36 שעות מסיום האירוע</strong>, בכפוף לכך שלא הוגשה תלונה מבוססת על תקינות הכרטיס
          ולסטטוס תקין של העסקה. פירוט ב־
          <Link to="/terms">תקנון</Link> ובדשבורד המוכר.
        </>
      ),
    },
    {
      question: 'האם TradeTix היא המפיקה של האירוע?',
      answer: (
        <>
          לא. TradeTix היא <strong>זירת מסחר משנית</strong> (marketplace) המחברת בין מוכרים מאומתים
          לקונים, וגובה תשלום כבית העסק הרשום. המפיק/בעל האירוע אינו TradeTix. ראו{' '}
          <Link to="/about">אודות</Link> ו־<Link to="/terms">תקנון — מעמד הפלטפורמה</Link>.
        </>
      ),
    },
    {
      question: 'איך פונים לתמיכה?',
      answer: (
        <>
          דרך עמוד <Link to="/contact">צור קשר</Link>, כפתור ה-WhatsApp באתר, או פרטי הקשר בעמוד{' '}
          <Link to="/about">אודות</Link>. במחלוקת בכניסה לאירוע — פנו בזמן אמת מהמקום.
        </>
      ),
    },
  ];

  const toggleFAQ = (index) => {
    setOpenIndex((prev) => (prev === index ? null : index));
  };

  return (
    <div className="faq-container">
      <div className="faq-header">
        <h1>שאלות נפוצות</h1>
        <p>תשובות ברורות — מיושרות עם התקנון ומדיניות ההחזרים</p>
      </div>

      <div className="faq-list">
        {faqs.map((faq, index) => (
          <div key={faq.question} className={`faq-item ${openIndex === index ? 'open' : ''}`}>
            <button
              className="faq-question"
              onClick={() => toggleFAQ(index)}
              aria-expanded={openIndex === index}
              type="button"
            >
              <span>{faq.question}</span>
              <svg
                className="faq-icon"
                width="20"
                height="20"
                viewBox="0 0 20 20"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                aria-hidden
              >
                <path
                  d="M5 7.5L10 12.5L15 7.5"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            <div className="faq-answer">
              <p>{faq.answer}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default FAQ;
