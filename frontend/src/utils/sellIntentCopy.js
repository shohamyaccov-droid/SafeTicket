/**
 * Intent-matched sell copy from Google Ads winners (Aug 8 – Sep 4 2026).
 * High-intent phrase "איך למכור כרטיס" converted at ₪11.96 CPA / 50% CVR;
 * general "אתר למכירת כרטיסים" spent ₪62 with 0 conversions — keep off.
 */

const INTENT_COPY = {
  howto: {
    h1: 'איך למכור כרטיס להופעה — בלי עמלה ובלי להיעקץ',
    subtitle: 'העלו את הכרטיס ב־3 דקות. הכסף בנאמנות SafePay עד אחרי ההופעה.',
    source: 'איך למכור כרטיס',
  },
  stuck: {
    h1: 'נתקעתם עם כרטיס? מכרו אותו עכשיו ב־0% עמלה',
    subtitle: 'זמן הביטול עבר — עדיין אפשר לקבל את הכסף בחזרה דרך TradeTix.',
    source: 'נתקעתי עם כרטיס',
  },
  where: {
    h1: 'איפה מוכרים כרטיסים להופעה בצורה בטוחה',
    subtitle: 'TradeTix — זירת מסחר יד־שנייה עם SafePay. 0% עמלה למוכרים.',
    source: 'איפה מוכרים כרטיסים',
  },
  sold_certainty: {
    h1: 'הכרטיס שלך כבר נמכר — נשאר רק להעלות אותו',
    subtitle: 'קונים מחפשים את ההופעה הזו עכשיו. העלו PDF או תמונה והתחילו לקבל הצעות.',
    source: 'fb:הכרטיס שלך נמכר',
  },
  default: {
    h1: 'תהליך הצעת כרטיס מאובטח',
    subtitle: 'הצע את הכרטיס שלך בצורה בטוחה ומאובטחת',
    source: 'default',
  },
};

function normalizeTerm(raw) {
  return String(raw || '')
    .trim()
    .toLowerCase()
    .replace(/["'[\]‏]/g, '');
}

/**
 * @param {string | URLSearchParams | { get?: Function }} search
 * @returns {{ h1: string, subtitle: string, source: string, intent: string }}
 */
export function resolveSellIntentCopy(search) {
  let params;
  if (search && typeof search.get === 'function') {
    params = search;
  } else {
    const raw =
      search == null
        ? ''
        : typeof search === 'string'
          ? search
          : typeof search.toString === 'function'
            ? search.toString()
            : '';
    params = new URLSearchParams(raw.startsWith('?') ? raw.slice(1) : raw);
  }

  const explicit = normalizeTerm(params.get('intent') || params.get('sell_intent'));
  if (explicit && INTENT_COPY[explicit]) {
    return { ...INTENT_COPY[explicit], intent: explicit };
  }

  const utmContent = normalizeTerm(params.get('utm_content'));
  if (utmContent.includes('sold') || utmContent.includes('נמכר') || utmContent === 'certainty') {
    return { ...INTENT_COPY.sold_certainty, intent: 'sold_certainty' };
  }

  const term = normalizeTerm(
    params.get('utm_term') || params.get('keyword') || params.get('q') || '',
  );
  const campaign = normalizeTerm(params.get('utm_campaign') || '');
  const haystack = `${term} ${campaign} ${utmContent}`;

  if (haystack.includes('נתקע') || haystack.includes('stuck')) {
    return { ...INTENT_COPY.stuck, intent: 'stuck' };
  }
  if (
    haystack.includes('איך למכור') ||
    haystack.includes('howto') ||
    haystack.includes('how-to') ||
    haystack.includes('how_to')
  ) {
    return { ...INTENT_COPY.howto, intent: 'howto' };
  }
  if (haystack.includes('איפה') || haystack.includes('where')) {
    return { ...INTENT_COPY.where, intent: 'where' };
  }
  if (
    haystack.includes('נמכר') ||
    haystack.includes('העלת') ||
    haystack.includes('upload') ||
    params.get('utm_source') === 'facebook' ||
    params.get('utm_source') === 'instagram' ||
    params.get('fbclid')
  ) {
    // Paid social winner creative leads with certainty — match landing headline.
    if (params.get('fbclid') || params.get('utm_source') === 'facebook' || params.get('utm_source') === 'instagram') {
      return { ...INTENT_COPY.sold_certainty, intent: 'sold_certainty' };
    }
  }

  return { ...INTENT_COPY.default, intent: 'default' };
}

export function buildSellerDemandLines(event) {
  if (!event) return null;
  const waitlist = Number(event.waitlist_count);
  const views = Number(event.view_count);
  const hasWaitlist = Number.isFinite(waitlist) && waitlist > 0;
  const hasViews = Number.isFinite(views) && views >= 10;
  if (!hasWaitlist && !hasViews) {
    return {
      headline: 'הכרטיס שלך כבר נמכר — נשאר רק להעלות אותו',
      detail: 'קונים מחפשים כרטיסים להופעה הזו. העלאה לוקחת פחות מדקה.',
      tone: 'certainty',
    };
  }
  const parts = [];
  if (hasWaitlist) {
    parts.push(
      waitlist === 1
        ? 'קונה אחד מחכה ברשימת ההמתנה לאירוע הזה'
        : `${waitlist} קונים מחכים ברשימת ההמתנה לאירוע הזה`,
    );
  }
  if (hasViews) {
    parts.push(`${views.toLocaleString('he-IL')} צפיות בעמוד האירוע`);
  }
  return {
    headline: 'הביקוש כבר כאן — הכרטיס רק מחכה להעלאה',
    detail: parts.join(' · '),
    tone: hasWaitlist ? 'demand' : 'views',
  };
}

export { INTENT_COPY };
