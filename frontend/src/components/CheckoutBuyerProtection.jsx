import { Link } from 'react-router-dom';
import './CheckoutBuyerProtection.css';

export function CheckoutEscrowNote() {
  return (
    <p className="checkout-escrow-note">
      הכסף נשמר בנאמנות ומשוחרר למוכר 36 שעות לאחר תום האירוע, בכפוף לתקינות הכרטיס ולהיעדר תלונה מבוססת.
    </p>
  );
}

export default function CheckoutBuyerProtection() {
  return (
    <details className="checkout-buyer-protection">
      <summary>הגנת הקונה של TradeTix — קונים בראש שקט</summary>
      <ul>
        <li>
          <strong>הכסף שלכם נשמר בנאמנות (Escrow):</strong> אנחנו מגנים עליכם מעקיצות. הכסף נשמר
          בנאמנות ומשוחרר למוכר 36 שעות לאחר תום האירוע, בכפוף לתקינות הכרטיס ולהיעדר תלונה מבוססת.
        </li>
        <li>
          <strong>סריקה ואימות כרטיסים:</strong> כל כרטיס שמועלה לפלטפורמה עובר בדיקת מערכת
          אוטומטית למניעת כפילויות. ברגע שכרטיס נמכר, הברקוד ננעל ולא ניתן למכור אותו שוב באתר.
        </li>
        <li>
          <strong>רכישה מאובטחת:</strong> הסליקה מתבצעת בתקן האבטחה המחמיר ביותר (PCI-DSS) על ידי
          חברת אשראי חיצונית. פרטי האשראי שלכם לעולם אינם נשמרים בשרתי האתר.
        </li>
        <li>
          <strong>החזר בביטול אירוע:</strong> החזר מלא (או זיכוי, בהתאם לתקנון) ישירות לאמצעי
          התשלום במקרה של ביטול סופי של האירוע על ידי ההפקה.
        </li>
      </ul>
      <p className="checkout-buyer-protection__more">
        <Link to="/buyer-guarantee">לתנאי הגנת הקונה המלאים</Link>
      </p>
    </details>
  );
}
