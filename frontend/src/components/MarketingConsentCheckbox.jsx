/* eslint-disable react/prop-types */
import './MarketingConsentCheckbox.css';

export const MARKETING_CONSENT_LABEL =
  'אני מסכים/ה לקבל עדכונים שיווקיים, מבצעים והטבות במייל ובוואטסאפ מ-TradeTix';

/**
 * Israeli spam-law opt-in. Must never be pre-checked.
 * Checking is optional — registration/checkout can proceed unchecked.
 */
export default function MarketingConsentCheckbox({
  checked,
  onChange,
  id = 'agreed-to-marketing',
  className = '',
}) {
  return (
    <div className={`marketing-consent ${className}`.trim()} dir="rtl">
      <label className="marketing-consent__label" htmlFor={id}>
        <input
          id={id}
          name="agreed_to_marketing"
          type="checkbox"
          className="marketing-consent__checkbox"
          checked={Boolean(checked)}
          onChange={(e) => onChange?.(e.target.checked)}
        />
        <span className="marketing-consent__text">{MARKETING_CONSENT_LABEL}</span>
      </label>
    </div>
  );
}
