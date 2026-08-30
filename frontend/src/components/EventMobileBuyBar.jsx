import {
  currencySymbol,
  buyerAllInFromTicket,
} from '../utils/priceFormat';
import useBuyerServiceFeePercent from '../hooks/useBuyerServiceFeePercent';
import './EventMobileBuyBar.css';

/* eslint-disable react/prop-types -- project does not use PropTypes consistently */

/**
 * Mobile-only sticky checkout bar: all-in listing price + קנה עכשיו.
 * Hidden on desktop via CSS. Parent should unmount when checkout/offer is open.
 */
export default function EventMobileBuyBar({
  ticket,
  remainingCount = null,
  busy = false,
  onBuy,
}) {
  const feePercent = useBuyerServiceFeePercent();
  if (!ticket) return null;
  const { formattedTotal, currency } = buyerAllInFromTicket(ticket, feePercent);
  const remaining = Number(remainingCount);
  const showScarcity = Number.isFinite(remaining) && remaining > 0 && remaining <= 3;
  const scarcityLabel =
    remaining === 1 ? 'נשאר כרטיס אחד בקבוצה הזו' : `נשארו ${remaining} כרטיסים בקבוצה הזו`;

  return (
    <div className="event-mobile-buy-bar" dir="rtl" role="region" aria-label="רכישה מהירה">
      <div className="event-mobile-buy-bar__price">
        <span className="event-mobile-buy-bar__from">
          {currencySymbol(currency)}{formattedTotal}
        </span>
        {showScarcity ? (
          <span className="event-mobile-buy-bar__scarcity">{scarcityLabel}</span>
        ) : null}
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
