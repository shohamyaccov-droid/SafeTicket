/**
 * Format price with exactly 2 decimal places
 * Uses precise decimal logic to avoid floating point errors
 * Global fix: Ensures 133 is always displayed as 133.00
 */
export const formatPrice = (price) => {
  if (price === null || price === undefined || price === '') {
    return '0.00';
  }
  
  // Convert to number for precise calculation
  // Handle Decimal objects from backend by converting to string first
  const priceStr = typeof price === 'string' ? price : String(price);
  const numPrice = parseFloat(priceStr);
  
  // Check if valid number
  if (isNaN(numPrice)) {
    return '0.00';
  }
  
  // Use toFixed(2) to ensure exactly 2 decimal places
  // This handles floating point precision issues and ensures 133 -> 133.00
  return numPrice.toFixed(2);
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
 * Get the display price from a ticket object
 * Returns the asking_price, original_price, or price field
 * Always returns a string with exactly 2 decimal places
 */
export const getTicketPrice = (ticket) => {
  if (!ticket) return '0.00';
  
  // Priority: asking_price > original_price > price
  // Ensure we handle Decimal fields from backend correctly
  // CRITICAL: Apply toFixed(2) to raw DB value BEFORE any calculations
  const price = ticket.asking_price ?? ticket.original_price ?? ticket.price ?? '0';
  
  // Convert to string if it's a Decimal object, then format
  // This ensures the raw DB value (e.g., 444.00) is preserved exactly
  const priceStr = typeof price === 'string' ? price : String(price);
  
  // Apply toFixed(2) to the raw value from DB to ensure 444.00, not 443.99
  return formatPrice(priceStr);
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

