const STORAGE_KEY = 'tradetix_cart_token';

export function normalizeCartToken(raw) {
  return String(raw || '').toLowerCase().replace(/[^0-9a-f]/g, '');
}

export function getOrCreateCartToken() {
  if (typeof sessionStorage === 'undefined') {
    return '';
  }
  try {
    let token = normalizeCartToken(sessionStorage.getItem(STORAGE_KEY));
    if (token.length < 16) {
      token = (typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`
      ).replace(/-/g, '');
      sessionStorage.setItem(STORAGE_KEY, token);
    }
    return token;
  } catch {
    return '';
  }
}

export function formatHoldCountdown(rawSeconds) {
  const seconds = Math.max(0, Math.floor(Number(rawSeconds) || 0));
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export function holdTimerLabel(rawSeconds) {
  return `הכרטיס שמור לך ל-${formatHoldCountdown(rawSeconds)} דקות לפני שישוחרר חזרה למלאי.`;
}
