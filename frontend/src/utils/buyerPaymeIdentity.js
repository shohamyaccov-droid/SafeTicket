/**
 * PayMe hosted checkout requires a real buyer name + phone on the authenticated user.
 * Email-like usernames are not accepted as a legal name.
 */
export function buyerHasPaymeIdentity(user) {
  if (!user) return false;
  const first = String(user.first_name || '').trim();
  const last = String(user.last_name || '').trim();
  const full = `${first} ${last}`.trim() || String(user.full_name || '').trim();
  const uname = String(user.username || '').trim();
  const nameOk =
    full.length >= 2 || (uname.length >= 2 && !uname.includes('@'));
  const phoneRaw = String(user.phone_number || user.bit_phone_number || '').trim();
  const digits = phoneRaw.replace(/\D/g, '');
  const phoneOk = digits.length >= 9;
  return Boolean(nameOk && phoneOk);
}

export function buyerMissingPaymeFields(user) {
  const missing = [];
  if (!user) return ['name', 'phone'];
  const first = String(user.first_name || '').trim();
  const last = String(user.last_name || '').trim();
  const full = `${first} ${last}`.trim() || String(user.full_name || '').trim();
  const uname = String(user.username || '').trim();
  const nameOk =
    full.length >= 2 || (uname.length >= 2 && !uname.includes('@'));
  if (!nameOk) missing.push('name');
  const phoneRaw = String(user.phone_number || user.bit_phone_number || '').trim();
  const digits = phoneRaw.replace(/\D/g, '');
  if (digits.length < 9) missing.push('phone');
  return missing;
}
