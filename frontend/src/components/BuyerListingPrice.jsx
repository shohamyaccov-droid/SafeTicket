import {
  getTicketPrice,
  resolveTicketCurrency,
  currencySymbol,
  getTicketBaseNumeric,
} from '../utils/priceFormat';
import { BUYER_SERVICE_FEE_PERCENT } from '../constants/pricing';
import './BuyerListingPrice.css';

/**
 * Browse surfaces: large seller asking price (base), muted line for buyer service fee.
 * Not used on final checkout summary (CheckoutModal keeps full breakdown).
 */
const BuyerListingPrice = ({ ticket, compact = false, quantity = null }) => {
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
          + {BUYER_SERVICE_FEE_PERCENT}% עמלת ביטחון
        </div>
      )}
    </div>
  );
};

export default BuyerListingPrice;
