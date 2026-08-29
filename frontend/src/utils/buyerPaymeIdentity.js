/**
 * Checkout identity: email + phone are required. First/last name are optional.
 */
import { isValidRequiredEmail, isValidRequiredPhone } from './contactValidation';

export function buyerHasPaymeIdentity(user) {
  if (!user) return false;
  const emailOk = isValidRequiredEmail(user.email);
  const phoneRaw = String(user.phone_number || user.bit_phone_number || '').trim();
  return Boolean(emailOk && isValidRequiredPhone(phoneRaw));
}

export function buyerMissingPaymeFields(user) {
  const missing = [];
  if (!user) return ['phone'];
  const phoneRaw = String(user.phone_number || user.bit_phone_number || '').trim();
  if (!isValidRequiredPhone(phoneRaw)) missing.push('phone');
  return missing;
}
