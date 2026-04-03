import {
  getTicketPrice,
  getBuyerServiceFeeShekels,
  resolveTicketCurrency,
  currencySymbol,
  formatAmountForCurrency,
  getTicketBaseNumeric,
} from '../utils/priceFormat';
import './BuyerListingPrice.css';

/**
 * Browse surfaces: large seller asking price (base), muted line for buyer service fee.
 * Not used on final checkout summary (CheckoutModal keeps full breakdown).
 */
const BuyerListingPrice = ({ ticket, compact = false }) => {
  const cur = resolveTicketCurrency(ticket);
  const sym = currencySymbol(cur);
  const baseNum = getTicketBaseNumeric(ticket);
  const fee =
    !Number.isNaN(baseNum) && baseNum > 0 ? getBuyerServiceFeeShekels(baseNum) : 0;

  return (
    <div className={`buyer-listing-price ${compact ? 'buyer-listing-price--compact' : ''}`}>
      <div className="buyer-listing-price-main">{sym}{getTicketPrice(ticket)}</div>
      {fee > 0 && (
        <div className="buyer-listing-price-fee">
          + {sym}{formatAmountForCurrency(fee, cur)} עמלת שירות (10%)
        </div>
      )}
    </div>
  );
};

export default BuyerListingPrice;
