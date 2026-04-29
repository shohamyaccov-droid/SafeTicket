const FIELD_LABELS_HE = {
  username: 'שם משתמש',
  email: 'אימייל',
  password: 'סיסמה',
  password2: 'אימות סיסמה',
  first_name: 'שם פרטי',
  last_name: 'שם משפחה',
  phone_number: 'טלפון',
  guest_email: 'אימייל',
  guest_phone: 'טלפון',
  ticket: 'כרטיס',
  ticket_id: 'כרטיס',
  amount: 'סכום',
  total_amount: 'סכום לתשלום',
  quantity: 'כמות',
  listing_price: 'מחיר מכירה',
  original_price: 'מחיר',
  asking_price: 'מחיר',
  pdf_file: 'קובץ כרטיס',
  receipt_file: 'הוכחת קנייה',
  non_field_errors: '',
  detail: '',
  error: '',
  message: '',
};

const COMMON_TRANSLATIONS = [
  [/invalid total amount|amount mismatch|amount does not match/i, 'הסכום לתשלום לא תואם למחיר המעודכן. רעננו את העמוד ונסו שוב.'],
  [/ticket.*reserved|someone else.*cart|already.*reserved|held by another/i, 'הכרטיס כבר נתפס על ידי משתמש אחר. ניתן לנסות שוב בעוד כמה דקות.'],
  [/ticket.*sold|no longer available|not available|just sold/i, 'הכרטיס אינו זמין יותר. אנא בחרו כרטיס אחר.'],
  [/not enough tickets/i, 'אין מספיק כרטיסים זמינים עבור הבקשה הזו.'],
  [/offer.*no longer pending|offer.*not pending/i, 'ההצעה כבר אינה זמינה. ייתכן שהיא טופלה על ידי משתמש אחר.'],
  [/offer.*expired/i, 'פג תוקף ההצעה.'],
  [/you cannot purchase your own tickets/i, 'לא ניתן לרכוש כרטיסים שהעלית בעצמך.'],
  [/you cannot make an offer on your own ticket/i, 'לא ניתן להציע מחיר על כרטיס שלך.'],
  [/authentication credentials were not provided|not authenticated/i, 'נדרש להתחבר כדי לבצע פעולה זו.'],
  [/permission|forbidden|not have permission/i, 'אין לך הרשאה לבצע פעולה זו.'],
  [/csrf/i, 'שגיאת אבטחה בתקשורת. רעננו את העמוד ונסו שוב.'],
  [/network error/i, 'שגיאת תקשורת עם השרת. בדקו את החיבור ונסו שוב.'],
  [/server error|internal server error|request failed with status code 500/i, 'שגיאת שרת זמנית. נסו שוב בעוד רגע.'],
  [/this field is required|required/i, 'שדה חובה חסר.'],
  [/enter a valid email|valid email/i, 'נא להזין כתובת אימייל תקינה.'],
  [/password fields didn'?t match|password.*match/i, 'הסיסמאות אינן תואמות.'],
  [/a user with that username already exists|already exists/i, 'כבר קיים חשבון עם הפרטים האלה.'],
  [/ensure this value is greater than or equal to/i, 'הערך שהוזן נמוך מדי.'],
  [/ensure this value is less than or equal to/i, 'הערך שהוזן גבוה מדי.'],
  [/invalid|not a valid/i, 'הערך שהוזן אינו תקין.'],
];

function translateText(raw) {
  const text = String(raw || '').replace(/<[^>]*>/g, '').trim();
  if (!text) return '';
  for (const [pattern, he] of COMMON_TRANSLATIONS) {
    if (pattern.test(text)) return he;
  }
  return text;
}

function flattenMessages(value, field = '') {
  if (value == null || value === '') return [];
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    const translated = translateText(value);
    const label = FIELD_LABELS_HE[field] ?? field;
    return [label ? `${label}: ${translated}` : translated];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item) => flattenMessages(item, field));
  }
  if (typeof value === 'object') {
    return Object.entries(value).flatMap(([key, nested]) => flattenMessages(nested, key));
  }
  return [];
}

export function apiErrorMessageHe(errorOrData, fallback = 'אירעה שגיאה. אנא נסו שוב.') {
  const data = errorOrData?.response?.data ?? errorOrData?.data ?? errorOrData;
  const status = errorOrData?.response?.status;

  if (status === 401) return 'החיבור שלך פג תוקף. אנא התחבר מחדש.';
  if (status === 403 && data == null) return 'אין לך הרשאה לבצע פעולה זו.';

  const messages = flattenMessages(data)
    .map((msg) => String(msg || '').trim())
    .filter(Boolean);

  if (messages.length) {
    return [...new Set(messages)].slice(0, 3).join(' ');
  }

  if (errorOrData?.message) {
    return translateText(errorOrData.message);
  }

  return fallback;
}
