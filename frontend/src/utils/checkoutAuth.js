/**
 * Checkout auth failure classification.
 * Safari ITP often yields 403 (CSRF / ownership) while the JWT session is still valid.
 * Only HTTP 401 should force re-login.
 */
export function isCheckoutAuthSessionFailure(err) {
  return err?.response?.status === 401;
}
