/**
 * Mandatory legal acceptance before payment.
 * Links open Terms / Refunds in a new tab.
 */
export default function CheckoutLegalAcceptance({
  checked,
  onChange,
  error = '',
  id = 'checkout-legal-acceptance',
}) {
  return (
    <div className="checkout-legal-acceptance" dir="rtl">
      <label className="checkout-legal-acceptance__label" htmlFor={id}>
        <input
          id={id}
          type="checkbox"
          className="checkout-legal-acceptance__checkbox"
          checked={Boolean(checked)}
          onChange={(e) => onChange?.(e.target.checked)}
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={error ? `${id}-error` : undefined}
        />
        <span className="checkout-legal-acceptance__text">
          קראתי ואני מאשר/ת את{' '}
          <a href="/terms" target="_blank" rel="noopener noreferrer">
            התקנון
          </a>{' '}
          ו
          <a href="/refunds" target="_blank" rel="noopener noreferrer">
            מדיניות ההחזרים
          </a>
        </span>
      </label>
      {error ? (
        <p id={`${id}-error`} className="checkout-legal-acceptance__error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Shared validation helper — used by CheckoutModal and unit tests. */
export function validateLegalAcceptance(checked) {
  if (checked) return '';
  return 'יש לאשר את התקנון ומדיניות ההחזרים לפני המשך לתשלום.';
}
