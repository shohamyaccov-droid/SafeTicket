import { useState, useEffect, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authAPI, orderAPI, paymentAPI, ticketAPI, ensureCsrfToken } from '../services/api';
import {
  getTicketPrice,
  formatPrice,
  buyerChargeFromBase,
  resolveTicketCurrency,
  currencySymbol,
  formatAmountForCurrency,
  getTicketBaseNumeric,
} from '../utils/priceFormat';
import { toastError } from '../utils/toast';
import { downloadTicketFromAxiosBlob, ticketFileMimeFromAxiosHeaders } from '../utils/ticketDownload';
import './CheckoutModal.css';

/** Buy Now: server cart hold (see TicketViewSet reserve). Negotiation: post-accept checkout window. */
const CART_RESERVE_SECONDS = 10 * 60;
const OFFER_CHECKOUT_FALLBACK_SECONDS = 24 * 60 * 60;

function portalCheckoutRoot(node) {
  if (typeof document === 'undefined') return null;
  return createPortal(node, document.body);
}

/** Django CSRF / generic HTML error pages — never show raw HTML in toasts (especially on mobile). */
const CHECKOUT_CSRF_HTML_MESSAGE =
  'שגיאת אבטחה בתקשורת. אנא רענן את העמוד ונסה שוב.';

function responseDataLooksLikeHtml(data) {
  if (typeof data !== 'string' || !data.length) return false;
  const head = data.slice(0, 800).toLowerCase();
  return (
    head.includes('<html') ||
    head.includes('<!doctype') ||
    head.includes('<body') ||
    head.includes('body {') ||
    head.includes('csrf verification failed') ||
    (head.includes('forbidden') && head.includes('403'))
  );
}

function formatCheckoutBackendError(err) {
  const data = err?.response?.data;
  const status = err?.response?.status;
  if (data == null || data === '') {
    return err?.message ? String(err.message) : '';
  }
  if (typeof data === 'string') {
    if (responseDataLooksLikeHtml(data) || (status === 403 && /csrf|forbidden/i.test(data))) {
      return CHECKOUT_CSRF_HTML_MESSAGE;
    }
    const stripped = data.replace(/<[^>]+>/g, '').trim();
    if (responseDataLooksLikeHtml(stripped) || (status === 403 && /csrf verification failed/i.test(stripped))) {
      return CHECKOUT_CSRF_HTML_MESSAGE;
    }
    return stripped.slice(0, 600);
  }
  const d = data.detail ?? data.error ?? data.message;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) {
    return d
      .map((x) => (typeof x === 'string' ? x : JSON.stringify(x)))
      .join('; ');
  }
  if (d && typeof d === 'object') {
    try {
      return JSON.stringify(d);
    } catch {
      return err?.message || '';
    }
  }
  try {
    return JSON.stringify(data);
  } catch {
    return err?.message || '';
  }
}

function validateGuestContact(email, phone) {
  const em = String(email || '').trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em)) {
    return 'נא להזין אימייל תקין';
  }
  const digits = String(phone || '').replace(/\D/g, '');
  if (digits.length < 9 || digits.length > 15) {
    return 'נא להזין מספר טלפון תקין (לפחות 9 ספרות)';
  }
  return null;
}

/** Pre-production mock gateway: digits-only PAN length 13–19; no Luhn (e.g. 1111111111111111 allowed). */
function validateMockPaymentFields(form) {
  const name = String(form.cardholderName || '').trim();
  if (name.length < 2) return 'נא להזין שם בעל כרטיס';
  const rawCard = String(form.cardNumber || '').replace(/\s/g, '');
  if (!/^\d{13,19}$/.test(rawCard)) return 'מספר כרטיס אשראי לא תקין';
  const expRaw = String(form.expiryDate || '').replace(/\D/g, '');
  if (expRaw.length !== 4) return 'תאריך תפוגה בפורמט MM/YY';
  const mm = parseInt(expRaw.slice(0, 2), 10);
  const yy = parseInt(expRaw.slice(2, 4), 10);
  if (mm < 1 || mm > 12) return 'חודש לא תקין';
  const now = new Date();
  const yFull = 2000 + yy;
  const curY = now.getFullYear();
  const curM = now.getMonth() + 1;
  if (yFull < curY || (yFull === curY && mm < curM)) return 'תוקף הכרטיס בעבר';
  const cvv = String(form.cvv || '').replace(/\D/g, '');
  if (!/^\d{3,4}$/.test(cvv)) return 'CVV לא תקין';
  return null;
}

const normalizeSplitType = (rawSplitType) => {
  if (!rawSplitType) return 'any';
  const str = String(rawSplitType).trim().toLowerCase();
  if (str.includes('זוגות') || str.includes('pairs')) return 'pairs';
  if (str.includes('הכל') || str.includes('all')) return 'all';
  return 'any';
};

const CheckoutModal = ({ ticket, ticketGroup, user, quantity: initialQuantity = 1, onClose, acceptedOffer = null, splitType: splitTypeOverride = null, onErrorToParent = null }) => {
  const [step, setStep] = useState('info'); // 'info', 'payment', 'success'
  const [quantity, setQuantity] = useState(initialQuantity);
  const [guestForm, setGuestForm] = useState({
    email: '',
    phone: '',
  });
  const [paymentForm, setPaymentForm] = useState({
    cardNumber: '',
    expiryDate: '',
    cvv: '',
    cardholderName: '',
  });
  const [loading, setLoading] = useState(false);
  const [infoStepBusy, setInfoStepBusy] = useState(false);
  const [pdfDownloadBusyId, setPdfDownloadBusyId] = useState(null);
  /** 'idle' | 'creating_order' | 'confirming_payment' — shown while pending_payment → paid */
  const [paymentPhase, setPaymentPhase] = useState('idle');
  const [error, setError] = useState('');
  const [orderId, setOrderId] = useState(null);
  const [orderData, setOrderData] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [timeRemaining, setTimeRemaining] = useState(CART_RESERVE_SECONDS);
  /** Initial budget for progress bar (reservation / offer checkout window). */
  const timerBudgetRef = useRef(CART_RESERVE_SECONDS);
  /** Buy Now: true only after /reserve succeeds so the 10m clock runs on info + payment. */
  const [reservationActive, setReservationActive] = useState(false);
  const [paidAmounts, setPaidAmounts] = useState(null); // Store actual paid amounts: { baseAmount, serviceFee, totalAmount }
  const [checkoutSucceeded, setCheckoutSucceeded] = useState(false); // Completed purchase — never return to payment for this session
  const timerRef = useRef(null);
  const reservationRef = useRef(false); // Track if reservation was made
  const transactionCompleteRef = useRef(false); // Prevents timer/cleanup from reverting UI after successful order
  const paymentSubmittingRef = useRef(false); // Pause reservation timer while payment API runs
  /** Synchronous snapshot so success UI never waits on PDF download or lost React state */
  const successSnapshotRef = useRef(null);
  const navigate = useNavigate();
  const stepRef = useRef(step);
  stepRef.current = step;
  const guestEmailRef = useRef('');
  useEffect(() => {
    guestEmailRef.current = (guestForm.email || '').trim();
  }, [guestForm.email]);

  useEffect(() => {
    console.info('[CheckoutModal] mount/update', {
      hasTicket: !!ticket,
      hasTicketGroup: !!ticketGroup,
      ticketId: ticket?.id,
      groupTicketsLen: ticketGroup?.tickets?.length,
    });
  }, [ticket, ticketGroup]);

  // Get locked quantity from accepted offer if it exists (accepted_at = server truth after accept)
  const isNegotiatedPrice =
    acceptedOffer &&
    (acceptedOffer.status === 'accepted' || acceptedOffer.accepted_at != null);
  /** Offer accept already locked inventory; skip cart /reserve and do not release on modal close. */
  const skipCartReserveForNegotiatedOffer = Boolean(isNegotiatedPrice && acceptedOffer);
  const checkoutTicketIdRef = useRef(null);
  useEffect(() => {
    const tid = ticket?.id;
    if (tid == null) return;
    const tidChanged = checkoutTicketIdRef.current !== tid;
    if (tidChanged) {
      checkoutTicketIdRef.current = tid;
    }
    if (skipCartReserveForNegotiatedOffer) {
      setReservationActive(true);
      if (tidChanged) {
        const cr = acceptedOffer?.checkout_time_remaining;
        const budget =
          typeof cr === 'number' && cr > 0 ? cr : OFFER_CHECKOUT_FALLBACK_SECONDS;
        timerBudgetRef.current = budget;
        setTimeRemaining(budget);
      }
    } else if (tidChanged) {
      timerBudgetRef.current = CART_RESERVE_SECONDS;
      setTimeRemaining(CART_RESERVE_SECONDS);
      setReservationActive(false);
    }
  }, [ticket?.id, skipCartReserveForNegotiatedOffer, acceptedOffer?.checkout_time_remaining]);
  const lockedQuantity = isNegotiatedPrice && acceptedOffer.quantity ? acceptedOffer.quantity : null;
  
  // Get available quantity - if locked quantity exists, use that; otherwise use ticket/group quantity
  const availableQuantity = lockedQuantity || ticketGroup?.available_count || ticket?.available_quantity || 1;

  const internalSplitTypeRaw =
    (ticketGroup?.tickets && ticketGroup.tickets[0]?.split_type) ||
    ticketGroup?.split_type ||
    ticket?.split_type ||
    null;
  const splitType = splitTypeOverride || normalizeSplitType(internalSplitTypeRaw);

  const buildQuantityOptions = () => {
    const max = availableQuantity;
    if (!max || max < 1) return [1];
    if (lockedQuantity) {
      const qty = typeof lockedQuantity === 'number' ? lockedQuantity : parseInt(lockedQuantity, 10);
      return !isNaN(qty) && qty > 0 ? [qty] : [1];
    }
    if (splitType === 'all') {
      return [max];
    }
    if (splitType === 'pairs') {
      const options = [];
      for (let i = 2; i <= max; i += 2) {
        options.push(i);
      }
      // Fallback: if no even options (e.g., max === 1), allow max
      return options.length ? options : [max];
    }
    const options = [];
    for (let i = 1; i <= max; i += 1) {
      options.push(i);
    }
    return options;
  };

  const quantityOptions = buildQuantityOptions();

  // Seat Transparency: allocated seats for selected quantity (from first N tickets, sorted by id)
  const allocatedSeatsText = (() => {
    const tickets = ticketGroup?.tickets || [];
    if (!tickets.length || quantity < 1) return null;
    const sorted = [...tickets].sort((a, b) => (a.id || 0) - (b.id || 0));
    const sliced = sorted.slice(0, quantity);
    const seats = sliced
      .map((t) => {
        const seat = t.seat_number ?? t.seat_numbers ?? '';
        const row = t.row_number ?? t.row ?? '';
        if (row && seat) return `שורה ${row} כיסא ${seat}`;
        if (seat) return String(seat);
        if (row) return `שורה ${row}`;
        return null;
      })
      .filter(Boolean);
    if (!seats.length) return null;
    return seats.join(', ');
  })();

  const checkoutCurrency = useMemo(() => {
    if (orderData?.currency) return String(orderData.currency).toUpperCase();
    if (acceptedOffer?.currency) return String(acceptedOffer.currency).toUpperCase();
    return resolveTicketCurrency(ticket);
  }, [orderData?.currency, acceptedOffer?.currency, ticket]);

  const curSym = currencySymbol(checkoutCurrency);

  // Listing unit base in event currency (ILS often integer in API; GBP/EUR allow decimals)
  const listUnitFace = getTicketBaseNumeric(ticket);
  const offerBaseAmountStr = isNegotiatedPrice && acceptedOffer?.amount != null ? String(acceptedOffer.amount) : null;
  const negotiatedQty = lockedQuantity || initialQuantity || 1;
  const negotiatedBaseTotal = offerBaseAmountStr != null ? parseFloat(offerBaseAmountStr) : null;
  const negotiatedUnitBase = negotiatedBaseTotal != null && negotiatedQty > 0 ? negotiatedBaseTotal / negotiatedQty : null;
  const basePriceNum = negotiatedUnitBase != null ? negotiatedUnitBase : listUnitFace;
  const listBaseSubtotalShekels =
    !isNegotiatedPrice && listUnitFace > 0 ? listUnitFace * quantity : 0;
  const negotiatedBundleBreakdown =
    isNegotiatedPrice && negotiatedBaseTotal != null && negotiatedBaseTotal > 0
      ? buyerChargeFromBase(negotiatedBaseTotal)
      : null;
  const listBreakdown =
    !isNegotiatedPrice && listBaseSubtotalShekels > 0 ? buyerChargeFromBase(listBaseSubtotalShekels) : null;
  const unitDisplayPrice =
    !isNaN(basePriceNum) && basePriceNum > 0 ? buyerChargeFromBase(basePriceNum).totalAmount : 0;
  const effectivePrice = String(negotiatedBaseTotal != null ? negotiatedBaseTotal : listUnitFace);
  const effectiveUnitPrice = negotiatedUnitBase != null ? negotiatedUnitBase : listUnitFace;
  const unitPriceForDisplay = unitDisplayPrice;
  const standardReceiptBaseTotal = listBreakdown?.baseAmount ?? 0;
  const standardReceiptTotalPay = listBreakdown?.totalAmount ?? 0;
  const standardReceiptFeeTotal = listBreakdown?.serviceFee ?? 0;

  // Update quantity when initialQuantity prop changes
  useEffect(() => {
    // If there's a locked quantity from accepted offer, use that
    if (lockedQuantity) {
      const qty = typeof lockedQuantity === 'number' ? lockedQuantity : parseInt(lockedQuantity, 10);
      if (!isNaN(qty) && qty > 0) {
        setQuantity(qty);
      }
    } else if (splitType === 'all') {
      // Strongly enforce: must buy all
      setQuantity(availableQuantity);
    } else {
      const options = buildQuantityOptions();
      let defaultQty = initialQuantity;
      if (!options.includes(defaultQty)) {
        defaultQty = options[0];
      }
      setQuantity(defaultQty);
    }
  }, [initialQuantity, availableQuantity, lockedQuantity, splitType]);

  // Handle quantity change with validation
  const handleQuantityChange = (e) => {
    const newQuantity = parseInt(e.target.value, 10);
    if (isNaN(newQuantity)) return;

    if (!quantityOptions.includes(newQuantity)) {
      if (splitType === 'all') {
        setError('You must buy all tickets together');
      } else if (splitType === 'pairs') {
        setError('Tickets can only be bought in pairs');
      } else {
        setError(`ניתן לבחור עד ${availableQuantity} כרטיסים בלבד`);
      }
      return;
    }

    setQuantity(newQuantity);
    setError(''); // Clear any previous errors
  };

  const handleGuestChange = (e) => {
    setGuestForm({
      ...guestForm,
      [e.target.name]: e.target.value,
    });
  };

  const handlePaymentChange = (e) => {
    let value = e.target.value;
    
    // Format card number with spaces (LTR format for numbers)
    if (e.target.name === 'cardNumber') {
      // Remove all spaces first, then add them back in groups of 4
      value = value.replace(/\s/g, '').replace(/(.{4})/g, '$1 ').trim();
      if (value.length > 19) return; // Max 16 digits + 3 spaces = 19 chars
    }
    
    // Format expiry date (MM/YY format - standard format)
    if (e.target.name === 'expiryDate') {
      // Remove all non-digits
      value = value.replace(/\D/g, '');
      // Add slash after 2 digits
      if (value.length >= 2) {
        value = value.substring(0, 2) + '/' + value.substring(2, 4);
      }
      if (value.length > 5) return; // MM/YY = 5 chars max
    }
    
    // CVV - only numbers, max 3-4 digits
    if (e.target.name === 'cvv') {
      value = value.replace(/\D/g, '');
      if (value.length > 4) return;
    }
    
    setPaymentForm({
      ...paymentForm,
      [e.target.name]: value,
    });
  };

  const handleInfoSubmit = async (e) => {
    e.preventDefault();
    if (infoStepBusy) return;
    setInfoStepBusy(true);
    setError('');
    const q = typeof quantity === 'number' ? quantity : parseInt(quantity, 10);
    const availNum = typeof availableQuantity === 'number' ? availableQuantity : parseInt(availableQuantity, 10);
    const validOptions = buildQuantityOptions();
    if (isNaN(q) || q < 1 || q > availNum) {
      setError(`כמות לא תקינה. ניתן לבחור בין 1 ל-${availNum} כרטיסים`);
      setInfoStepBusy(false);
      return;
    }
    if (!validOptions.includes(q)) {
      if (splitType === 'all') {
        setError('חובה לקנות את כל הכמות יחד');
      } else if (splitType === 'pairs') {
        setError('ניתן לקנות בזוגות בלבד');
      } else {
        setError(`כמות לא תקינה. בחר מתוך: ${validOptions.join(', ')}`);
      }
      setInfoStepBusy(false);
      return;
    }
    if (!user) {
      if (!guestForm.email || !guestForm.phone) {
        setError('אנא מלא את כל השדות הנדרשים');
        setInfoStepBusy(false);
        return;
      }
      const gErr = validateGuestContact(guestForm.email, guestForm.phone);
      if (gErr) {
        setError(gErr);
        setInfoStepBusy(false);
        return;
      }
    }
    setError('');
    setStep('payment');
    setInfoStepBusy(false);
  };

  const handlePaymentSubmit = async (e) => {
    console.log('Starting payment...');
    e.preventDefault();
    e.stopPropagation();
    if (checkoutSucceeded || transactionCompleteRef.current) {
      return;
    }
    if (loading) {
      return;
    }
    setError('');
    const payErr = validateMockPaymentFields(paymentForm);
    if (payErr) {
      setError(payErr);
      return;
    }
    setLoading(true);
    setPaymentPhase('idle');
    paymentSubmittingRef.current = true;

    try {
      // Validate quantity before processing payment
      if (quantity < 1 || quantity > availableQuantity) {
        throw new Error(`כמות לא תקינה. ניתן לבחור בין 1 ל-${availableQuantity} כרטיסים`);
      }
      
      let baseAmount, serviceFee, totalAmount;
      
      if (isNegotiatedPrice) {
        const raw = acceptedOffer.amount;
        const negotiatedBase = typeof raw === 'number' ? raw : parseFloat(String(raw));
        if (isNaN(negotiatedBase) || negotiatedBase <= 0) {
          throw new Error('מחיר הצעה לא תקין');
        }
        const ch = buyerChargeFromBase(negotiatedBase);
        baseAmount = ch.baseAmount;
        serviceFee = ch.serviceFee;
        totalAmount = ch.totalAmount;
      } else {
        const unitFace = listUnitFace;
        if (!Number.isFinite(unitFace) || unitFace < 0) {
          throw new Error('מחיר כרטיס לא תקין');
        }
        const ch = buyerChargeFromBase(unitFace * quantity);
        baseAmount = ch.baseAmount;
        serviceFee = ch.serviceFee;
        totalAmount = ch.totalAmount;
      }
      
      // Final validation
      if (isNaN(baseAmount) || baseAmount <= 0 || isNaN(totalAmount) || totalAmount <= 0) {
        throw new Error('מחיר כרטיס לא תקין');
      }
      
      // CRITICAL: Store the actual paid amounts for the success screen (Phase 2: integers for negotiated)
      const paidSnapshot = {
        baseAmount: baseAmount.toFixed(2),
        serviceFee: serviceFee.toFixed(2),
        totalAmount: totalAmount.toFixed(2),
      };
      setPaidAmounts(paidSnapshot);
      
      // CRITICAL DEBUG: Trace all values before payment
      console.log('=== PAYMENT FLOW DEBUG ===');
      console.log('listUnitFace (shekels):', listUnitFace, 'unitDisplayPrice:', unitDisplayPrice);
      console.log('isNegotiatedPrice:', isNegotiatedPrice);
      console.log('acceptedOffer:', acceptedOffer ? {
        id: acceptedOffer.id,
        amount: acceptedOffer.amount,
        quantity: acceptedOffer.quantity,
        status: acceptedOffer.status
      } : 'null');
      console.log('quantity (state):', quantity, 'type:', typeof quantity);
      console.log('lockedQuantity:', lockedQuantity);
      console.log('availableQuantity:', availableQuantity);
      console.log('ticket.id:', ticket?.id);
      console.log('ticket.event_name:', ticket?.event_name);
      console.log('ticket.event:', ticket?.event);
      console.log('Base amount (calculated):', baseAmount, 'type:', typeof baseAmount);
      console.log('Service fee (calculated):', serviceFee, 'type:', typeof serviceFee);
      console.log('Total amount (calculated):', totalAmount, 'type:', typeof totalAmount);
      
      // Get listing_group_id from ticketGroup if available (CRITICAL for grouped tickets)
      const listingGroupId = ticketGroup?.listing_group_id || ticket?.listing_group_id;
      console.log('Listing Group ID:', listingGroupId);
      console.log('========================');
      
      const finalTotal = totalAmount;
      console.log('finalTotal=', finalTotal, 'isNegotiated=', isNegotiatedPrice);
      
      // Step 1: Simulate payment - send total amount (with service fee)
      console.log('Calling paymentAPI.simulatePayment...');
      console.log('Payment simulation - Listing Group ID:', listingGroupId);
      const paymentData = {
        ticket_id: ticket.id,
        amount: finalTotal,
        quantity: quantity,
        timestamp: Date.now(),
        listing_group_id: listingGroupId, // CRITICAL: Send listing_group_id so backend checks group availability
      };

      // CRITICAL: If this is a negotiated price, include offer_id
      if (isNegotiatedPrice && acceptedOffer && acceptedOffer.id) {
        paymentData.offer_id = acceptedOffer.id;
        console.log('Including offer_id in payment simulation:', acceptedOffer.id);
      }
      if (!user && guestForm?.email?.trim()) {
        paymentData.guest_email = guestForm.email.trim();
      }

      await ensureCsrfToken();
      const paymentResponse = await paymentAPI.simulatePayment(paymentData);

      console.log('Payment response:', paymentResponse);

      if (!paymentResponse.data || !paymentResponse.data.success) {
        throw new Error(paymentResponse.data?.message || 'סימולציית התשלום נכשלה');
      }

      // Step 2: Create order - ensure total_amount is a Number
      console.log('Creating order...');
      setPaymentPhase('creating_order');
      let orderResponse;
      // Get listing_group_id from ticketGroup if available
      const listing_group_id = ticketGroup?.listing_group_id || ticket?.listing_group_id;
      
      // Ensure all values are properly defined and formatted
      const ticketId = ticket?.id;
      const eventName = ticket?.event_name || ticket?.event?.name || 'אירוע';
      
      // Ensure quantity is a valid integer
      const orderQuantity = typeof quantity === 'number' ? quantity : parseInt(quantity, 10);
      if (isNaN(orderQuantity) || orderQuantity < 1) {
        throw new Error('שגיאה: כמות לא תקינה');
      }
      
      // Use finalTotal (exact base*1.10) for order - NOT totalAmount which may have been rounded
      const orderTotalAmount = finalTotal;
      
      if (!ticketId) {
        throw new Error('שגיאה: לא נמצא מזהה כרטיס');
      }
      
      if (isNaN(orderTotalAmount) || orderTotalAmount <= 0) {
        throw new Error('שגיאה: סכום הזמנה לא תקין');
      }
      
      // Final validation before API call
      console.log('=== FINAL VALIDATION ===');
      console.log('ticketId:', ticketId, 'type:', typeof ticketId);
      console.log('orderQuantity:', orderQuantity, 'type:', typeof orderQuantity);
      console.log('orderTotalAmount:', orderTotalAmount, 'type:', typeof orderTotalAmount);
      console.log('eventName:', eventName, 'type:', typeof eventName);
      console.log('listing_group_id:', listing_group_id, 'type:', typeof listing_group_id);
      console.log('======================');
      
      if (user) {
        // Authenticated user checkout
        const orderData = {
          ticket: ticketId,
          total_amount: orderTotalAmount,
          quantity: orderQuantity,
          event_name: eventName,
        };
        
        // CRITICAL: If this is a negotiated price from an accepted offer, include offer_id
        // This tells the backend to bypass price validation and use the offer amount
        if (isNegotiatedPrice && acceptedOffer && acceptedOffer.id) {
          orderData.offer_id = acceptedOffer.id;
          console.log('Including offer_id in payload:', acceptedOffer.id);
        }
        
        // Only add listing_group_id if it exists
        if (listing_group_id) {
          orderData.listing_group_id = listing_group_id;
        }
        
        console.log('PAYLOAD (Authenticated):', JSON.stringify(orderData, null, 2));
        console.log('Payload values:', {
          ticket: typeof orderData.ticket,
          total_amount: typeof orderData.total_amount,
          quantity: typeof orderData.quantity,
          event_name: typeof orderData.event_name,
          offer_id: orderData.offer_id ? typeof orderData.offer_id : 'null',
          listing_group_id: listing_group_id ? typeof listing_group_id : 'null'
        });

        await ensureCsrfToken();
        orderResponse = await orderAPI.createOrder(orderData);
      } else {
        // Guest checkout
        const orderData = {
          guest_email: guestForm.email.trim(),
          guest_phone: guestForm.phone.trim(),
          ticket_id: ticketId,
          total_amount: orderTotalAmount,
          quantity: orderQuantity,
          event_name: eventName,
        };
        
        // CRITICAL: If this is a negotiated price from an accepted offer, include offer_id
        if (isNegotiatedPrice && acceptedOffer && acceptedOffer.id) {
          orderData.offer_id = acceptedOffer.id;
          console.log('Including offer_id in payload (Guest):', acceptedOffer.id);
        }
        
        // Only add listing_group_id if it exists
        if (listing_group_id) {
          orderData.listing_group_id = listing_group_id;
        }
        
        console.log('PAYLOAD (Guest):', JSON.stringify(orderData, null, 2));
        console.log('Payload values:', {
          ticket_id: typeof orderData.ticket_id,
          total_amount: typeof orderData.total_amount,
          quantity: typeof orderData.quantity,
          event_name: typeof orderData.event_name,
          offer_id: orderData.offer_id ? typeof orderData.offer_id : 'null',
          listing_group_id: listing_group_id ? typeof listing_group_id : 'null'
        });

        await ensureCsrfToken();
        orderResponse = await orderAPI.guestCheckout(orderData);
      }

      console.log('Order response:', orderResponse);

      const pendingOrder = orderResponse.data;
      const pendingId = pendingOrder?.id;
      if (pendingId == null) {
        throw new Error('יצירת ההזמנה נכשלה — לא התקבל מזהה הזמנה');
      }

      setPaymentPhase('confirming_payment');
      await authAPI.getCsrf().catch(() => {});

      const confirmPayload = { mock_payment_ack: true };
      const orderTok = pendingOrder?.payment_confirm_token;
      if (orderTok) {
        confirmPayload.payment_confirm_token = String(orderTok);
      }
      const vitePaySecret = import.meta.env.VITE_MOCK_PAYMENT_WEBHOOK_SECRET;
      if (vitePaySecret != null && String(vitePaySecret).trim() !== '') {
        confirmPayload.payment_secret = String(vitePaySecret).trim();
      }
      if (!user && guestForm?.email?.trim()) {
        confirmPayload.guest_email = guestForm.email.trim();
      }
      const confirmResponse = await orderAPI.confirmPayment(pendingId, confirmPayload);
      orderResponse = confirmResponse;

      const raw = orderResponse.data;
      if (!raw) {
        throw new Error('יצירת ההזמנה נכשלה');
      }
      const resolvedId = raw.id ?? raw.order_id ?? raw.order?.id ?? raw.pk;
      if (resolvedId == null) {
        throw new Error('יצירת ההזמנה נכשלה — לא התקבל מזהה הזמנה');
      }
      const orderPayload = { ...raw, id: resolvedId };

      // Snapshot FIRST (sync) — success UI must not depend on PDF or batched state
      successSnapshotRef.current = {
        orderId: resolvedId,
        orderData: orderPayload,
        paidAmounts: paidSnapshot,
      };

      setOrderId(resolvedId);
      setOrderData(orderPayload);

      reservationRef.current = false;
      transactionCompleteRef.current = true;
      setCheckoutSucceeded(true);
      setStep('success');

      // PDF after success — never block transition (was causing payment form to reappear if PDF hung)
      const emailForPdf = user ? null : guestForm.email.trim();
      void (async () => {
        try {
          const pdfResponse = await ticketAPI.downloadPDF(ticket.id, emailForPdf);
          const ct = ticketFileMimeFromAxiosHeaders(pdfResponse.headers);
          const blob = new Blob([pdfResponse.data], { type: ct });
          const url = window.URL.createObjectURL(blob);
          setPdfUrl(url);
        } catch (pdfError) {
          toastError('לא ניתן להכין את קובץ הכרטיס כרגע. ניתן להוריד שוב מעמוד ההזמנה.');
        }
      })();
    } catch (err) {
      const res = err.response;
      console.error('Checkout Error Payload:', res?.data);
      console.error('[CheckoutModal] handlePaymentSubmit failed', {
        status: res?.status,
        data: res?.data,
        message: err.message,
      });
      const formatted = formatCheckoutBackendError(err);
      const detail =
        formatted ||
        (typeof res?.data?.detail === 'string' ? res.data.detail : '') ||
        (typeof res?.data?.error === 'string' ? res.data.error : '') ||
        (typeof res?.data === 'string' && !responseDataLooksLikeHtml(res.data) ? res.data : '') ||
        err.message ||
        '';
      const userFacing =
        detail === CHECKOUT_CSRF_HTML_MESSAGE
          ? detail
          : detail
            ? `לא ניתן לשמור: ${detail}`
            : 'שגיאה בתקשורת עם השרת';
      setError(userFacing);
      toastError(userFacing);
      // Enterprise UX: Show Toast for "ticket was just sold" - beautiful feedback instead of raw alert
      const isSoldError = /sold|נמכר|just sold/i.test(userFacing);
      if (isSoldError && onErrorToParent) {
        onErrorToParent({ message: 'הכרטיס נמכר ברגע זה. ריעננו את הרשימה – נסה כרטיס אחר.', type: 'error' });
      }
    } finally {
      paymentSubmittingRef.current = false;
      setLoading(false);
      setPaymentPhase('idle');
    }
  };

  const handleDownloadPDF = async (ticketId, index = null) => {
    if (!ticketId) {
      const msg = 'שגיאה: מזהה כרטיס חסר';
      setError(msg);
      toastError(msg);
      return;
    }
    if (pdfDownloadBusyId != null) {
      return;
    }
    console.log('Downloading ticket ID:', ticketId);
    setPdfDownloadBusyId(ticketId);
    try {
      const email = user ? null : (guestForm?.email?.trim() || null);
      const response = await ticketAPI.downloadPDF(ticketId, email);
      downloadTicketFromAxiosBlob(response, { ticketId, index });
    } catch (err) {
      const msg = 'הורדת הכרטיס נכשלה. אנא נסה שוב מאוחר יותר.';
      setError(msg);
      toastError(msg);
    } finally {
      setPdfDownloadBusyId(null);
    }
  };

  // Reserve once per ticket: logged-in users can hold on info step; guests only on payment step
  // (email + CSRF warm — fixes mobile Safari generic "לא ניתן לשמור את הכרטיס").
  useEffect(() => {
    const tid = ticket?.id;
    if (!tid) return undefined;

    if (!user && step !== 'payment' && !skipCartReserveForNegotiatedOffer) {
      return undefined;
    }

    const reserveTicket = async () => {
      if (stepRef.current === 'success') return;
      if (reservationRef.current) return;

      try {
        if (skipCartReserveForNegotiatedOffer) {
          const cr = acceptedOffer?.checkout_time_remaining;
          const budget =
            typeof cr === 'number' && cr > 0 ? cr : OFFER_CHECKOUT_FALLBACK_SECONDS;
          timerBudgetRef.current = budget;
          setTimeRemaining(budget);
          setReservationActive(true);
          return;
        }

        if (ticket.status && ticket.status !== 'active') {
          setError('הכרטיס אינו זמין כרגע. אנא נסה כרטיס אחר.');
          setTimeout(() => {
            handleClose();
          }, 3000);
          return;
        }

        const email = user ? null : guestEmailRef.current || null;
        const listingGroupId = ticketGroup?.listing_group_id || ticket?.listing_group_id;
        console.log('Reserving Ticket ID:', tid, 'listingGroupId:', listingGroupId);
        await ensureCsrfToken();
        const response = await ticketAPI.reserveTicket(tid, email);

        if (response.data && response.data.success) {
          reservationRef.current = true;
          setReservationActive(true);
          if (response.data.expires_at) {
            const expiresAt = new Date(response.data.expires_at);
            const now = new Date();
            const remaining = Math.max(0, Math.floor((expiresAt - now) / 1000));
            timerBudgetRef.current = remaining;
            setTimeRemaining(remaining);
          } else {
            timerBudgetRef.current = CART_RESERVE_SECONDS;
            setTimeRemaining(CART_RESERVE_SECONDS);
          }
          console.log('Ticket reserved successfully');
        }
      } catch (err) {
        const res = err.response;
        console.error('[CheckoutModal] reserveTicket failed', {
          status: res?.status,
          data: res?.data,
          ticketId: tid,
        });
        console.error('Checkout Error Payload (reserve):', res?.data);
        if (res?.data?.status === 'reserved' || res?.data?.error?.includes('someone else')) {
          const errorMsg = res?.data?.error || 'הכרטיס נמצא כעת בעגלה של מישהו אחר. הוא עשוי להיות זמין שוב בעוד כמה דקות.';
          setError(errorMsg);
          toastError(errorMsg);
          setTimeout(() => {
            handleClose();
          }, 5000);
        } else if (res?.data?.error?.includes('no longer available') || res?.data?.error?.includes('not available')) {
          const errorMsg = res?.data?.error || 'הכרטיס אינו זמין עוד. אנא נסה כרטיס אחר.';
          setError(errorMsg);
          toastError(errorMsg);
          setTimeout(() => {
            handleClose();
          }, 3000);
        } else {
          const detail = formatCheckoutBackendError(err);
          const suffix =
            detail ||
            (typeof res?.data?.error === 'string' ? res.data.error : '') ||
            (typeof res?.data?.detail === 'string' ? res.data.detail : '') ||
            err.message ||
            '';
          const errorMsg =
            suffix === CHECKOUT_CSRF_HTML_MESSAGE
              ? suffix
              : suffix
                ? `לא ניתן לשמור: ${suffix}`
                : 'לא ניתן לשמור את הכרטיס כרגע. אנא נסה שוב.';
          setError(errorMsg);
          toastError(errorMsg);
        }
      }
    };

    void reserveTicket();

    return () => {
      if (transactionCompleteRef.current) return;
      if (skipCartReserveForNegotiatedOffer) return;
      if (reservationRef.current) {
        const email = user ? null : guestEmailRef.current || null;
        reservationRef.current = false;
        setReservationActive(false);
        void ticketAPI.releaseReservation(tid, email).catch(() => {});
      }
    };
  }, [ticket?.id, user, skipCartReserveForNegotiatedOffer, acceptedOffer?.id, step]);

  /** Countdown: 10m cart lock ticks after reserve; 24h offer window ticks from open (info + payment). */
  useEffect(() => {
    if (checkoutSucceeded || step === 'success') {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return undefined;
    }

    const negotiated = skipCartReserveForNegotiatedOffer;
    const shouldTick =
      (negotiated && (step === 'info' || step === 'payment')) ||
      (!negotiated && reservationActive && (step === 'info' || step === 'payment'));

    if (!shouldTick) {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return undefined;
    }

    timerRef.current = setInterval(() => {
      setTimeRemaining((prev) => {
        if (paymentSubmittingRef.current || transactionCompleteRef.current) {
          return prev;
        }
        if (prev <= 1) {
          clearInterval(timerRef.current);
          timerRef.current = null;
          if (transactionCompleteRef.current || paymentSubmittingRef.current) {
            return prev;
          }
          if (!skipCartReserveForNegotiatedOffer) {
            const releaseReservation = async () => {
              try {
                const email = user ? null : guestForm.email || null;
                await ticketAPI.releaseReservation(ticket?.id, email);
                reservationRef.current = false;
                setReservationActive(false);
              } catch {
                /* best-effort release */
              }
            };
            void releaseReservation();
          }
          const expiredMsg = skipCartReserveForNegotiatedOffer
            ? 'פג זמן התשלום להצעה. סגרו ונסו שוב או פנו לתמיכה.'
            : 'פג הזמן. הכרטיסים שוחררו חזרה למלאי. אנא נסה שוב.';
          setError(expiredMsg);
          toastError(expiredMsg);
          setStep('info');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [
    step,
    reservationActive,
    skipCartReserveForNegotiatedOffer,
    checkoutSucceeded,
    ticket?.id,
    user,
    guestForm.email,
  ]);

  /** Always H:MM:SS so multi-hour windows never show confusing mm:ss (e.g. 239:53 for ~4h). */
  const formatTime = (rawSeconds) => {
    const seconds = Math.max(0, Math.floor(Number(rawSeconds) || 0));
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const defaultTimerBudget = skipCartReserveForNegotiatedOffer
    ? OFFER_CHECKOUT_FALLBACK_SECONDS
    : CART_RESERVE_SECONDS;
  const budget =
    timerBudgetRef.current > 0 ? timerBudgetRef.current : defaultTimerBudget;
  const progressPercentage =
    budget > 0 ? Math.min(100, Math.max(0, ((budget - timeRemaining) / budget) * 100)) : 0;

  const handleClose = async () => {
    if (pdfUrl) {
      window.URL.revokeObjectURL(pdfUrl);
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    
    // Release reservation if not completed
    if (transactionCompleteRef.current) {
      onClose();
      return;
    }
    if (!skipCartReserveForNegotiatedOffer && reservationRef.current && step !== 'success') {
      try {
        const email = user ? null : guestForm.email || null;
        await ticketAPI.releaseReservation(ticket.id, email);
        reservationRef.current = false;
        setReservationActive(false);
      } catch {
        /* best-effort release */
      }
    }

    onClose();
  };

  // Success screen — must win over payment step if checkoutSucceeded (PDF no longer blocks transition)
  if (checkoutSucceeded || step === 'success') {
    const snap = successSnapshotRef.current;
    const resolvedOrderId = orderId ?? snap?.orderId;
    const resolvedOrderData = orderData ?? snap?.orderData;
    const resolvedPaid = paidAmounts ?? snap?.paidAmounts;
    const payIso = String(
      resolvedOrderData?.currency || acceptedOffer?.currency || resolveTicketCurrency(ticket)
    ).toUpperCase();
    const paySym = currencySymbol(payIso);
    return portalCheckoutRoot(
      <div className="success-overlay" onClick={handleClose}>
        <div className="success-celebration" onClick={(e) => e.stopPropagation()}>
          <div className="success-celebration-content">
            <div className="success-checkmark-large">
              <svg viewBox="0 0 100 100" className="checkmark-svg">
                <circle cx="50" cy="50" r="45" className="checkmark-circle" />
                <path d="M30 50 L45 65 L70 35" className="checkmark-path" />
              </svg>
            </div>
            <h1 className="success-title-large">הרכישה הושלמה</h1>
            <h2 className="success-subtitle">הזמנה אושרה בהצלחה!</h2>
            <p className="success-order-number">מספר הזמנה: #{resolvedOrderId}</p>
            
            <div className="success-ticket-summary">
              <h3>{ticket?.event_name || 'אירוע'}</h3>
              <div className="success-ticket-details">
                <p><strong>מיקום:</strong> {ticket?.venue || 'לא צוין'}</p>
                {isNegotiatedPrice && (
                  <p><strong>מחיר מוסכם:</strong> <span style={{color: '#10b981', fontSize: '0.9em'}}>{paySym}{formatAmountForCurrency(resolvedPaid?.baseAmount ?? effectivePrice, payIso)}</span></p>
                )}
                {quantity > 1 && (
                  <p><strong>כמות:</strong> {quantity}</p>
                )}
                {resolvedOrderData?.total_paid_by_buyer != null || resolvedOrderData?.final_negotiated_price != null ? (
                  <>
                    {resolvedOrderData?.final_negotiated_price != null && (
                      <p><strong>מחיר מוסכם (למוכר):</strong> {paySym}{formatAmountForCurrency(resolvedOrderData.final_negotiated_price, payIso)}</p>
                    )}
                    {resolvedOrderData?.buyer_service_fee != null && Number(resolvedOrderData.buyer_service_fee) > 0 && (
                      <p><strong>עמלת שירות:</strong> {paySym}{formatAmountForCurrency(resolvedOrderData.buyer_service_fee, payIso)}</p>
                    )}
                    <p><strong>סה״כ שולם (לקונה):</strong> {paySym}{formatAmountForCurrency(resolvedOrderData.total_paid_by_buyer ?? resolvedOrderData.total_amount, payIso)}</p>
                  </>
                ) : resolvedPaid ? (
                  <>
                    <p><strong>מחיר כרטיסים:</strong> {paySym}{formatAmountForCurrency(resolvedPaid.baseAmount, payIso)}</p>
                    <p><strong>עמלת שירות (10%):</strong> {paySym}{formatAmountForCurrency(resolvedPaid.serviceFee, payIso)}</p>
                    <p><strong>סה"כ שולם:</strong> {paySym}{formatAmountForCurrency(resolvedPaid.totalAmount, payIso)}</p>
                  </>
                ) : (
                  <>
                    <p><strong>מחיר כרטיסים:</strong> {paySym}{(negotiatedBundleBreakdown || listBreakdown)?.baseAmount != null ? formatAmountForCurrency((negotiatedBundleBreakdown || listBreakdown).baseAmount, payIso) : '—'}</p>
                    <p><strong>עמלת שירות (10%):</strong> {paySym}{(negotiatedBundleBreakdown || listBreakdown)?.serviceFee != null ? formatAmountForCurrency((negotiatedBundleBreakdown || listBreakdown).serviceFee, payIso) : '—'}</p>
                    <p><strong>סה"כ שולם:</strong> {paySym}{(negotiatedBundleBreakdown || listBreakdown)?.totalAmount != null ? formatAmountForCurrency((negotiatedBundleBreakdown || listBreakdown).totalAmount, payIso) : '—'}</p>
                  </>
                )}
              </div>
            </div>

            {!user && (
              <div className="guest-post-purchase-panel" role="region" aria-label="הוראות לאורח">
                <p className="guest-post-purchase-lead">
                  <strong>הרכישה הושלמה ללא הרשמה.</strong> הורידו את קובץ הכרטיס כעת והשמרו אותו בטלפון או במחשב לפני האירוע.
                </p>
                <ul className="guest-post-purchase-list">
                  <li>לחצו על &quot;הורדת כרטיס&quot; — זה הכרטיס התקף לכניסה.</li>
                  <li>אם הזנתם אימייל בקופה, נשלח אליכם עותק (בדקו גם בתיקיית ספאם).</li>
                  <li>אין חובה להירשם; אפשר לפתוח חשבון מאוחר יותר כדי לראות הזמנות עתידיות בדשבורד.</li>
                </ul>
              </div>
            )}
            
            <div className="success-actions">
              <div className="success-download-buttons">
                {(() => {
                  const ticketIds = resolvedOrderData?.tickets?.length > 0
                    ? resolvedOrderData.tickets.map((t) => t.id)
                    : (resolvedOrderData?.ticket_ids?.length > 0 ? resolvedOrderData.ticket_ids : (ticket?.id ? [ticket.id] : []));
                  const CheckIcon = () => (
                    <span className="download-check-icon" aria-hidden="true">✓</span>
                  );
                  const DownloadIcon = () => (
                    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M10 2V12M10 12L6 8M10 12L14 8M3 14V16C3 17.1 3.9 18 5 18H15C16.1 18 17 17.1 17 16V14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  );
                  if (ticketIds.length > 1) {
                    return ticketIds.map((tid, idx) => (
                      <button
                        key={tid}
                        type="button"
                        onClick={() => handleDownloadPDF(tid, idx)}
                        className="success-download-button"
                        disabled={pdfDownloadBusyId != null}
                        data-e2e="checkout-success-pdf"
                      >
                        <CheckIcon />
                        <DownloadIcon />
                        {`הורד כרטיס ${idx + 1}`}
                      </button>
                    ));
                  }
                  if (ticketIds.length === 1) {
                    return (
                      <button
                        type="button"
                        onClick={() => handleDownloadPDF(ticketIds[0])}
                        className="success-download-button"
                        disabled={pdfDownloadBusyId != null}
                        data-e2e="checkout-success-pdf"
                      >
                        <CheckIcon />
                        <DownloadIcon />
                        הורדת כרטיס
                      </button>
                    );
                  }
                  return (
                    <button
                      type="button"
                      onClick={() => handleDownloadPDF(ticket?.id)}
                      className="success-download-button"
                      disabled={!ticket?.id || pdfDownloadBusyId != null}
                      data-e2e="checkout-success-pdf"
                    >
                      <CheckIcon />
                      <DownloadIcon />
                      הורדת כרטיס
                    </button>
                  );
                })()}
              </div>
              {user ? (
                <button
                  type="button"
                  onClick={() => {
                    navigate('/dashboard');
                    onClose();
                  }}
                  className="success-close-button success-primary-dashboard"
                >
                  מעבר לאזור האישי
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      navigate('/');
                      onClose();
                    }}
                    className="success-close-button success-primary-dashboard"
                  >
                    חזרה לעמוד הבית
                  </button>
                  <Link
                    to="/register"
                    className="success-register-cta"
                    onClick={onClose}
                  >
                    פתיחת חשבון (אופציונלי) — ניהול הזמנות
                  </Link>
                </>
              )}
              <button onClick={handleClose} className="success-close-button" type="button">
                סגור
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Payment screen — never after a completed checkout (even if step lags)
  if (step === 'payment' && !checkoutSucceeded) {
    return portalCheckoutRoot(
      <div className="modal-overlay checkout-modal-overlay" onClick={handleClose}>
        <div className="modal-content checkout-modal-shell" onClick={(e) => e.stopPropagation()}>
          <button type="button" className="close-button" onClick={handleClose} aria-label="סגירה">×</button>
          <p className="checkout-modal-brand">TradeTix</p>
          <div className="checkout-stepper" role="list" aria-label="שלבי קופה">
            <span className="checkout-step checkout-step--done" role="listitem">1 · פרטים</span>
            <span className="checkout-step-sep" aria-hidden>›</span>
            <span className="checkout-step checkout-step--active" role="listitem">2 · תשלום</span>
          </div>
          <div className="secure-checkout-header">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10 1L3 4V9C3 13.55 6.16 17.74 10 19C13.84 17.74 17 13.55 17 9V4L10 1Z" fill="currentColor"/>
              <path d="M8 9L9 10L12 7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <h2>תשלום מאובטח</h2>
          </div>
          
          {/* Reservation Notice with Countdown Timer - at top */}
          <div className="reservation-notice reservation-timer-top">
            <div>
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M10 1L3 4V9C3 13.55 6.16 17.74 10 19C13.84 17.74 17 13.55 17 9V4L10 1Z" fill="currentColor"/>
                <path d="M8 9L9 10L12 7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <span>
                {skipCartReserveForNegotiatedOffer
                  ? 'הצעה מאושרת — יש לך עד 24 שעות להשלים את התשלום. זמן נותר:'
                  : 'רכישה ישירה — הכרטיס נעול בעגלה למשך 10 דקות. זמן נותר:'}
              </span>
              <span
                className={`timer-countdown ${
                  timeRemaining < (skipCartReserveForNegotiatedOffer ? 300 : 60) ? 'timer-warning' : ''
                } ${timeRemaining === 0 ? 'timer-expired' : ''}`}
              >
                {formatTime(timeRemaining)}
              </span>
            </div>
            <div className="progress-bar-container">
              <div 
                className="progress-bar-fill" 
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
          </div>

          <div className="ticket-summary">
            <h3>{ticket.event_name}</h3>
            <p>מיקום: {ticket.venue}</p>
            
            {/* PDF Verified Badge */}
            {(ticket.has_pdf_file || ticket.pdf_file_url) && (
              <div className="pdf-verified-badge">
                <svg width="16" height="16" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M10 1L3 4V9C3 13.55 6.16 17.74 10 19C13.84 17.74 17 13.55 17 9V4L10 1Z" fill="currentColor"/>
                  <path d="M8 9L9 10L12 7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <span>PDF מאומת - הקובץ מוכן למסירה</span>
              </div>
            )}
            
            {/* Quantity Selector */}
            <div className="quantity-selector-group">
              <label htmlFor="quantity-select-payment">כמות כרטיסים:</label>
              {lockedQuantity ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexDirection: 'row-reverse' }}>
                  <span style={{ 
                    padding: '0.875rem 1rem', 
                    border: '2px solid #e2e8f0', 
                    borderRadius: '8px', 
                    background: '#f8fafc',
                    fontWeight: '600',
                    color: '#475569'
                  }}>
                    {lockedQuantity} {lockedQuantity === 1 ? 'כרטיס' : 'כרטיסים'}
                  </span>
                  <span style={{ fontSize: '0.875rem', color: '#64748b', fontStyle: 'italic' }}>
                    (כמות נעולה לפי ההצעה)
                  </span>
                </div>
              ) : splitType === 'all' ? (
                <div className="locked-quantity-display">
                  <span>{availableQuantity} כרטיסים (חובה לקנות הכל יחד)</span>
                </div>
              ) : (
                <select
                  id="quantity-select-payment"
                  className="quantity-select"
                  value={quantity}
                  onChange={handleQuantityChange}
                  dir="rtl"
                >
                  {quantityOptions.map((num) => (
                    <option key={num} value={num}>
                      {num} {num === 1 ? 'כרטיס' : 'כרטיסים'}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {allocatedSeatsText && (
              <div className="allocated-seats-display">
                מושבים מוקצים: {allocatedSeatsText}
              </div>
            )}

            <div className="price-breakdown">
              {isNegotiatedPrice && (
                <div className="negotiated-price-badge" style={{
                  padding: '0.75rem',
                  background: '#d1fae5',
                  borderRadius: '8px',
                  marginBottom: '1rem',
                  textAlign: 'center',
                  color: '#065f46',
                  fontSize: '0.9rem'
                }}>
                  ✓ מחיר מוסכם: {curSym}{formatAmountForCurrency(offerBaseAmountStr ?? effectivePrice, checkoutCurrency)} סה"כ ל-{quantity} כרטיסים (במקום {curSym}{getTicketPrice(ticket)} ליחידה)
                </div>
              )}
              {isNegotiatedPrice ? (
                <>
                  <div className="price-row">
                    <span>מחיר ליחידה:</span>
                    <span>{curSym}{negotiatedUnitBase != null ? formatAmountForCurrency(negotiatedUnitBase, checkoutCurrency) : formatAmountForCurrency(unitPriceForDisplay, checkoutCurrency)}</span>
                  </div>
                  <div className="price-row">
                    <span>כמות:</span>
                    <span>{quantity}</span>
                  </div>
                  {allocatedSeatsText && (
                    <div className="price-row allocated-seats-row">
                      <span>מושבים מוקצים:</span>
                      <span>{allocatedSeatsText}</span>
                    </div>
                  )}
                  <div className="price-row">
                    <span>מחיר כרטיס</span>
                    <span>{curSym}{negotiatedBundleBreakdown ? formatAmountForCurrency(negotiatedBundleBreakdown.baseAmount, checkoutCurrency) : formatAmountForCurrency(0, checkoutCurrency)}</span>
                  </div>
                  <div className="price-row">
                    <span>עמלת שירות (10%)</span>
                    <span>{curSym}{negotiatedBundleBreakdown ? formatAmountForCurrency(negotiatedBundleBreakdown.serviceFee, checkoutCurrency) : formatAmountForCurrency(0, checkoutCurrency)}</span>
                  </div>
                  <div className="price-row total-row">
                    <span>סך הכל לתשלום:</span>
                    <span>{curSym}{negotiatedBundleBreakdown ? formatAmountForCurrency(negotiatedBundleBreakdown.totalAmount, checkoutCurrency) : formatAmountForCurrency(0, checkoutCurrency)}</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="price-row">
                    <span>מחיר כרטיס</span>
                    <span>{curSym}{formatAmountForCurrency(standardReceiptBaseTotal, checkoutCurrency)}</span>
                  </div>
                  <div className="price-row">
                    <span>כמות:</span>
                    <span>{quantity}</span>
                  </div>
                  {allocatedSeatsText && (
                    <div className="price-row allocated-seats-row">
                      <span>מושבים מוקצים:</span>
                      <span>{allocatedSeatsText}</span>
                    </div>
                  )}
                  <div className="price-row">
                    <span>עמלת שירות (10%)</span>
                    <span>{curSym}{formatAmountForCurrency(standardReceiptFeeTotal, checkoutCurrency)}</span>
                  </div>
                  <div className="price-row total-row">
                    <span>סך הכל לתשלום:</span>
                    <span>{curSym}{formatAmountForCurrency(standardReceiptTotalPay, checkoutCurrency)}</span>
                  </div>
                </>
              )}
            </div>
          </div>
          
          <form onSubmit={handlePaymentSubmit} className="payment-form">
            <div className="form-group">
              <label htmlFor="cardholderName">שם בעל הכרטיס *</label>
              <input
                type="text"
                id="cardholderName"
                name="cardholderName"
                value={paymentForm.cardholderName}
                onChange={handlePaymentChange}
                required
                placeholder="שם פרטי ומשפחה"
                dir="rtl"
              />
            </div>
            
            <div className="form-group">
              <label htmlFor="cardNumber">מספר כרטיס *</label>
              <input
                type="text"
                id="cardNumber"
                name="cardNumber"
                value={paymentForm.cardNumber}
                onChange={handlePaymentChange}
                required
                placeholder="1234 5678 9012 3456"
                maxLength="19"
                dir="ltr"
              />
            </div>
            
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="expiryDate">תאריך תפוגה *</label>
                <input
                  type="text"
                  id="expiryDate"
                  name="expiryDate"
                  value={paymentForm.expiryDate}
                  onChange={handlePaymentChange}
                  required
                  placeholder="MM/YY"
                  maxLength="5"
                  dir="ltr"
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="cvv">CVV *</label>
                <input
                  type="text"
                  id="cvv"
                  name="cvv"
                  value={paymentForm.cvv}
                  onChange={handlePaymentChange}
                  required
                  placeholder="123"
                  maxLength="4"
                  dir="ltr"
                />
              </div>
            </div>
            
            <p className="payment-note">
              <small>🔒 זהו סימולציה של תשלום. לא יתבצע תשלום אמיתי.</small>
            </p>
            
            {error && (
              <div className="error-message" role="alert" aria-live="polite">
                {error || 'שגיאה לא ידועה'}
              </div>
            )}
            
            <div className="button-group checkout-buttons-row modal-actions">
              <button
                type="button"
                onClick={() => setStep('info')}
                className="back-button checkout-row-btn modal-action-secondary"
                disabled={loading || timeRemaining === 0}
              >
                חזרה
              </button>
              <button
                type="submit"
                disabled={loading || checkoutSucceeded || timeRemaining === 0}
                className="checkout-button checkout-row-btn modal-action-primary"
              >
                {loading
                  ? paymentPhase === 'creating_order'
                    ? 'יוצר הזמנה...'
                    : paymentPhase === 'confirming_payment'
                      ? 'מעבד תשלום...'
                      : 'מעבד...'
                  : timeRemaining === 0
                    ? 'זמן פג'
                    : 'השלמת תשלום'}
              </button>
            </div>
            <div className="payment-security-badges">
              <div className="payment-icons">
                <svg width="40" height="24" viewBox="0 0 40 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <rect width="40" height="24" rx="4" fill="#1434CB"/>
                  <path d="M16.5 12C16.5 10.5 17.5 9.5 19 9.5C20.5 9.5 21.5 10.5 21.5 12C21.5 13.5 20.5 14.5 19 14.5C17.5 14.5 16.5 13.5 16.5 12Z" fill="white"/>
                  <path d="M23.5 12C23.5 10.5 24.5 9.5 26 9.5C27.5 9.5 28.5 10.5 28.5 12C28.5 13.5 27.5 14.5 26 14.5C24.5 14.5 23.5 13.5 23.5 12Z" fill="white"/>
                </svg>
                <svg width="40" height="24" viewBox="0 0 40 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <rect width="40" height="24" rx="4" fill="#EB001B"/>
                  <circle cx="15" cy="12" r="6" fill="#F79E1B"/>
                  <circle cx="25" cy="12" r="6" fill="#FF5F00"/>
                </svg>
              </div>
              <div className="ssl-badge">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M8 1L3 3V8C3 11.31 5.69 14 9 14C12.31 14 15 11.31 15 8V3L10 1L8 1Z" fill="#10b981"/>
                  <path d="M6 8L7.5 9.5L10 7" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <span>מוגן SSL</span>
              </div>
            </div>
          </form>
        </div>
      </div>
    );
  }

  // Info screen (initial)
  return portalCheckoutRoot(
    <div className="modal-overlay checkout-modal-overlay" onClick={handleClose}>
      <div className="modal-content checkout-modal-shell" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="close-button" onClick={handleClose} aria-label="סגירה">×</button>
        <p className="checkout-modal-brand">TradeTix</p>
        <div className="checkout-stepper" role="list" aria-label="שלבי קופה">
          <span className="checkout-step checkout-step--active" role="listitem">1 · פרטים</span>
          <span className="checkout-step-sep" aria-hidden>›</span>
          <span className="checkout-step" role="listitem">2 · תשלום</span>
        </div>
        <div className="secure-checkout-header">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M10 1L3 4V9C3 13.55 6.16 17.74 10 19C13.84 17.74 17 13.55 17 9V4L10 1Z" fill="currentColor"/>
            <path d="M8 9L9 10L12 7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <h2>סיכום והמשך לתשלום</h2>
        </div>
        
        
          <div className="ticket-summary">
            <h3>{ticket.event_name}</h3>
            <p>מיקום: {ticket.venue}</p>
            
            {/* Quantity Selector */}
            <div className="quantity-selector-group">
              <label htmlFor="quantity-select-info">כמות כרטיסים:</label>
              {lockedQuantity ? (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                  <span style={{ 
                    padding: '0.875rem 1rem', 
                    border: '2px solid #e2e8f0', 
                    borderRadius: '8px', 
                    background: '#f8fafc',
                    fontWeight: '600',
                    color: '#475569'
                  }}>
                    {lockedQuantity} {lockedQuantity === 1 ? 'כרטיס' : 'כרטיסים'}
                  </span>
                </div>
              ) : splitType === 'all' ? (
                <div className="locked-quantity-display">
                  <span>{availableQuantity} כרטיסים (חובה לקנות הכל יחד)</span>
                </div>
              ) : (
                <select
                  id="quantity-select-info"
                  className="quantity-select"
                  value={quantity}
                  onChange={handleQuantityChange}
                  dir="rtl"
                >
                  {quantityOptions.map((num) => (
                    <option key={num} value={num}>
                      {num} {num === 1 ? 'כרטיס' : 'כרטיסים'}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {allocatedSeatsText && (
              <div className="allocated-seats-display">
                מושבים מוקצים: {allocatedSeatsText}
              </div>
            )}

            <div className="price-breakdown">
              {isNegotiatedPrice && (
                <div className="negotiated-price-badge" style={{
                  padding: '0.75rem',
                  background: '#d1fae5',
                  borderRadius: '8px',
                  marginBottom: '1rem',
                  textAlign: 'center',
                  color: '#065f46',
                  fontSize: '0.9rem'
                }}>
                  ✓ מחיר מוסכם: {curSym}{formatAmountForCurrency(effectivePrice, checkoutCurrency)} סה"כ ל-{quantity} כרטיסים (במקום {curSym}{getTicketPrice(ticket)} ליחידה)
                </div>
              )}
              {isNegotiatedPrice ? (
                <>
                  <div className="price-row">
                    <span>מחיר ליחידה:</span>
                    <span>{curSym}{negotiatedUnitBase != null ? formatAmountForCurrency(negotiatedUnitBase, checkoutCurrency) : formatAmountForCurrency(unitPriceForDisplay, checkoutCurrency)}</span>
                  </div>
                  <div className="price-row">
                    <span>כמות:</span>
                    <span>{quantity}</span>
                  </div>
                  {allocatedSeatsText && (
                    <div className="price-row allocated-seats-row">
                      <span>מושבים מוקצים:</span>
                      <span>{allocatedSeatsText}</span>
                    </div>
                  )}
                  <div className="price-row">
                    <span>מחיר כרטיס</span>
                    <span>{curSym}{negotiatedBundleBreakdown ? formatAmountForCurrency(negotiatedBundleBreakdown.baseAmount, checkoutCurrency) : formatAmountForCurrency(0, checkoutCurrency)}</span>
                  </div>
                  <div className="price-row">
                    <span>עמלת שירות (10%)</span>
                    <span>{curSym}{negotiatedBundleBreakdown ? formatAmountForCurrency(negotiatedBundleBreakdown.serviceFee, checkoutCurrency) : formatAmountForCurrency(0, checkoutCurrency)}</span>
                  </div>
                  <div className="price-row total-row">
                    <span>סך הכל לתשלום:</span>
                    <span>{curSym}{negotiatedBundleBreakdown ? formatAmountForCurrency(negotiatedBundleBreakdown.totalAmount, checkoutCurrency) : formatAmountForCurrency(0, checkoutCurrency)}</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="price-row">
                    <span>מחיר כרטיס</span>
                    <span>{curSym}{formatAmountForCurrency(standardReceiptBaseTotal, checkoutCurrency)}</span>
                  </div>
                  <div className="price-row">
                    <span>כמות:</span>
                    <span>{quantity}</span>
                  </div>
                  {allocatedSeatsText && (
                    <div className="price-row allocated-seats-row">
                      <span>מושבים מוקצים:</span>
                      <span>{allocatedSeatsText}</span>
                    </div>
                  )}
                  <div className="price-row">
                    <span>עמלת שירות (10%)</span>
                    <span>{curSym}{formatAmountForCurrency(standardReceiptFeeTotal, checkoutCurrency)}</span>
                  </div>
                  <div className="price-row total-row">
                    <span>סך הכל לתשלום:</span>
                    <span>{curSym}{formatAmountForCurrency(standardReceiptTotalPay, checkoutCurrency)}</span>
                  </div>
                </>
              )}
            </div>
          </div>

        {user ? (
          <div className="user-checkout">
            <p>מחובר כ: <strong>{user.username}</strong></p>
            <p>אימייל: <strong>{user.email}</strong></p>
            {error && (
              <div className="error-message" role="alert" aria-live="polite">
                {error || 'שגיאה לא ידועה'}
              </div>
            )}
            <button
              type="button"
              onClick={handleInfoSubmit}
              disabled={loading || infoStepBusy}
              className="checkout-button"
            >
              {infoStepBusy ? 'ממשיך…' : 'המשך לתשלום'}
            </button>
          </div>
        ) : (
          <div className="guest-checkout">
            <p>המשך כאורח או <a href="/login">התחבר</a> לחשבון שלך</p>
            <form onSubmit={handleInfoSubmit}>
              <div className="form-group">
                <label htmlFor="email">אימייל *</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={guestForm.email}
                  onChange={handleGuestChange}
                  required
                  placeholder="your.email@example.com"
                />
              </div>
              <div className="form-group">
                <label htmlFor="phone">מספר טלפון *</label>
                <input
                  type="tel"
                  id="phone"
                  name="phone"
                  value={guestForm.phone}
                  onChange={handleGuestChange}
                  required
                  placeholder="050-1234567"
                />
              </div>
              {error && (
              <div className="error-message" role="alert" aria-live="polite">
                {error || 'שגיאה לא ידועה'}
              </div>
            )}
              <button
                type="submit"
                disabled={loading || infoStepBusy}
                className="checkout-button"
              >
                {infoStepBusy ? 'ממשיך…' : 'המשך לתשלום'}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};

export default CheckoutModal;
