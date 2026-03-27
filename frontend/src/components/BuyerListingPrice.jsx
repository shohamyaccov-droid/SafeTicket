import { formatPrice, getTicketPrice, getBuyerServiceFeeShekels } from '../utils/priceFormat';
import './BuyerListingPrice.css';

/**
 * Browse surfaces: large seller asking price (base), muted line for buyer service fee.
 * Not used on final checkout summary (CheckoutModal keeps full breakdown).
 */
const BuyerListingPrice = ({ ticket, compact = false }) => {
  const baseStr = getTicketPrice(ticket);
  const baseNum = parseFloat(baseStr);
  const fee =
    !Number.isNaN(baseNum) && baseNum > 0 ? getBuyerServiceFeeShekels(baseNum) : 0;

  return (
    <div className={`buyer-listing-price ${compact ? 'buyer-listing-price--compact' : ''}`}>
      <div className="buyer-listing-price-main">₪{formatPrice(baseNum)}</div>
      {fee > 0 && (
        <div className="buyer-listing-price-fee">
          + ₪{formatPrice(fee)} עמלת שירות (10%)
        </div>
      )}
    </div>
  );
};

export default BuyerListingPrice;
