import { Link } from 'react-router-dom';
import './CheckoutBuyerProtection.css';

export function CheckoutEscrowNote() {
  return (
    <p className="checkout-escrow-note">הכסף יועבר למוכר רק אחרי המופע</p>
  );
}

export default function CheckoutBuyerProtection() {
  return (
    <details className="checkout-buyer-protection">
      <summary>הגנת הקונה של TradeTix — קונים בראש שקט</summary>
      <ul>
        <li>
          <strong>הכסף שלכם נשמר בנאמנות (Escrow):</strong> אנחנו מגנים עליכם מעקיצות. התשלום
          שלכם נשמר בצורה מאובטחת במערכת ומועבר למוכר <strong>רק לאחר שהאירוע הסתיים</strong>{' '}
          ונכנסתם להופעה בהצלחה.
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
          <strong>החזר כספי מלא מובטח:</strong> במקרה של ביטול האירוע על ידי ההפקה, תקבלו החזר
          כספי מלא וישיר לכרטיס האשראי, ללא אותיות קטנות וללא עיכובים.
        </li>
      </ul>
      <p className="checkout-buyer-protection__more">
        <Link to="/buyer-guarantee">לתנאי הגנת הקונה המלאים</Link>
      </p>
    </details>
  );
}
