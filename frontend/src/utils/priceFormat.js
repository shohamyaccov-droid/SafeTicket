/**
 * Format price for display: whole shekels show without decimals (222), fractional amounts keep 2 decimals (e.g. order totals).
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
 * Calculate unit price with 10% fee - ROUND UP per Israeli marketplace standard.
 * Used for display on EventDetailsPage and CheckoutModal to ensure consistency.
 * Rule: Math.ceil(base_price * 1.10)
 */
export const getUnitPriceWithFee = (basePrice) => {
  const base = parseFloat(String(basePrice ?? 0));
  if (isNaN(base) || base <= 0) return 0;
  return Math.ceil(base * 1.10);
};

/**
 * Calculate total price for quantity: unitPriceWithFee * quantity.
 * Ensures unitPrice * quantity === totalPrice (no rounding drift).
 */
export const getTotalWithFee = (basePrice, quantity) => {
  const unitPrice = getUnitPriceWithFee(basePrice);
  const qty = typeof quantity === 'string' ? parseInt(quantity, 10) : Number(quantity);
  if (isNaN(qty) || qty <= 0) return 0;
  return unitPrice * qty;
};

/**
 * Face value for a ticket listing (whole shekels only: "222", not "221.99").
 */
export const getTicketPrice = (ticket) => {
  if (!ticket) return '0';

  const price = ticket.asking_price ?? ticket.original_price ?? ticket.price ?? '0';
  const priceStr = typeof price === 'string' ? price : String(price);
  const num = parseFloat(priceStr);
  if (isNaN(num)) return '0';
  return String(Math.round(num));
};

/**
 * Calculate base amount (unit price * quantity) using precise decimal math
 * Returns string with exactly 2 decimal places
 * Global fix: Wraps calculation in .toFixed(2) to ensure precision
 */
export const calculateBaseAmount = (unitPrice, quantity) => {
  // Handle Decimal objects from backend
  const priceStr = typeof unitPrice === 'string' ? unitPrice : String(unitPrice);
  const price = parseFloat(priceStr);
  const qty = typeof quantity === 'string' ? parseInt(quantity, 10) : Number(quantity);
  
  if (isNaN(price) || isNaN(qty) || price <= 0 || qty <= 0) {
    return '0.00';
  }
  
  // Calculate base amount with precise decimal math
  // Wrap in .toFixed(2) to ensure exactly 2 decimal places
  const baseAmount = price * qty;
  return parseFloat(baseAmount.toFixed(2)).toFixed(2); // Double ensure precision
};

/**
 * Calculate service fee using precise decimal math
 * Returns string with exactly 2 decimal places
 * Global fix: Wraps calculation in .toFixed(2) to ensure precision
 */
export const calculateServiceFee = (baseAmount, serviceFeePercent = 10) => {
  const amountStr = typeof baseAmount === 'string' ? baseAmount : String(baseAmount);
  const amount = parseFloat(amountStr);
  
  if (isNaN(amount) || amount <= 0) {
    return '0.00';
  }
  
  // Calculate service fee with precise decimal math
  // Wrap in .toFixed(2) to ensure exactly 2 decimal places
  const serviceFee = (amount * serviceFeePercent) / 100;
  return parseFloat(serviceFee.toFixed(2)).toFixed(2); // Double ensure precision
};

/**
 * Calculate total price with service fee using precise decimal math
 * Returns string with exactly 2 decimal places
 * Global fix: Wraps calculation in .toFixed(2) to ensure precision
 */
export const calculateTotalWithFee = (unitPrice, quantity, serviceFeePercent = 10) => {
  const baseAmount = calculateBaseAmount(unitPrice, quantity);
  const serviceFee = calculateServiceFee(baseAmount, serviceFeePercent);
  
  // Calculate total with precise decimal math
  // Wrap in .toFixed(2) to ensure exactly 2 decimal places
  const total = parseFloat(baseAmount) + parseFloat(serviceFee);
  return parseFloat(total.toFixed(2)).toFixed(2); // Double ensure precision
};

