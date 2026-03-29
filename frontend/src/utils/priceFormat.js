/**
 * Money: align with backend `buyer_charge_from_base_amount` — base + 10% fee, each rounded to 0.01 ILS.
 * Implemented via integer agorot to avoid float drift.
 */

/**
 * @param {number|string} baseInput - Seller-facing base (per unit or bundle) in ILS
 * @returns {{ baseAmount: number, serviceFee: number, totalAmount: number }}
 */
export function buyerChargeFromBase(baseInput) {
  const raw = parseFloat(String(baseInput ?? 0));
  if (!Number.isFinite(raw) || raw <= 0) {
    return { baseAmount: 0, serviceFee: 0, totalAmount: 0 };
  }
  const base = Math.round(raw * 100) / 100;
  const baseAg = Math.round(base * 100);
  const feeAg = Math.round((baseAg * 10) / 100);
  const totalAg = baseAg + feeAg;
  return {
    baseAmount: baseAg / 100,
    serviceFee: feeAg / 100,
    totalAmount: totalAg / 100,
  };
}

/**
 * Format price for display: whole shekels without decimals; otherwise 2 decimals.
 */
export const formatPrice = (price) => {
  if (price === null || price === undefined || price === '') {
    return '0';
  }

  const priceStr = typeof price === 'string' ? price : String(price);
  const numPrice = parseFloat(priceStr);

  if (isNaN(numPrice)) {
    return '0';
  }

  const rounded = Math.round(numPrice * 100) / 100;
  if (Number.isInteger(rounded) || Math.abs(rounded - Math.round(rounded)) < 1e-9) {
    return String(Math.round(rounded));
  }
  return rounded.toFixed(2);
};

/**
 * Single listing unit: total buyer pays for one ticket at list/negotiated unit base.
 */
export const getUnitPriceWithFee = (basePrice) => {
  const { totalAmount } = buyerChargeFromBase(basePrice);
  return totalAmount;
};

/**
 * Buyer service fee for one unit (total − base).
 */
export const getBuyerServiceFeeShekels = (basePrice) => {
  const { serviceFee } = buyerChargeFromBase(basePrice);
  return serviceFee;
};

/**
 * Total for quantity: 10% fee on (unit base × qty) subtotal.
 */
export const getTotalWithFee = (basePrice, quantity) => {
  const qty = typeof quantity === 'string' ? parseInt(quantity, 10) : Number(quantity);
  if (isNaN(qty) || qty <= 0) return 0;
  const unit = parseFloat(String(basePrice ?? 0));
  if (isNaN(unit) || unit <= 0) return 0;
  const baseSubtotal = Math.round(unit * qty * 100) / 100;
  const { totalAmount } = buyerChargeFromBase(baseSubtotal);
  return totalAmount;
};

/**
 * Face value for a ticket listing (whole shekels for display).
 */
export const getTicketPrice = (ticket) => {
  if (!ticket) return '0';

  const price = ticket.asking_price ?? ticket.original_price ?? ticket.price ?? '0';
  const priceStr = typeof price === 'string' ? price : String(price);
  const num = parseFloat(priceStr);
  if (isNaN(num)) return '0';
  return String(Math.round(num));
};

export const calculateBaseAmount = (unitPrice, quantity) => {
  const priceStr = typeof unitPrice === 'string' ? unitPrice : String(unitPrice);
  const price = parseFloat(priceStr);
  const qty = typeof quantity === 'string' ? parseInt(quantity, 10) : Number(quantity);

  if (isNaN(price) || isNaN(qty) || price <= 0 || qty <= 0) {
    return '0.00';
  }

  const baseAmount = price * qty;
  return parseFloat(baseAmount.toFixed(2)).toFixed(2);
};

export const calculateServiceFee = (baseAmount, serviceFeePercent = 10) => {
  const amountStr = typeof baseAmount === 'string' ? baseAmount : String(baseAmount);
  const amount = parseFloat(amountStr);

  if (isNaN(amount) || amount <= 0) {
    return '0.00';
  }

  const { serviceFee } = buyerChargeFromBase(amount);
  return serviceFee.toFixed(2);
};

export const calculateTotalWithFee = (unitPrice, quantity, serviceFeePercent = 10) => {
  const baseAmount = calculateBaseAmount(unitPrice, quantity);
  const { totalAmount } = buyerChargeFromBase(parseFloat(baseAmount));
  return totalAmount.toFixed(2);
};
