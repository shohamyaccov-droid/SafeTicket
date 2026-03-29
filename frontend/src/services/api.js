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

function stripContentTypeForMultipart(config) {
  if (!(config.data instanceof FormData)) {
    return;
  }
  const h = config.headers;
  if (!h) {
    return;
  }
  // Axios 1.x often uses AxiosHeaders; default instance also merges post/common Content-Type: application/json.
  if (typeof h.delete === 'function') {
    h.delete('Content-Type');
    h.delete('content-type');
  } else {
    delete h['Content-Type'];
    delete h['content-type'];
  }
  if (h.common) {
    delete h.common['Content-Type'];
  }
  if (h.post) {
    delete h.post['Content-Type'];
  }
}

// Attach X-CSRFToken for unsafe methods (POST, PUT, PATCH, DELETE).
// FormData: strip every Content-Type variant first, then set CSRF (multipart boundary must not be forced).
api.interceptors.request.use(
  (config) => {
    const method = (config.method || 'get').toLowerCase();
    stripContentTypeForMultipart(config);
    if (method !== 'get' && method !== 'head' && method !== 'options') {
      const token = getCsrfTokenForRequest();
      if (token) {
        config.headers['X-CSRFToken'] = token;
      }
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

/** Warm CSRF cache before multipart uploads (cross-origin: cookie not readable for API host). */
export async function ensureCsrfToken() {
  try {
    await authAPI.getCsrf();
  } catch {
    // Same-site dev may still work via csrftoken cookie in interceptor
  }
}

export const paymentAPI = {
  simulatePayment: (data) => api.post('/users/payments/simulate/', data),
};

export const orderAPI = {
  createOrder: (data) => api.post('/users/orders/', data),
  guestCheckout: (data) => api.post('/users/orders/guest/', data),
  confirmPayment: (orderId, data) => api.post(`/users/orders/${orderId}/confirm-payment/`, data),
  getReceipt: (orderId) => api.get(`/users/orders/${orderId}/receipt/`),
};

/**
 * Ticket upload MUST use browser multipart (boundary set by the browser).
 * Axios can still merge Content-Type: application/json from defaults in some builds/adapters,
 * which makes Django parse JSON and leaves request.FILES empty → ghost rows / storage.exists fails.
 * Native fetch never sets Content-Type on FormData — same as MDN/CORS recommended pattern.
 */
async function postTicketMultipart(formData) {
  await ensureCsrfToken();
  const base = API_URL.replace(/\/+$/, '');
  const ticketUrl = `${base}/users/tickets/`;
  const refreshUrl = `${base}/users/token/refresh/`;

  const postOnce = () => {
    const token = getCsrfTokenForRequest();
    const headers = {};
    if (token) {
      headers['X-CSRFToken'] = token;
    }
    return fetch(ticketUrl, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: formData,
    });
  };

  let res = await postOnce();
  if (res.status === 401) {
    try {
      await ensureCsrfToken();
      const tok = getCsrfTokenForRequest();
      await fetch(refreshUrl, {
        method: 'POST',
        credentials: 'include',
        headers: {
          ...(tok ? { 'X-CSRFToken': tok } : {}),
          'Content-Type': 'application/json',
        },
        body: '{}',
      });
    } catch {
      /* retry below may still 401 */
    }
    res = await postOnce();
  }

  const text = await res.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!res.ok) {
    const body = data && typeof data === 'object' ? data : {};
    const rawMsg = body.error || body.detail;
    const msg =
      typeof rawMsg === 'string'
        ? rawMsg
        : rawMsg != null
          ? JSON.stringify(rawMsg)
          : `Request failed: ${res.status}`;
    const err = new Error(msg);
    err.response = { status: res.status, data: body };
    throw err;
  }
  return { data, status: res.status, statusText: res.statusText };
}

export const ticketAPI = {
  getTickets: (config = {}) => api.get('/users/tickets/', config),
  getTicket: (id) => api.get(`/users/tickets/${id}/`),
  getTicketDetails: (id) => api.get(`/users/tickets/${id}/details/`),
  /** FormData: native fetch (reliable multipart). Otherwise Axios. */
  createTicket: (data) =>
    typeof FormData !== 'undefined' && data instanceof FormData
      ? postTicketMultipart(data)
      : api.post('/users/tickets/', data, {
          ...creds,
          timeout: 120000,
          maxBodyLength: Infinity,
          maxContentLength: Infinity,
        }),
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

