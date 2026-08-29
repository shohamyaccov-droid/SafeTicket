/** Shared buyer/seller/guest contact rules: email + phone required, names optional. */

export function phoneDigitCount(phone) {
  return String(phone || '').replace(/\D/g, '').length;
}

export function isValidRequiredEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email || '').trim());
}

export function isValidRequiredPhone(phone) {
  const digits = phoneDigitCount(phone);
  return digits >= 9 && digits <= 15;
}

export function validateRequiredEmail(email) {
  if (!isValidRequiredEmail(email)) return 'נא להזין אימייל תקין';
  return null;
}

export function validateRequiredPhone(phone) {
  if (!isValidRequiredPhone(phone)) return 'נא להזין מספר טלפון תקין (לפחות 9 ספרות)';
  return null;
}

export function validateGuestContact({ email, phone } = {}) {
  return validateRequiredEmail(email) || validateRequiredPhone(phone) || null;
}

export function isGuestContactComplete({ email, phone } = {}) {
  return isValidRequiredEmail(email) && isValidRequiredPhone(phone);
}
