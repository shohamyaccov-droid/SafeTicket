/** Default and event document titles for Google + Helmet. */

export const DEFAULT_SITE_TITLE =
  'TradeTix - זירת מסחר בטוחה למכירת כרטיסים יד שנייה';

export const DEFAULT_SITE_DESCRIPTION =
  'טריידטיקס (TradeTix) — זירת מסחר בטוחה בישראל לקנייה ומכירת כרטיסים יד שנייה. תשלום מאובטח והגנה על הכסף.';

/**
 * Event SERP title: "כרטיסים לאייל גולן במנורה - TradeTix"
 */
export function eventDocumentTitle({ artistName, eventName, venue } = {}) {
  const subject = String(artistName || eventName || '').trim();
  const place = String(venue || '').trim();
  if (subject && place) {
    return `כרטיסים ל${subject} ב${place} - TradeTix`;
  }
  if (subject) {
    return `כרטיסים ל${subject} - TradeTix`;
  }
  return DEFAULT_SITE_TITLE;
}
