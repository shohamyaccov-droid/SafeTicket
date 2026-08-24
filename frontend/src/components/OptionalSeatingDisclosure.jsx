/* eslint-disable react/prop-types */

const SEATING_HINT =
  'לא בטוחים? השאירו ריק ואנחנו נשלים את הפרטים מהכרטיס באופן אוטומטי לאחר ההעלאה.';

/**
 * Progressive disclosure for optional גוש / שורה / כיסא on the sell wizard.
 */
export default function OptionalSeatingDisclosure({ open, onToggle, children }) {
  return (
    <div className="sell-optional-seating">
      <button
        type="button"
        className="sell-optional-seating__toggle"
        onClick={onToggle}
        aria-expanded={open}
      >
        ➕ הוספת פרטי ישיבה (אופציונלי)
      </button>
      {open ? (
        <div className="sell-optional-seating__panel">
          <p className="sell-optional-seating__hint">{SEATING_HINT}</p>
          {children}
        </div>
      ) : null}
    </div>
  );
}

export { SEATING_HINT };
