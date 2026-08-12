/**
 * Admin helpers for contacting sellers about invalid / pending tickets.
 */

/** Digits only; convert leading Israeli 0… to 972… for wa.me */
export function normalizePhoneForWhatsApp(phone) {
  const digits = String(phone || '').replace(/\D/g, '');
  if (!digits) return '';
  if (digits.startsWith('972')) return digits;
  if (digits.startsWith('0') && digits.length >= 9) return `972${digits.slice(1)}`;
  return digits;
}

export function whatsAppChatUrl(phone, message = '') {
  const intl = normalizePhoneForWhatsApp(phone);
  if (!intl) return null;
  const base = `https://wa.me/${intl}`;
  const text = String(message || '').trim();
  if (!text) return base;
  return `${base}?text=${encodeURIComponent(text)}`;
}

export function telHref(phone) {
  const raw = String(phone || '').trim();
  if (!raw) return null;
  // Keep + and digits for tel: links
  const cleaned = raw.replace(/[^\d+]/g, '');
  if (!cleaned || cleaned === '+') return null;
  return `tel:${cleaned}`;
}

export function mailtoHref(email) {
  const addr = String(email || '').trim();
  if (!addr || !addr.includes('@')) return null;
  return `mailto:${addr}`;
}

export function sellerDisplayName(contact, fallbackUsername = '') {
  if (!contact || typeof contact !== 'object') {
    return fallbackUsername || '—';
  }
  return (
    contact.full_name ||
    contact.username ||
    fallbackUsername ||
    '—'
  );
}
