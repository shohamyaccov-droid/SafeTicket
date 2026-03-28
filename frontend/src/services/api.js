import axios from 'axios';

axios.defaults.withCredentials = true;
axios.defaults.xsrfCookieName = 'csrftoken';
axios.defaults.xsrfHeaderName = 'X-CSRFToken';

/** In-memory CSRF for cross-origin: csrftoken cookie is not visible on document.cookie for the API host. */
let csrfTokenFromApi = null;

/** Production API when VITE_API_URL is missing at build time (never fall back to localhost in prod). */
const PRODUCTION_API_BASE_URL = 'https://safeticket-api.onrender.com/api';

/** Ensure base URL ends with /api (Render often sets host only, which would 404 and look like CORS). */
function normalizeApiBase(url) {
  const raw = url == null ? '' : String(url).trim();
  if (raw === '' || raw === 'undefined' || raw === 'null') {
    if (import.meta.env.PROD) {
      return PRODUCTION_API_BASE_URL;
    }
    return 'http://localhost:8000/api';
  }
  let base = raw.replace(/\/+$/, '');
  if (!base.endsWith('/api')) {
    base = `${base}/api`;
  }
  return base;
}

const API_URL = normalizeApiBase(import.meta.env.VITE_API_URL);

/** CSRF for X-CSRFToken: prefer JSON warmup cache (cross-origin); else cookie (same-site dev). */
function getCsrfTokenForRequest() {
  if (csrfTokenFromApi != null && csrfTokenFromApi !== '') {
    return csrfTokenFromApi;
  }
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1].trim());
  } catch {
    return match[1].trim();
  }
}

const api = axios.create({
  baseURL: API_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Attach X-CSRFToken for unsafe methods (POST, PUT, PATCH, DELETE)
api.interceptors.request.use(
  (config) => {
    const method = (config.method || 'get').toLowerCase();
    if (method !== 'get' && method !== 'head' && method !== 'options') {
      const token = getCsrfTokenForRequest();
      if (token) {
        config.headers['X-CSRFToken'] = token;
      }
    }
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Handle 401: auto-refresh via HttpOnly cookie, then retry; else redirect to login
// IMPORTANT: Do NOT redirect when the failed request is getProfile - that's the initial
// auth check. Let it reject so AuthContext can set user=null (avoids infinite redirect loop).
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const is401 = error.response?.status === 401;
    const noRetryYet = !originalRequest._retry;
    const isAuthEndpoint = originalRequest.url?.includes('/login/') ||
      originalRequest.url?.includes('/register/') ||
      originalRequest.url?.includes('/token/refresh/') ||
      originalRequest.url?.includes('/logout/');
    const isGetProfile = originalRequest.url?.includes('/profile/');

    if (is401 && noRetryYet && !isAuthEndpoint) {
      originalRequest._retry = true;
      try {
        // Refresh uses HttpOnly cookie (withCredentials) - no localStorage
        await api.post('/users/token/refresh/');
        // Retry original request - browser now has new access_token cookie
        return api(originalRequest);
      } catch (refreshError) {
        // getProfile 401 = not logged in; let AuthContext handle it (set user null)
        if (isGetProfile) {
          return Promise.reject(error);
        }
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

const creds = { withCredentials: true };

export const authAPI = {
  register: (data) => api.post('/users/register/', data, creds),
  login: (data) => api.post('/users/login/', data, creds),
  logout: () => api.post('/users/logout/', {}, creds),
  getProfile: () => api.get('/users/profile/', creds),
  getDashboard: () => api.get('/users/dashboard/', creds),
  getCsrf: async () => {
    const response = await api.get('/users/csrf/', creds);
    const t = response.data?.csrfToken;
    if (t != null && t !== '') {
      csrfTokenFromApi = String(t);
    }
    return response;
  },
};

export const paymentAPI = {
  simulatePayment: (data) => api.post('/users/payments/simulate/', data),
};

export const orderAPI = {
  createOrder: (data) => api.post('/users/orders/', data),
  guestCheckout: (data) => api.post('/users/orders/guest/', data),
  getReceipt: (orderId) => api.get(`/users/orders/${orderId}/receipt/`),
};

export const ticketAPI = {
  getTickets: (config = {}) => api.get('/users/tickets/', config),
  getTicket: (id) => api.get(`/users/tickets/${id}/`),
  getTicketDetails: (id) => api.get(`/users/tickets/${id}/details/`),
  createTicket: (data) => api.post('/users/tickets/', data),
  updateTicket: (id, data) => api.put(`/users/tickets/${id}/`, data),
  updateTicketPrice: (id, price) => api.patch(`/users/tickets/${id}/update-price/`, { original_price: price }),
  deleteTicket: (id) => api.delete(`/users/tickets/${id}/`),
  downloadPDF: (id, email = null) => {
    const config = {
      responseType: 'blob',
    };
    if (email) {
      config.params = { email };
    }
    return api.get(`/users/tickets/${id}/download_pdf/`, config);
  },
  reserveTicket: (id, email = null) => {
    const data = email ? { email } : {};
    return api.post(`/users/tickets/${id}/reserve/`, data);
  },
  releaseReservation: (id, email = null) => {
    const data = email ? { email } : {};
    return api.post(`/users/tickets/${id}/release_reservation/`, data);
  },
};

export const eventAPI = {
  /** Pass axios config (params, signal, timeout, etc.) */
  getEvents: (config = {}) => api.get('/users/events/', config),
  getEvent: (id) => api.get(`/users/events/${id}/`),
  getEventTickets: (id, params = {}) => api.get(`/users/events/${id}/tickets/`, { params }),
  createEvent: (data) => api.post('/users/events/', data),
  updateEvent: (id, data) => api.put(`/users/events/${id}/`, data),
  deleteEvent: (id) => api.delete(`/users/events/${id}/`),
};

export const artistAPI = {
  getArtists: (config = {}) => api.get('/users/artists/', config),
  getArtist: (id, config = {}) => api.get(`/users/artists/${id}/`, config),
  getArtistEvents: (id, config = {}) => api.get(`/users/artists/${id}/events/`, config),
  createArtist: (data) => api.post('/users/artists/', data),
  updateArtist: (id, data) => api.put(`/users/artists/${id}/`, data),
  deleteArtist: (id) => api.delete(`/users/artists/${id}/`),
};

export const alertAPI = {
  createAlert: (data) => api.post('/users/alerts/', data),
};

export const offerAPI = {
  createOffer: (data) => api.post('/users/offers/', data),
  getOffers: () => api.get('/users/offers/'),
  getReceivedOffers: () => api.get('/users/offers/received/'),
  getSentOffers: () => api.get('/users/offers/sent/'),
  acceptOffer: (offerId) => api.post(`/users/offers/${offerId}/accept/`),
  rejectOffer: (offerId) => api.post(`/users/offers/${offerId}/reject/`),
  counterOffer: (offerId, data) => api.post(`/users/offers/${offerId}/counter/`, data),
  getOffer: (offerId) => api.get(`/users/offers/${offerId}/`),
};

export const adminAPI = {
  getPendingTickets: () => api.get('/users/admin/pending-tickets/'),
  approveTicket: (ticketId) => api.post(`/users/admin/tickets/${ticketId}/approve/`),
  rejectTicket: (ticketId) => api.post(`/users/admin/tickets/${ticketId}/reject/`),
};

export const contactAPI = {
  createContactMessage: (data) => api.post('/users/contact-messages/', data),
};

export const eventRequestAPI = {
  create: (data) => api.post('/users/event-requests/', data),
};

export default api;

