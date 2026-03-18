import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { orderAPI, paymentAPI, ticketAPI } from '../services/api';
import { getTicketPrice, formatPrice, getUnitPriceWithFee, calculateServiceFee } from '../utils/priceFormat';
import './CheckoutModal.css';

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
  const [error, setError] = useState('');
  const [orderId, setOrderId] = useState(null);
  const [orderData, setOrderData] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [timeRemaining, setTimeRemaining] = useState(600); // 10 minutes in seconds
  const [paidAmounts, setPaidAmounts] = useState(null); // Store actual paid amounts: { baseAmount, serviceFee, totalAmount }
  const timerRef = useRef(null);
  const reservationRef = useRef(false); // Track if reservation was made
  const navigate = useNavigate();

  // Get locked quantity from accepted offer if it exists
  const isNegotiatedPrice = acceptedOffer && acceptedOffer.status === 'accepted';
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

  // CRITICAL: When acceptedOffer exists, base price = acceptedOffer.amount (negotiated), NOT ticket.asking_price
  const basePriceStr = getTicketPrice(ticket);
  const ticketBaseNum = parseFloat(basePriceStr) || 0;
  const offerBaseAmountStr = isNegotiatedPrice && acceptedOffer?.amount != null ? String(acceptedOffer.amount) : null;
  const negotiatedQty = lockedQuantity || initialQuantity || 1;
  const negotiatedBaseTotal = offerBaseAmountStr != null ? parseFloat(offerBaseAmountStr) : null;
  const negotiatedUnitBase = negotiatedBaseTotal != null && negotiatedQty > 0 ? negotiatedBaseTotal / negotiatedQty : null;
  const basePriceNum = negotiatedUnitBase != null ? negotiatedUnitBase : ticketBaseNum;
  // UNIFIED: Math.ceil(base * 1.10) - same as EventDetailsPage. Phase 2: ALWAYS whole numbers (no .90 or .99)
  const unitDisplayPrice = !isNaN(basePriceNum) && basePriceNum > 0 ? getUnitPriceWithFee(basePriceNum) : 0;
  const effectivePrice = String(negotiatedBaseTotal != null ? negotiatedBaseTotal : ticketBaseNum);
  const effectiveUnitPrice = negotiatedUnitBase != null ? negotiatedUnitBase : ticketBaseNum;
  const unitPriceForDisplay = unitDisplayPrice;
  
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
    setError('');
    const q = typeof quantity === 'number' ? quantity : parseInt(quantity, 10);
    const availNum = typeof availableQuantity === 'number' ? availableQuantity : parseInt(availableQuantity, 10);
    const validOptions = buildQuantityOptions();
    if (isNaN(q) || q < 1 || q > availNum) {
      setError(`כמות לא תקינה. ניתן לבחור בין 1 ל-${availNum} כרטיסים`);
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
      return;
    }
    if (!user) {
      if (!guestForm.email || !guestForm.phone) {
        setError('אנא מלא את כל השדות הנדרשים');
        return;
      }
    }
    setStep('payment');
  };

  const handlePaymentSubmit = async (e) => {
    console.log('Starting payment...');
    e.preventDefault();
    e.stopPropagation();
    setError('');
    setLoading(true);

    try {
      // Validate quantity before processing payment
      if (quantity < 1 || quantity > availableQuantity) {
        throw new Error(`כמות לא תקינה. ניתן לבחור בין 1 ל-${availableQuantity} כרטיסים`);
      }
      
      let baseAmount, serviceFee, totalAmount;
      
      if (isNegotiatedPrice) {
        // acceptedOffer.amount is the TOTAL base amount (before fee) for the bundle
        const raw = acceptedOffer.amount;
        const negotiatedBase = typeof raw === 'number' ? raw : parseFloat(String(raw));
        if (isNaN(negotiatedBase) || negotiatedBase <= 0) {
          throw new Error('מחיר הצעה לא תקין');
        }
        // Phase 2: Force strict rounding - finalTotal and unitDisplayPrice ALWAYS whole numbers (no 141.90 or .99)
        totalAmount = Math.ceil(negotiatedBase * 1.10); // Total = ceil(base * 1.10), always integer
        serviceFee = Math.ceil(negotiatedBase * 0.10);  // Service fee rounded up
        baseAmount = totalAmount - serviceFee;           // Base = total - fee, ensures base + fee = total (both integers)
      } else {
        // Regular flow: unitDisplayPrice = Math.ceil(base * 1.10), total = unitDisplayPrice * quantity
        baseAmount = unitDisplayPrice * quantity;
        serviceFee = 0;
        totalAmount = baseAmount;
      }
      
      // Final validation
      if (isNaN(baseAmount) || baseAmount <= 0 || isNaN(totalAmount) || totalAmount <= 0) {
        throw new Error('מחיר כרטיס לא תקין');
      }
      
      // CRITICAL: Store the actual paid amounts for the success screen (Phase 2: integers for negotiated)
      setPaidAmounts({
        baseAmount: Number.isInteger(baseAmount) ? String(baseAmount) : baseAmount.toFixed(2),
        serviceFee: Number.isInteger(serviceFee) ? String(serviceFee) : serviceFee.toFixed(2),
        totalAmount: Number.isInteger(totalAmount) ? String(totalAmount) : totalAmount.toFixed(2)
      });
      
      // CRITICAL DEBUG: Trace all values before payment
      console.log('=== PAYMENT FLOW DEBUG ===');
      console.log('basePriceStr (raw):', basePriceStr, 'unitDisplayPrice:', unitDisplayPrice);
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
      
      // Payload: use exact finalized total (matches UI display). Phase 2: negotiated = Math.ceil(base*1.10)
      let finalTotal = totalAmount;
      if (isNegotiatedPrice && acceptedOffer?.amount != null) {
        const exactBase = parseFloat(acceptedOffer.amount);
        finalTotal = Math.ceil(exactBase * 1.10); // Always whole number, no .90 or .99
        console.log('Negotiated: exactBase=', exactBase, 'finalTotal=', finalTotal);
      } else {
        // Standard tickets: finalTotal = unitDisplayPrice * quantity (Math.ceil(base*1.10) * qty)
        finalTotal = unitDisplayPrice * quantity;
        console.log('Standard: unitDisplayPrice=', unitDisplayPrice, 'quantity=', quantity, 'finalTotal=', finalTotal);
      }
      
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
      
      const paymentResponse = await paymentAPI.simulatePayment(paymentData);

      console.log('Payment response:', paymentResponse);

      if (!paymentResponse.data || !paymentResponse.data.success) {
        throw new Error(paymentResponse.data?.message || 'סימולציית התשלום נכשלה');
      }

      // Step 2: Create order - ensure total_amount is a Number
      console.log('Creating order...');
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
        
        orderResponse = await orderAPI.guestCheckout(orderData);
      }

      console.log('Order response:', orderResponse);

      if (!orderResponse.data || !orderResponse.data.id) {
        throw new Error('יצירת ההזמנה נכשלה');
      }

      // CRITICAL: Set order data BEFORE transitioning to success to prevent empty success screen / layout jump
      setOrderId(orderResponse.data.id);
      setOrderData(orderResponse.data);

      // Clear reservation flag since purchase is complete
      reservationRef.current = false;

      // Step 3: Get PDF download URL (optional - download buttons work via API)
      try {
        const email = user ? null : guestForm.email.trim();
        const pdfResponse = await ticketAPI.downloadPDF(ticket.id, email);

        // Create blob URL for download
        const blob = new Blob([pdfResponse.data], { type: 'application/pdf' });
        const url = window.URL.createObjectURL(blob);
        setPdfUrl(url);
      } catch (pdfError) {
        console.error('Error fetching PDF:', pdfError);
        // PDF download will be available via the download button
      }

      // Transition to success ONLY after orderData is set (React batches these; success screen will have data)
      setStep('success');
    } catch (err) {
      console.error('Payment error:', err);
      const message = err.response?.data?.detail ||
                     err.response?.data?.error ||
                     (typeof err.response?.data === 'string' ? err.response.data : JSON.stringify(err.response?.data)) ||
                     err.message ||
                     'שגיאה בתקשורת עם השרת';
      setError(message);
      // Enterprise UX: Show Toast for "ticket was just sold" - beautiful feedback instead of raw alert
      const isSoldError = /sold|נמכר|just sold/i.test(message);
      if (isSoldError && onErrorToParent) {
        onErrorToParent({ message: 'הכרטיס נמכר ברגע זה. ריעננו את הרשימה – נסה כרטיס אחר.', type: 'error' });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPDF = async (ticketId, index = null) => {
    if (!ticketId) {
      console.error('handleDownloadPDF: No ticket ID provided');
      setError('שגיאה: מזהה כרטיס חסר');
      return;
    }
    console.log('Downloading ticket ID:', ticketId);
    try {
      const email = user ? null : (guestForm?.email?.trim() || null);
      const response = await ticketAPI.downloadPDF(ticketId, email);
      
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = index != null ? `ticket-${index + 1}.pdf` : `ticket-${ticketId}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('PDF download failed:', err?.response?.status, err?.response?.data, err);
      setError('הורדת ה-PDF נכשלה. אנא נסה שוב מאוחר יותר.');
    }
  };

  // Reserve ticket when modal opens (only once)
  useEffect(() => {
    // Phase 1: Once order is complete, ignore ticket validation - prevents "Ticket unavailable" from ruining success screen
    if (step === 'success') return;
    const reserveTicket = async () => {
      if (reservationRef.current || !ticket) return;
      
      try {
        // Ensure we have a valid ticket ID
        const ticketId = ticket.id;
        if (!ticketId) {
          setError('שגיאה: לא נמצא מזהה כרטיס תקין');
          return;
        }
        
        // Check if ticket is available (status should be 'active')
        if (ticket.status && ticket.status !== 'active') {
          setError('הכרטיס אינו זמין כרגע. אנא נסה כרטיס אחר.');
          setTimeout(() => {
            handleClose();
          }, 3000);
          return;
        }
        
        const email = user ? null : guestForm.email || null;
        const listingGroupId = ticketGroup?.listing_group_id || ticket?.listing_group_id;
        console.log('Reserving Ticket ID:', ticketId);
        console.log('Listing Group ID:', listingGroupId);
        console.log('Ticket Group:', ticketGroup);
        console.log('Ticket:', ticket);
        const response = await ticketAPI.reserveTicket(ticketId, email);
        
        if (response.data && response.data.success) {
          reservationRef.current = true;
          // Calculate remaining time from reservation
          if (response.data.expires_at) {
            const expiresAt = new Date(response.data.expires_at);
            const now = new Date();
            const remaining = Math.max(0, Math.floor((expiresAt - now) / 1000));
            setTimeRemaining(remaining);
          } else {
            setTimeRemaining(600); // Default 10 minutes
          }
          console.log('Ticket reserved successfully');
        }
      } catch (err) {
        console.error('Error reserving ticket:', err);
        console.error('Error response:', err.response?.data);
        
        // Check if ticket is reserved by someone else
        if (err.response?.data?.status === 'reserved' || err.response?.data?.error?.includes('someone else')) {
          const errorMsg = err.response?.data?.error || 'הכרטיס נמצא כעת בעגלה של מישהו אחר. הוא עשוי להיות זמין שוב בעוד כמה דקות.';
          setError(errorMsg);
          // Close modal after showing error
          setTimeout(() => {
            handleClose();
          }, 5000);
        } else if (err.response?.data?.error?.includes('no longer available') || err.response?.data?.error?.includes('not available')) {
          const errorMsg = err.response?.data?.error || 'הכרטיס אינו זמין עוד. אנא נסה כרטיס אחר.';
          setError(errorMsg);
          setTimeout(() => {
            handleClose();
          }, 3000);
        } else {
          // If reservation fails for other reasons, still allow checkout but show warning
          const errorMsg = err.response?.data?.error || err.response?.data?.detail || 'לא ניתן לשמור את הכרטיס כרגע. אנא נסה שוב.';
          setError(errorMsg);
        }
      }
    };

    // Reserve ticket immediately when modal opens
    reserveTicket();

    return () => {
      // Release reservation if modal closes without completing purchase
      if (reservationRef.current && step !== 'success' && ticket) {
        const releaseReservation = async () => {
          try {
            const email = user ? null : guestForm.email || null;
            await ticketAPI.releaseReservation(ticket.id, email);
            console.log('Reservation released on modal close');
          } catch (err) {
            console.error('Error releasing reservation:', err);
          }
        };
        releaseReservation();
      }
    };
  }, [ticket, step]); // Re-run if ticket changes; step guard prevents post-purchase validation

  // Reset and start timer when entering payment step
  useEffect(() => {
    if (step === 'payment') {
      // Start the countdown timer
      timerRef.current = setInterval(() => {
        setTimeRemaining((prev) => {
          if (prev <= 1) {
            clearInterval(timerRef.current);
            // Release reservation when timer expires - explicit API call
            const releaseReservation = async () => {
              try {
                const email = user ? null : guestForm.email || null;
                await ticketAPI.releaseReservation(ticket?.id, email);
                reservationRef.current = false;
              } catch (err) {
                console.error('Error releasing reservation:', err);
              }
            };
            releaseReservation();
            setError('פג הזמן. הכרטיסים שוחררו חזרה למלאי. אנא נסה שוב.');
            setStep('info'); // Close payment step, back to info
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      // Clear timer when not in payment step
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [step, ticket, user, guestForm.email]);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const progressPercentage = ((600 - timeRemaining) / 600) * 100;

  const handleClose = async () => {
    if (pdfUrl) {
      window.URL.revokeObjectURL(pdfUrl);
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    
    // Release reservation if not completed
    if (reservationRef.current && step !== 'success') {
      try {
        const email = user ? null : guestForm.email || null;
        await ticketAPI.releaseReservation(ticket.id, email);
        reservationRef.current = false;
      } catch (err) {
        console.error('Error releasing reservation:', err);
      }
    }
    
    onClose();
  };

  // Success screen - Full-screen celebration (guard: prevent empty screen / layout jump)
  if (step === 'success') {
    if (!orderId && !orderData) {
      return (
        <div className="modal-overlay" onClick={handleClose}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ minHeight: '400px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <p>טוען...</p>
          </div>
        </div>
      );
    }
    return (
      <div className="success-overlay" onClick={handleClose}>
        <div className="success-celebration" onClick={(e) => e.stopPropagation()}>
          <div className="success-celebration-content">
            <div className="success-checkmark-large">
              <svg viewBox="0 0 100 100" className="checkmark-svg">
                <circle cx="50" cy="50" r="45" className="checkmark-circle" />
                <path d="M30 50 L45 65 L70 35" className="checkmark-path" />
              </svg>
            </div>
            <h1 className="success-title-large">Order Confirmed</h1>
            <h2 className="success-subtitle">הזמנה אושרה בהצלחה!</h2>
            <p className="success-order-number">מספר הזמנה: #{orderId}</p>
            
            <div className="success-ticket-summary">
              <h3>{ticket?.event_name || 'אירוע'}</h3>
              <div className="success-ticket-details">
                <p><strong>מיקום:</strong> {ticket?.venue || 'לא צוין'}</p>
                {isNegotiatedPrice && (
                  <p><strong>מחיר מוסכם:</strong> <span style={{color: '#10b981', fontSize: '0.9em'}}>₪{paidAmounts?.baseAmount || effectivePrice}</span></p>
                )}
                {quantity > 1 && (
                  <p><strong>כמות:</strong> {quantity}</p>
                )}
                {paidAmounts ? (
                  <>
                    <p><strong>מחיר כרטיסים:</strong> ₪{paidAmounts.baseAmount}</p>
                    <p><strong>עמלת שירות (10%):</strong> ₪{paidAmounts.serviceFee}</p>
                    <p><strong>סה"כ שולם:</strong> ₪{paidAmounts.totalAmount}</p>
                  </>
                ) : (
                  <>
                    <p><strong>מחיר כרטיסים:</strong> ₪{Math.floor((unitDisplayPrice * quantity) / 1.10)}</p>
                    <p><strong>עמלת שירות (10%):</strong> ₪{(unitDisplayPrice * quantity) - Math.floor((unitDisplayPrice * quantity) / 1.10)}</p>
                    <p><strong>סה"כ שולם:</strong> ₪{unitDisplayPrice * quantity}</p>
                  </>
                )}
              </div>
            </div>
            
            <div className="success-actions">
              <div className="success-download-buttons">
                {(() => {
                  const ticketIds = orderData?.tickets?.length > 0
                    ? orderData.tickets.map((t) => t.id)
                    : (orderData?.ticket_ids?.length > 0 ? orderData.ticket_ids : (ticket?.id ? [ticket.id] : []));
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
                        onClick={() => handleDownloadPDF(tid, idx)}
                        className="success-download-button"
                      >
                        <CheckIcon />
                        <DownloadIcon />
                        {ticketIds.length > 1 ? `הורד כרטיס ${idx + 1}` : 'הורדת כרטיס PDF'}
                      </button>
                    ));
                  }
                  if (ticketIds.length === 1) {
                    return (
                      <button
                        onClick={() => handleDownloadPDF(ticketIds[0])}
                        className="success-download-button"
                      >
                        <CheckIcon />
                        <DownloadIcon />
                        הורדת כרטיס PDF
                      </button>
                    );
                  }
                  return (
                    <button
                      onClick={() => handleDownloadPDF(ticket?.id)}
                      className="success-download-button"
                      disabled={!ticket?.id}
                    >
                      <CheckIcon />
                      <DownloadIcon />
                      הורדת כרטיס PDF
                    </button>
                  );
                })()}
              </div>
              <button onClick={handleClose} className="success-close-button">
                סגור
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Payment screen
  if (step === 'payment') {
    return (
      <div className="modal-overlay" onClick={handleClose}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <button className="close-button" onClick={handleClose}>×</button>
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
              <span>הכרטיסים שמורים לך למשך:</span>
              <span className={`timer-countdown ${timeRemaining < 60 ? 'timer-warning' : ''} ${timeRemaining === 0 ? 'timer-expired' : ''}`}>
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
            {ticket.pdf_file_url && (
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
                  ✓ מחיר מוסכם: ₪{offerBaseAmountStr ?? effectivePrice} סה"כ ל-{quantity} כרטיסים (במקום ₪{getTicketPrice(ticket)} ליחידה)
                </div>
              )}
              {isNegotiatedPrice ? (
                <>
                  <div className="price-row">
                    <span>מחיר ליחידה:</span>
                    <span>₪{negotiatedUnitBase != null ? negotiatedUnitBase.toFixed(2) : unitPriceForDisplay}</span>
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
                    <span>מחיר כרטיסים:</span>
                    <span>₪{offerBaseAmountStr != null ? parseFloat(offerBaseAmountStr).toFixed(2) : parseFloat(effectivePrice).toFixed(2)}</span>
                  </div>
                  <div className="price-row">
                    <span>עמלת שירות (10%):</span>
                    <span>₪{calculateServiceFee(offerBaseAmountStr ?? effectivePrice, 10)}</span>
                  </div>
                  <div className="price-row total-row">
                    <span>סה"כ לתשלום:</span>
                    <span>₪{(parseFloat(offerBaseAmountStr ?? effectivePrice) + parseFloat(calculateServiceFee(offerBaseAmountStr ?? effectivePrice, 10))).toFixed(2)}</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="price-row">
                    <span>מחיר ליחידה (כולל עמלה):</span>
                    <span>₪{unitDisplayPrice}</span>
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
                  <div className="price-row total-row">
                    <span>סה"כ לתשלום:</span>
                    <span>₪{unitDisplayPrice * quantity}</span>
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
            
            <div className="button-group checkout-buttons-row">
              <button
                type="button"
                onClick={() => setStep('info')}
                className="back-button checkout-row-btn"
                disabled={loading || timeRemaining === 0}
              >
                חזרה
              </button>
              <button
                type="submit"
                disabled={loading || timeRemaining === 0}
                className="checkout-button checkout-row-btn"
              >
                {loading ? 'מעבד תשלום...' : timeRemaining === 0 ? 'זמן פג' : 'השלמת תשלום'}
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
  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="close-button" onClick={handleClose}>×</button>
        <div className="secure-checkout-header">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M10 1L3 4V9C3 13.55 6.16 17.74 10 19C13.84 17.74 17 13.55 17 9V4L10 1Z" fill="currentColor"/>
            <path d="M8 9L9 10L12 7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <h2>תשלום מאובטח</h2>
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
                  ✓ מחיר מוסכם: ₪{effectivePrice} סה"כ ל-{quantity} כרטיסים (במקום ₪{getTicketPrice(ticket)} ליחידה)
                </div>
              )}
              {isNegotiatedPrice ? (
                <>
                  <div className="price-row">
                    <span>מחיר ליחידה:</span>
                    <span>₪{negotiatedUnitBase != null ? negotiatedUnitBase.toFixed(2) : unitPriceForDisplay}</span>
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
                    <span>מחיר כרטיסים:</span>
                    <span>₪{offerBaseAmountStr != null ? parseFloat(offerBaseAmountStr).toFixed(2) : parseFloat(effectivePrice).toFixed(2)}</span>
                  </div>
                  <div className="price-row">
                    <span>עמלת שירות (10%):</span>
                    <span>₪{calculateServiceFee(effectivePrice, 10)}</span>
                  </div>
                  <div className="price-row total-row">
                    <span>סה"כ לתשלום:</span>
                    <span>₪{(parseFloat(effectivePrice) + parseFloat(calculateServiceFee(effectivePrice, 10))).toFixed(2)}</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="price-row">
                    <span>מחיר ליחידה:</span>
                    <span>₪{unitDisplayPrice}</span>
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
                    <span>מחיר כרטיסים:</span>
                    <span>₪{(unitDisplayPrice * quantity)}</span>
                  </div>
                  <div className="price-row total-row">
                    <span>סה"כ לתשלום:</span>
                    <span>₪{unitDisplayPrice * quantity}</span>
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
              onClick={handleInfoSubmit}
              disabled={loading}
              className="checkout-button"
            >
              המשך לתשלום
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
                disabled={loading}
                className="checkout-button"
              >
                המשך לתשלום
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};

export default CheckoutModal;
