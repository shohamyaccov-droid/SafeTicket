import { currencySymbol, formatAmountForCurrency, resolveTicketCurrency } from '../utils/priceFormat';
import './EventMobileBuyBar.css';

/* eslint-disable react/prop-types -- project does not use PropTypes consistently */

/**
 * Mobile-only sticky checkout bar: lowest visible listing price + קנה עכשיו.
 * Hidden on desktop via CSS. Parent should unmount when checkout/offer is open.
 */
export default function EventMobileBuyBar({
  ticket,
  remainingCount = null,
  busy = false,
  onBuy,
}) {
  if (!ticket) return null;
  const cur = resolveTicketCurrency(ticket);
  const sym = currencySymbol(cur);
  const priceLabel = formatAmountForCurrency(ticket.asking_price || ticket.original_price, cur);
  const remaining = Number(remainingCount);
  const showScarcity = Number.isFinite(remaining) && remaining > 0 && remaining <= 3;
  const scarcityLabel =
    remaining === 1 ? 'נשאר כרטיס אחד בקבוצה הזו' : `נשארו ${remaining} כרטיסים בקבוצה הזו`;

  return (
    <div className="event-mobile-buy-bar" dir="rtl" role="region" aria-label="רכישה מהירה">
      <div className="event-mobile-buy-bar__price">
        <span className="event-mobile-buy-bar__from">כרטיסים מ-{sym}{priceLabel}</span>
        {showScarcity ? (
          <span className="event-mobile-buy-bar__scarcity">{scarcityLabel}</span>
        ) : (
          <span className="event-mobile-buy-bar__hint">לכרטיס, לפני דמי שירות</span>
        )}
      </div>
      <button
        type="button"
        className="event-mobile-buy-bar__cta"
        disabled={busy}
        onClick={onBuy}
      >
        {busy ? (
          <>
            מעביר לתשלום… <span className="button-spinner" aria-hidden />
          </>
        ) : (
          'קנה עכשיו'
        )}
      </button>
    </div>
  );
}
