import './BuyerGuarantee.css';

function IconRefundCard() {
  return (
    <svg
      className="buyer-guarantee__icon-svg"
      width="32"
      height="32"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M5 9.5C5 8.11929 6.11929 7 7.5 7H16.5C17.8807 7 19 8.11929 19 9.5V16.5C19 17.8807 17.8807 19 16.5 19H7.5C6.11929 19 5 17.8807 5 16.5V9.5Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
      <path d="M5 11H19" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      <path
        d="M9 15.25L10.75 17L14 13.5"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconCommunityVerified() {
  return (
    <svg
      className="buyer-guarantee__icon-svg"
      width="32"
      height="32"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.75" />
      <path
        d="M8.5 12L11 14.5L15.5 9.5"
        stroke="currentColor"
        strokeWidth="1.85"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconSecureLock() {
  return (
    <svg
      className="buyer-guarantee__icon-svg"
      width="32"
      height="32"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M8 10V8C8 5.79086 9.79086 4 12 4C14.2091 4 16 5.79086 16 8V10"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
      <rect
        x="5.5"
        y="10"
        width="13"
        height="10"
        rx="2.25"
        stroke="currentColor"
        strokeWidth="1.75"
      />
      <circle cx="12" cy="14.75" r="1.35" fill="currentColor" />
      <path d="M12 16.1V17.9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

const FEATURES = [
  {
    id: 'refund',
    icon: IconRefundCard,
    text:
      'אחריות כספית מלאה: האירוע בוטל? הכרטיס לא עבד בקופות? אתם מקבלים החזר כספי מלא באופן אוטומטי.',
  },
  {
    id: 'community',
    icon: IconCommunityVerified,
    text: 'קהילה אמינה: כל המוכרים בפלטפורמה עוברים אימות זהות מקיף.',
  },
  {
    id: 'secure',
    icon: IconSecureLock,
    text:
      'קנייה מאובטחת: הצטרפו למאות משתמשים שכבר קנו ומכרו כרטיסים בבטחה דרך הפלטפורמה שלנו.',
  },
];

export default function BuyerGuarantee() {
  return (
    <section className="buyer-guarantee" dir="rtl" aria-labelledby="buyer-guarantee-heading">
      <div className="buyer-guarantee__inner">
        <header className="buyer-guarantee__header">
          <h2 id="buyer-guarantee-heading" className="buyer-guarantee__title">
            קונים כרטיסים בראש שקט – מוגנים ב-100% מהונאות
          </h2>
          <p className="buyer-guarantee__subtitle">
            התשלום שלכם מוחזק בנאמנות (Escrow) ומועבר למוכר אך ורק לאחר שהאירוע התקיים ונכנסתם אליו
            בהצלחה. בלי עוקצים, בלי הפתעות.
          </p>
        </header>

        <ul className="buyer-guarantee__grid">
          {FEATURES.map(({ id, icon: Icon, text }) => (
            <li key={id} className="buyer-guarantee__feature">
              <div className="buyer-guarantee__icon-wrap" aria-hidden>
                <Icon />
              </div>
              <p className="buyer-guarantee__feature-text">{text}</p>
            </li>
          ))}
        </ul>

        <p className="buyer-guarantee__footer">
          <strong className="buyer-guarantee__footer-strong">הכסף שלכם מוגן</strong>
          {', '}
          <strong className="buyer-guarantee__footer-strong">הכרטיס שלכם מובטח</strong>
          {', ולכם נשאר רק '}
          <strong className="buyer-guarantee__footer-strong">ליהנות מהאירוע</strong>
          .
        </p>
      </div>
    </section>
  );
}
