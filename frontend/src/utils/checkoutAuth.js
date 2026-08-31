/**
 * Checkout auth failure classification.
 * Safari ITP often yields 403 (CSRF / ownership) while the JWT session is still valid.
 * Only HTTP 401 should force re-login. Timeouts and gateway errors are not session expiry.
 */
export function isCheckoutAuthSessionFailure(err) {
  const status = err?.response?.status;
  const code = err?.code;
  if (
    code === 'ECONNABORTED' ||
    code === 'ERR_NETWORK' ||
    code === 'ERR_CANCELED' ||
    status === 502 ||
    status === 503 ||
    status === 504
  ) {
    return false;
  }
  return status === 401;
}
