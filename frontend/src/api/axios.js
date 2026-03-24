/**
 * Re-exports the configured Axios instance (see services/api.js for defaults + interceptors).
 */
export {
  default,
  authAPI,
  paymentAPI,
  orderAPI,
  ticketAPI,
  eventAPI,
  artistAPI,
  alertAPI,
  offerAPI,
  adminAPI,
  contactAPI,
} from '../services/api.js';
