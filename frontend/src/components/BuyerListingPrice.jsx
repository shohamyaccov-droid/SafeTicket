import {
  buyerAllInFromTicket,
  currencySymbol,
} from '../utils/priceFormat';
import useBuyerServiceFeePercent from '../hooks/useBuyerServiceFeePercent';
import './BuyerListingPrice.css';

/**
 * Browse surfaces: all-in buyer price only. Fee breakdown belongs in CheckoutModal.
 */
/* eslint-disable-next-line react/prop-types */
const BuyerListingPrice = ({ ticket, compact = false, quantity = null }) => {
  const feePercent = useBuyerServiceFeePercent();
  const { formattedTotal, currency } = buyerAllInFromTicket(ticket, feePercent);
  const sym = currencySymbol(currency);

  const qty = quantity != null ? Number(quantity) : null;
  const qtyLabel =
    qty != null && qty > 0 ? `${qty} ${qty === 1 ? 'כרטיס' : 'כרטיסים'}` : null;

  return (
    <div className={`buyer-listing-price ${compact ? 'buyer-listing-price--compact' : ''}`}>
      {qtyLabel ? <div className="buyer-listing-price-qty">{qtyLabel}</div> : null}
      <div className="buyer-listing-price-main">
        <span>{sym}{formattedTotal}</span>
        <span className="buyer-listing-price-per-ticket">לכרטיס</span>
      </div>
    </div>
  );
};

export default BuyerListingPrice;
