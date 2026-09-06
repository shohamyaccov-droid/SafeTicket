import {
  currencySymbol,
  formatListingAmountForCurrency,
  getTicketBaseNumeric,
  resolveTicketCurrency,
} from '../utils/priceFormat';
import './BuyerListingPrice.css';

/**
 * Browse surfaces: face-value (base) price only. Fees appear in CheckoutModal.
 */
/* eslint-disable-next-line react/prop-types */
const BuyerListingPrice = ({ ticket, compact = false, quantity = null }) => {
  const currency = resolveTicketCurrency(ticket);
  const formatted = formatListingAmountForCurrency(getTicketBaseNumeric(ticket), currency);
  const sym = currencySymbol(currency);

  const qty = quantity != null ? Number(quantity) : null;
  const qtyLabel =
    qty != null && qty > 0 ? `${qty} ${qty === 1 ? 'כרטיס' : 'כרטיסים'}` : null;

  return (
    <div className={`buyer-listing-price ${compact ? 'buyer-listing-price--compact' : ''}`}>
      {qtyLabel ? <div className="buyer-listing-price-qty">{qtyLabel}</div> : null}
      <div className="buyer-listing-price-main">
        <span>{sym}{formatted}</span>
        <span className="buyer-listing-price-per-ticket">לכרטיס</span>
      </div>
    </div>
  );
};

export default BuyerListingPrice;
