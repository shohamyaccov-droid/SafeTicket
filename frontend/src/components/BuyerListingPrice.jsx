import {
  getTicketPrice,
  resolveTicketCurrency,
  currencySymbol,
  getTicketBaseNumeric,
} from '../utils/priceFormat';
import useBuyerServiceFeePercent from '../hooks/useBuyerServiceFeePercent';
import { formatBuyerFeePercent } from '../services/pricingSettings';
import './BuyerListingPrice.css';

/**
 * Browse surfaces: large seller asking price (base), muted line for buyer service fee.
 * Fee % comes from the same live pricing settings as checkout.
 * Not used on final checkout summary (CheckoutModal keeps full breakdown).
 */
/* eslint-disable-next-line react/prop-types */
const BuyerListingPrice = ({ ticket, compact = false, quantity = null }) => {
  const feePercent = useBuyerServiceFeePercent();
  const feeLabel = formatBuyerFeePercent(feePercent);
  const cur = resolveTicketCurrency(ticket);
  const sym = currencySymbol(cur);
  const baseNum = getTicketBaseNumeric(ticket);
  const showFee = !Number.isNaN(baseNum) && baseNum > 0;

  const qty = quantity != null ? Number(quantity) : null;
  const qtyLabel =
    qty != null && qty > 0 ? `${qty} ${qty === 1 ? 'כרטיס' : 'כרטיסים'}` : null;

  return (
    <div className={`buyer-listing-price ${compact ? 'buyer-listing-price--compact' : ''}`}>
      {qtyLabel ? <div className="buyer-listing-price-qty">{qtyLabel}</div> : null}
      <div className="buyer-listing-price-main">
        <span>{sym}{getTicketPrice(ticket)}</span>
        <span className="buyer-listing-price-per-ticket">לכרטיס</span>
      </div>
      {showFee && (
        <div className="buyer-listing-price-fee">
          + {feeLabel}% דמי שירות ותפעול
        </div>
      )}
    </div>
  );
};

export default BuyerListingPrice;
