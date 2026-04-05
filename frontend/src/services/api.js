import axios from 'axios';

axios.defaults.withCredentials = true;
axios.defaults.xsrfCookieName = 'csrftoken';
axios.defaults.xsrfHeaderName = 'X-CSRFToken';

/** In-memory CSRF for cross-origin: csrftoken cookie is not visible on document.cookie for the API host. */
let csrfTokenFromApi = null;

/** Clear cached CSRF (e.g. stale token on mobile / after 403). */
export function resetCsrfTokenCache() {
  csrfTokenFromApi = null;
}

/**
 * Mobile-first JWT: Authorization Bearer is the primary auth for cross-origin API calls.
 * Access + refresh are persisted in localStorage so iOS Safari survives reloads without cookies.
 */
let bearerAccessToken = null;
let bearerRefreshToken = null;
const LEGACY_ACCESS_KEY = 'safeticket_jwt_access';
const LEGACY_REFRESH_KEY = 'safeticket_jwt_refresh';
/** TradeTix branding — migrated once from safeticket_* keys so users stay logged in. */
const BEARER_ACCESS_KEY = 'tradetix_jwt_access';
const BEARER_REFRESH_KEY = 'tradetix_jwt_refresh';

function _readLs(key) {
  try {
    const v = localStorage.getItem(key);
    return v && v !== '' ? v : null;
  } catch {
    return null;
  }
}

function _writeLs(key, val) {
  try {
    if (val == null || val === '') {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, String(val));
    }
  } catch {
    /* ignore quota / private mode */
  }
}

/**
 * Bearer for API calls: localStorage is source of truth (iOS Safari reload / multi-tab).
 * Memory is synced from LS when present so other code sees the same value.
 */
export function getEffectiveBearerAccess() {
  try {
    const fromLs = localStorage.getItem(BEARER_ACCESS_KEY);
    if (fromLs && fromLs !== '') {
      bearerAccessToken = fromLs;
      return fromLs;
    }
  } catch {
    /* private mode / denied */
  }
  return bearerAccessToken;
}

function hydrateRefreshFromStorage() {
  if (bearerRefreshToken) return;
  let s = _readLs(BEARER_REFRESH_KEY);
  if (!s) {
    try {
      const legacy =
        sessionStorage.getItem('tradetix_bearer_refresh') ||
        sessionStorage.getItem('safeticket_bearer_refresh');
      if (legacy) {
        _writeLs(BEARER_REFRESH_KEY, legacy);
        sessionStorage.removeItem('tradetix_bearer_refresh');
        sessionStorage.removeItem('safeticket_bearer_refresh');
        s = legacy;
      }
    } catch {
      /* ignore */
    }
  }
  if (s) bearerRefreshToken = s;
}

hydrateRefreshFromStorage();
const _storedAccess = _readLs(BEARER_ACCESS_KEY);
if (_storedAccess) {
  bearerAccessToken = _storedAccess;
}

function getRefreshForBearerFallback() {
  if (bearerRefreshToken) return bearerRefreshToken;
  hydrateRefreshFromStorage();
  return bearerRefreshToken;
}

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

/**
 * CRITICAL (iOS Safari): set axios default Authorization synchronously so the very next
 * request (e.g. getProfile right after login) cannot outrun the interceptor.
 */
export function syncAxiosDefaultAuthHeader() {
  const t = getEffectiveBearerAccess();
  if (t) {
    api.defaults.headers.common.Authorization = `Bearer ${t}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

export function setBearerFallback(access, refresh) {
  bearerAccessToken = access != null && access !== '' ? String(access) : null;
  _writeLs(BEARER_ACCESS_KEY, bearerAccessToken);
  if (refresh != null && refresh !== '') {
    bearerRefreshToken = String(refresh);
    _writeLs(BEARER_REFRESH_KEY, bearerRefreshToken);
  }
  syncAxiosDefaultAuthHeader();
}

export function clearBearerFallback() {
  bearerAccessToken = null;
  bearerRefreshToken = null;
  _writeLs(BEARER_ACCESS_KEY, null);
  _writeLs(BEARER_REFRESH_KEY, null);
  syncAxiosDefaultAuthHeader();
}

if (_storedAccess) {
  syncAxiosDefaultAuthHeader();
}

function bodyTextLooksLikeCsrfFailure(data) {
  if (data == null) return false;
  if (typeof data === 'string') {
    return /csrf/i.test(data) || /CSRF verification failed/i.test(data);
  }
  if (typeof data === 'object') {
    const msg = data.detail || data.message || data.error;
    if (typeof msg === 'string' && /csrf/i.test(msg)) return true;
    try {
      return /csrf/i.test(JSON.stringify(data));
    } catch {
      return false;
    }
  }
  return false;
}

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
// Cross-origin SPA: cookie is often unreadable — refresh token via /users/csrf/ before mutating if missing.
// FormData: strip every Content-Type variant first, then set CSRF (multipart boundary must not be forced).
api.interceptors.request.use(
  async (config) => {
    const method = (config.method || 'get').toLowerCase();
    stripContentTypeForMultipart(config);
    const bearer = getEffectiveBearerAccess();
    if (bearer) {
      config.headers.Authorization = `Bearer ${bearer}`;
    }
    if (method !== 'get' && method !== 'head' && method !== 'options') {
      let token = getCsrfTokenForRequest();
      if (!token) {
        try {
          await ensureCsrfToken();
        } catch {
          /* dev same-site may rely on csrftoken cookie only */
        }
        token = getCsrfTokenForRequest();
      }
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
  (response) => {
    const url = response.config?.url || '';
    const st = response.status;
    if ((st === 200 || st === 201) && response.data && typeof response.data === 'object') {
      const d = response.data;
      if (
        url.includes('/login/') ||
        url.includes('/register/') ||
        url.includes('/token/refresh/')
      ) {
        if (d.access) {
          setBearerFallback(d.access, d.refresh);
        }
      }
    }
    return response;
  },
  async (error) => {
    const originalRequest = error.config;
    if (!originalRequest) {
      return Promise.reject(error);
    }
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
        const rTok = getRefreshForBearerFallback();
        const refreshRes = await api.post(
          '/users/token/refresh/',
          rTok ? { refresh: rTok } : {},
        );
        if (refreshRes.data?.access) {
          setBearerFallback(
            refreshRes.data.access,
            refreshRes.data.refresh || rTok || undefined,
          );
        }
        return api(originalRequest);
      } catch (refreshError) {
        // getProfile 401 = not logged in; let AuthContext handle it (set user null)
        if (isGetProfile) {
          return Promise.reject(error);
        }
        clearBearerFallback();
        window.location.href = '/login';
      }
    }

    const is403 = error.response?.status === 403;
    const urlPath = originalRequest?.url || '';
    const canCsrfRetry =
      is403 &&
      !originalRequest._csrfRetry &&
      !urlPath.includes('/users/csrf/');
    if (canCsrfRetry && bodyTextLooksLikeCsrfFailure(error.response?.data)) {
      originalRequest._csrfRetry = true;
      resetCsrfTokenCache();
      try {
        await ensureCsrfToken();
      } catch {
        /* ignore */
      }
      const token = getCsrfTokenForRequest();
      if (token) {
        const h = originalRequest.headers;
        if (h && typeof h.set === 'function') {
          h.set('X-CSRFToken', token);
        } else if (h) {
          h['X-CSRFToken'] = token;
        }
      }
      return api(originalRequest);
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
  upgradeToSeller: (data) => api.post('/users/me/upgrade-to-seller/', data, creds),
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
    // Retry once (transient network / cold start on Render)
    try {
      await authAPI.getCsrf();
    } catch {
      /* same-site dev may still work via csrftoken cookie on document */
    }
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
  if (!getCsrfTokenForRequest()) {
    resetCsrfTokenCache();
    await authAPI.getCsrf();
  }
  const base = API_URL.replace(/\/+$/, '');
  const ticketUrl = `${base}/users/tickets/`;
  const refreshUrl = `${base}/users/token/refresh/`;

  const postOnce = () => {
    const token = getCsrfTokenForRequest();
    const headers = {};
    if (token) {
      headers['X-CSRFToken'] = token;
    }
    const bearer = getEffectiveBearerAccess();
    if (bearer) {
      headers.Authorization = `Bearer ${bearer}`;
    }
    console.log('[TradeTix] POST /users/tickets/ FormData (multipart) before fetch:');
    for (const [key, val] of formData.entries()) {
      if (typeof File !== 'undefined' && val instanceof File) {
        console.log(
          `  ${key}:`,
          'File',
          val.name,
          `size=${val.size}`,
          `type=${val.type || '(empty)'}`,
          val.size === 0 ? '(EMPTY FILE)' : ''
        );
      } else if (typeof Blob !== 'undefined' && val instanceof Blob && !(val instanceof File)) {
        console.log(`  ${key}:`, 'Blob', `size=${val.size}`, `type=${val.type || '(empty)'}`);
      } else {
        console.log(`  ${key}:`, val);
      }
    }
    return fetch(ticketUrl, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: formData,
    });
  };

  let res = await postOnce();
  if (res.status === 403) {
    const t403 = await res.clone().text();
    const looksCsrf =
      /csrf/i.test(t403) ||
      /CSRF verification failed/i.test(t403) ||
      (() => {
        try {
          const j = JSON.parse(t403);
          const d = j && (j.detail || j.message || j.error);
          return typeof d === 'string' && /csrf/i.test(d);
        } catch {
          return false;
        }
      })();
    if (looksCsrf) {
      resetCsrfTokenCache();
      try {
        await authAPI.getCsrf();
      } catch {
        await ensureCsrfToken();
      }
      res = await postOnce();
    }
  }
  if (res.status === 401) {
    try {
      await ensureCsrfToken();
      const tok = getCsrfTokenForRequest();
      const rTok = getRefreshForBearerFallback();
      const refreshRes = await fetch(refreshUrl, {
        method: 'POST',
        credentials: 'include',
        headers: {
          ...(tok ? { 'X-CSRFToken': tok } : {}),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(rTok ? { refresh: rTok } : {}),
      });
      const rtxt = await refreshRes.text();
      if (refreshRes.ok && rtxt) {
        try {
          const rd = JSON.parse(rtxt);
          if (rd.access) {
            setBearerFallback(rd.access, rd.refresh || rTok || undefined);
          }
        } catch {
          /* ignore */
        }
      }
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
  /** Proof of purchase — staff/seller only (same auth as backend download_receipt). */
  downloadReceipt: (id) =>
    api.get(`/users/tickets/${id}/download_receipt/`, { responseType: 'blob' }),
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
  getEvent: (id, config = {}) => api.get(`/users/events/${id}/`, config),
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
  createOffer: async (data) => {
    await ensureCsrfToken();
    return api.post('/users/offers/', data);
  },
  getOffers: () => api.get('/users/offers/'),
  getReceivedOffers: () => api.get('/users/offers/received/'),
  getSentOffers: () => api.get('/users/offers/sent/'),
  acceptOffer: async (offerId) => {
    await ensureCsrfToken();
    const id = encodeURIComponent(String(offerId));
    return api.post(`/users/offers/${id}/accept/`);
  },
  rejectOffer: async (offerId) => {
    await ensureCsrfToken();
    return api.post(`/users/offers/${offerId}/reject/`);
  },
  counterOffer: async (offerId, data) => {
    await ensureCsrfToken();
    return api.post(`/users/offers/${offerId}/counter/`, data);
  },
  getOffer: (offerId) => api.get(`/users/offers/${offerId}/`),
};

export const adminAPI = {
  getPendingTickets: () => api.get('/users/admin/pending-tickets/'),
  getDashboardStats: () => api.get('/users/admin/dashboard/stats/'),
  getTransactions: (params) => api.get('/users/admin/transactions/', { params }),
  cancelOrder: async (orderId, data = {}) => {
    await ensureCsrfToken();
    return api.post(`/users/admin/orders/${orderId}/cancel/`, data);
  },
  approveTicket: async (ticketId) => {
    await ensureCsrfToken();
    return api.post(`/users/admin/tickets/${ticketId}/approve/`);
  },
  rejectTicket: async (ticketId) => {
    await ensureCsrfToken();
    return api.post(`/users/admin/tickets/${ticketId}/reject/`);
  },
};

export const contactAPI = {
  createContactMessage: (data) => api.post('/users/contact-messages/', data),
};

export const eventRequestAPI = {
  create: (data) => api.post('/users/event-requests/', data),
};

export default api;

