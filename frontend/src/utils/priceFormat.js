/**
 * Money: buyer total = base + 10% fee, quantized like backend (agorot/cents).
 * Currency follows Event.country → ISO 4217 (same mapping as backend users/currency.py).
 */

/** @param {string|null|undefined} countryCode */
export function iso4217FromCountry(countryCode) {
  const c = String(countryCode ?? 'IL').trim().toUpperCase();
  const code = c || 'IL';
  if (code === 'IL') return 'ILS';
  if (code === 'US') return 'USD';
  if (code === 'GB') return 'GBP';
  if (['DE', 'FR', 'ES', 'IT', 'GR', 'CY'].includes(code)) return 'EUR';
  if (code === 'AE') return 'USD';
  return 'ILS';
}

/** @param {string|null|undefined} iso */
export function currencySymbol(iso) {
  const u = String(iso || 'ILS').toUpperCase();
  const map = { ILS: '₪', USD: '$', GBP: '£', EUR: '€' };
  return map[u] || u;
}

/**
 * Ticket / nested event from API — prefer explicit `currency`, else event.country.
 * @param {Record<string, unknown>|null|undefined} ticket
 */
export function resolveTicketCurrency(ticket) {
  if (!ticket || typeof ticket !== 'object') return 'ILS';
  const cur = ticket.currency;
  if (cur && typeof cur === 'string') return cur.toUpperCase();
  const ev = ticket.event;
  if (ev && typeof ev === 'object') {
    if (ev.currency && typeof ev.currency === 'string') return String(ev.currency).toUpperCase();
    if (ev.country) return iso4217FromCountry(ev.country);
  }
  return 'ILS';
}

/**
 * @param {number|string} price
 * @param {string} [iso='ILS']
 */
export function formatAmountForCurrency(price, iso = 'ILS') {
  const u = String(iso || 'ILS').toUpperCase();
  const numPrice = typeof price === 'string' ? parseFloat(price) : Number(price);
  if (!Number.isFinite(numPrice)) return u === 'ILS' ? '0' : '0.00';

  const rounded = Math.round(numPrice * 100) / 100;
  if (u === 'ILS') {
    if (Number.isInteger(rounded) || Math.abs(rounded - Math.round(rounded)) < 1e-9) {
      return String(Math.round(rounded));
    }
    return rounded.toFixed(2);
  }
  if (Number.isInteger(rounded) || Math.abs(rounded - Math.round(rounded)) < 1e-9) {
    return String(Math.round(rounded));
  }
  return rounded.toFixed(2);
}

/** Symbol + amount (no separate ISO code — use alongside labels when needed). */
export function formatMoney(amount, iso = 'ILS') {
  return `${currencySymbol(iso)}${formatAmountForCurrency(amount, iso)}`;
}

/**
 * Raw listing base from API fields (before display formatting).
 * @param {Record<string, unknown>|null|undefined} ticket
 */
export function getTicketBaseNumeric(ticket) {
  if (!ticket) return 0;
  const raw = ticket.asking_price ?? ticket.original_price ?? ticket.price ?? 0;
  const n = parseFloat(String(raw));
  return Number.isFinite(n) ? n : 0;
}

/**
 * @param {Record<string, unknown>|null|undefined} ticket
 */
export function getTicketPrice(ticket) {
  if (!ticket) return '0';
  const cur = resolveTicketCurrency(ticket);
  return formatAmountForCurrency(getTicketBaseNumeric(ticket), cur);
}

/**
 * Negotiation / offer row from API (amount + currency).
 * @param {Record<string, unknown>|null|undefined} offer
 * @param {string} [fallbackCurrency='ILS']
 */
export function formatOfferAmount(offer, fallbackCurrency = 'ILS') {
  const cur = (offer && typeof offer.currency === 'string' && offer.currency) || fallbackCurrency;
  const n = parseFloat(String(offer?.amount ?? 0));
  return formatAmountForCurrency(Number.isFinite(n) ? n : 0, cur);
}

/**
 * @param {number|string} baseInput - Seller-facing base (per unit or bundle) in listing currency
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
 * Format numeric price for display: whole units when integer-like; else 2 decimals.
 * @deprecated Prefer formatAmountForCurrency(price, resolveTicketCurrency(ticket)) for locale-aware display.
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
