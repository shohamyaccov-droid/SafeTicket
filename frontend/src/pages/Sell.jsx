import { useState, useEffect, useMemo, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { ticketAPI, eventAPI, artistAPI, eventRequestAPI, authAPI } from '../services/api';
import { createListFetchAbort } from '../utils/listFetch';
import SellFormSkeleton from '../components/skeletons/SellFormSkeleton';
import { toastError } from '../utils/toast';
import { apiErrorMessageHe } from '../utils/apiErrors';
import { iso4217FromCountry, currencySymbol, formatAmountForCurrency } from '../utils/priceFormat';
import { VENUE_BLOOMFIELD_CONCERT, VENUE_RAMAT_GAN, VENUE_CAESAREA } from '../utils/venueMaps';
import { CONCERT_BLOCK_COUNT, CONCERT_SECTION_NAMES } from '../utils/bloomfieldConcertGeometry';
import { isRamatGanVenueEvent, ramatGanSellSectionOptions } from '../utils/ramatGanSellSections';
import { isCaesareaVenueEvent, caesareaSellSectionOptions } from '../utils/caesareaSellSections';
import { displayEventVenueName, formatEventLocation } from '../utils/eventLocalTime';
import '../components/BecomeSellerModal.css';

const SELL_PAGE_BUILD_TAG = import.meta.env.VITE_BUILD_ID || 'local-dev';

/** PDF or image (JPEG/PNG) — matches backend ticket upload */
const TICKET_FILE_INPUT_ACCEPT =
  'image/*,application/pdf,.pdf,.jpg,.jpeg,.png';
const MAX_TICKET_FILE_SIZE_BYTES = 5 * 1024 * 1024;
const TICKET_FILE_CONSTRAINTS_HE = 'פורמטים נתמכים: PDF, JPG, PNG · גודל מקסימלי: 5MB לקובץ';

function isPdfFile(file) {
  if (!file) return false;
  return file.type === 'application/pdf' || /\.pdf$/i.test(file.name || '');
}

function isTicketAttachmentFile(file) {
  if (!file) return false;
  if (isPdfFile(file)) return true;
  if (file.type === 'image/jpeg' || file.type === 'image/jpg' || file.type === 'image/png') return true;
  return /\.(jpe?g|png)$/i.test(file.name || '');
}

function formatFileSize(bytes) {
  const n = Number(bytes || 0);
  if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)}MB`;
  if (n >= 1024) return `${Math.ceil(n / 1024)}KB`;
  return `${n}B`;
}

function ticketFileValidationError(file, { requirePdf = false } = {}) {
  if (!file) return 'לא נבחר קובץ.';
  if (!isTicketAttachmentFile(file)) {
    return `הקובץ "${file.name || 'ללא שם'}" אינו נתמך. ניתן להעלות PDF, JPG או PNG בלבד.`;
  }
  if (requirePdf && !isPdfFile(file)) {
    return 'למספר כרטיסים במצב קובץ יחיד יש להעלות PDF מרובה עמודים בלבד.';
  }
  if (file.size > MAX_TICKET_FILE_SIZE_BYTES) {
    return `הקובץ "${file.name || 'ללא שם'}" גדול מדי (${formatFileSize(file.size)}). הגודל המקסימלי הוא 5MB.`;
  }
  return '';
}

function validateTicketFiles(files, options = {}) {
  for (const file of files || []) {
    const msg = ticketFileValidationError(file, options);
    if (msg) return msg;
  }
  return '';
}

/* eslint-disable react/prop-types */
function SellFieldError({ message }) {
  if (!message) return null;
  return (
    <p className="sell-field-error" role="alert">
      {message}
    </p>
  );
}
/* eslint-enable react/prop-types */

function parseApiMessage(data, fallback) {
  if (typeof data === 'object' && data !== null) {
    const txt = Object.values(data).flat().filter(Boolean).join(' ');
    if (txt) return txt;
  }
  if (typeof data === 'string' && data.trim()) return data;
  return fallback;
}

/** DD.MM.YYYY | Venue Name | Artist Name — compact labels for iOS event <select> */
function formatEventDropdownLabel(event) {
  const d = event?.date ? new Date(event.date) : null;
  const dateStr =
    d && !Number.isNaN(d.getTime())
      ? `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`
      : '';
  const venue = displayEventVenueName(event);
  const artist = (
    event.artist_name
    || event.artist_detail?.name
    || event.name
    || ''
  ).trim();
  return [dateStr, venue, artist].filter(Boolean).join(' | ');
}

const SELL_DRAFT_STORAGE_KEY = 'safeticket_sell_listing_draft_v1';

const defaultSellFormData = () => ({
  event_id: '',
  event_name: '',
  event_date: '',
  event_time: '',
  venue: '',
  selectedEvent: null,
  seat_row: '',
  section: '',
  row: '',
  available_quantity: 1,
  ticket_packages: [],
  singleMultiPagePdf: null,
  is_together: true,
  start_seat: '',
  listing_price: '',
  ticket_type: 'pdf',
  split_type: 'כל כמות',
  is_obstructed_view: false,
});

function readSellListingDraft() {
  try {
    const raw = sessionStorage.getItem(SELL_DRAFT_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeSellListingDraft(draft) {
  try {
    if (!draft) sessionStorage.removeItem(SELL_DRAFT_STORAGE_KEY);
    else sessionStorage.setItem(SELL_DRAFT_STORAGE_KEY, JSON.stringify(draft));
  } catch {
    /* ignore quota / private mode */
  }
}

function buildSellListingDraftSnapshot({
  formData,
  uploadMethod,
  selectedCategory,
  selectedArtistId,
  sellerListingTermsAccepted,
}) {
  return {
    uploadMethod,
    selectedCategory,
    selectedArtistId,
    sellerListingTermsAccepted,
    formData: {
      event_id: formData.event_id,
      event_name: formData.event_name,
      section: formData.section,
      row: formData.row,
      available_quantity: formData.available_quantity,
      is_together: formData.is_together,
      start_seat: formData.start_seat,
      listing_price: formData.listing_price,
      ticket_type: formData.ticket_type,
      split_type: formData.split_type,
      is_obstructed_view: formData.is_obstructed_view,
      ticket_packages: (formData.ticket_packages || []).map((pkg) => ({
        seat_number: pkg?.seat_number || '',
      })),
    },
  };
}

/* eslint-disable react/prop-types */
function PasswordField({ id, name, label, value, onChange, required }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="form-group">
      <label htmlFor={id}>{label}</label>
      <div className="sell-password-field-wrap">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          name={name}
          value={value}
          onChange={onChange}
          required={required}
          autoComplete={name === 'password2' ? 'new-password' : 'current-password'}
        />
        <button
          type="button"
          className="sell-password-toggle"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'הסתר סיסמה' : 'הצג סיסמה'}
          aria-pressed={visible}
        >
          {visible ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M3 3l18 18M10.58 10.58A2 2 0 0012 15a2 2 0 001.42-.58M9.88 4.24A10.94 10.94 0 0112 5c5 0 9.27 3.11 11 7a11.8 11.8 0 01-2.16 3.19M6.11 6.11A10.94 10.94 0 003 12c1.73 3.89 6 7 11 7 1.01 0 1.98-.13 2.88-.37" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
/* eslint-enable react/prop-types */

function InlineAuthFunnel({ onAuthed }) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState('register');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [becomeSellerNow, setBecomeSellerNow] = useState(false);
  const [sellerFieldErrors, setSellerFieldErrors] = useState({});
  const [payoutMethod, setPayoutMethod] = useState('bank');
  const [bitPhoneConfirm, setBitPhoneConfirm] = useState('');
  const [acceptedEscrow, setAcceptedEscrow] = useState(false);
  const [sellerBank, setSellerBank] = useState({
    account_holder_name: '',
    id_number: '',
    bank_name_or_code: '',
    branch_number: '',
    account_number: '',
  });
  const [form, setForm] = useState({
    email: '',
    phone_number: '',
    password: '',
    password2: '',
    first_name: '',
    last_name: '',
  });

  const onChange = (e) => {
    const { name, value } = e.target;
    setError('');
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const setSellerBankField = (key, value) => {
    setSellerBank((prev) => ({ ...prev, [key]: value }));
  };

  const validateSellerOnboarding = () => {
    const fe = {};
    if (!acceptedEscrow) fe.acceptedEscrow = 'יש לאשר את תנאי הנאמנות כדי להמשיך.';
    const signupPhone = String(form.phone_number || '').replace(/\D/g, '').replace(/^972/, '0');
    if (!/^05\d{8}$/.test(signupPhone)) {
      fe.phone_number = 'נא להזין מספר טלפון ישראלי תקין.';
    }

    if (payoutMethod === 'bank') {
      if ((sellerBank.account_holder_name || '').trim().length < 2) fe.account_holder_name = 'נא להזין שם בעל חשבון.';
      const idRaw = (sellerBank.id_number || '').replace(/[\s-]/g, '');
      if (!/^\d+$/.test(idRaw) || idRaw.length < 5 || idRaw.length > 9) fe.id_number = 'נא להזין מספר תעודת זהות תקין.';
      if (!(sellerBank.bank_name_or_code || '').trim()) fe.bank_name_or_code = 'נא לציין בנק (שם או מספר).';
      if (!/^\d+$/.test((sellerBank.branch_number || '').trim())) fe.branch_number = 'נא להזין מספר סניף תקין.';
      if (!/^\d{4,}$/.test((sellerBank.account_number || '').trim())) fe.account_number = 'נא להזין מספר חשבון תקין.';
    } else {
      const idRaw = (sellerBank.id_number || '').replace(/[\s-]/g, '');
      if (!/^\d+$/.test(idRaw) || idRaw.length < 5 || idRaw.length > 9) {
        fe.id_number = 'נא להזין מספר תעודת זהות תקין.';
      }
      const normalize = (v) => String(v || '').replace(/\D/g, '').replace(/^972/, '0');
      const phoneMain = normalize(form.phone_number);
      const phoneConfirm = normalize(bitPhoneConfirm);
      if (phoneMain !== phoneConfirm) fe.bit_phone_number_confirm = 'אימות מספר הטלפון לביט חייב להיות זהה למספר הטלפון הראשי.';
    }
    return fe;
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSellerFieldErrors({});
    if (mode === 'register' && form.password !== form.password2) {
      setError('הסיסמאות אינן תואמות.');
      return;
    }
    if (mode === 'register' && becomeSellerNow) {
      const sellerErrors = validateSellerOnboarding();
      if (Object.keys(sellerErrors).length > 0) {
        setSellerFieldErrors(sellerErrors);
        return;
      }
    }
    setSaving(true);
    try {
      if (mode === 'login') {
        const result = await login(form.email.trim(), form.password);
        if (!result.success) {
          setError(result.errorHebrew || result.error || 'ההתחברות נכשלה.');
          return;
        }
      } else {
        const result = await register({
          username: form.email.trim(),
          email: form.email.trim(),
          phone_number: form.phone_number.trim(),
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
          password: form.password,
          password2: form.password2,
          role: 'buyer',
        });
        if (!result.success) {
          setError(parseApiMessage(result.error, 'ההרשמה נכשלה.'));
          return;
        }
        if (becomeSellerNow) {
          try {
            await authAPI.getCsrf();
            await authAPI.upgradeToSeller({
              phone_number: form.phone_number.trim(),
              payout_method: payoutMethod,
              bit_phone_number: payoutMethod === 'bit' ? form.phone_number.replace(/\D/g, '').replace(/^972/, '0') : '',
              account_holder_name: payoutMethod === 'bank'
                ? sellerBank.account_holder_name.trim()
                : `${form.first_name.trim()} ${form.last_name.trim()}`.trim(),
              id_number: sellerBank.id_number.replace(/[\s-]/g, ''),
              bank_name_or_code: payoutMethod === 'bank' ? sellerBank.bank_name_or_code.trim() : '',
              branch_number: payoutMethod === 'bank' ? sellerBank.branch_number.trim() : '',
              account_number: payoutMethod === 'bank' ? sellerBank.account_number.trim() : '',
              accepted_escrow_terms: true,
            });
          } catch (upgradeErr) {
            setError(
              `נרשמת בהצלחה, אך שדרוג למוכר נכשל: ${parseApiMessage(
                upgradeErr.response?.data,
                upgradeErr.message || 'נסה שוב מטאטא "הפוך למוכר".'
              )}`
            );
            await onAuthed?.();
            return;
          }
        }
      }
      await onAuthed?.();
    } catch (err) {
      setError(parseApiMessage(err.response?.data, err.message || 'הפעולה נכשלה.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="listing-card sell-inline-card">
      <h2>{mode === 'login' ? 'התחברות כדי להתחיל למכור' : 'הרשמה מהירה כדי להתחיל למכור'}</h2>
      {error ? <div className="error-message">{error}</div> : null}
      <form onSubmit={onSubmit} className="sell-inline-auth-form sell-inline-auth-form--compact">
        {mode === 'register' ? (
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="first_name">שם פרטי</label>
              <input id="first_name" name="first_name" value={form.first_name} onChange={onChange} required />
            </div>
            <div className="form-group">
              <label htmlFor="last_name">שם משפחה</label>
              <input id="last_name" name="last_name" value={form.last_name} onChange={onChange} required />
            </div>
          </div>
        ) : null}
        <div className="form-group">
          <label htmlFor="email">אימייל</label>
          <input id="email" type="email" name="email" value={form.email} onChange={onChange} required />
        </div>
        {mode === 'register' ? (
          <div className="form-group">
            <label htmlFor="phone_number">מספר טלפון</label>
            <input id="phone_number" type="tel" dir="ltr" name="phone_number" value={form.phone_number} onChange={onChange} required />
            {sellerFieldErrors.phone_number ? <span className="become-seller-field-error">{sellerFieldErrors.phone_number}</span> : null}
          </div>
        ) : null}
        <PasswordField id="password" name="password" label="סיסמה" value={form.password} onChange={onChange} required />
        {mode === 'register' ? (
          <PasswordField id="password2" name="password2" label="אימות סיסמה" value={form.password2} onChange={onChange} required />
        ) : null}
        {mode === 'register' ? (
          <label className="sell-inline-become-seller-check">
            <input
              type="checkbox"
              checked={becomeSellerNow}
              onChange={(e) => {
                setBecomeSellerNow(e.target.checked);
                setSellerFieldErrors({});
              }}
            />
            <span>הפוך למוכר עכשיו כדי להעלות כרטיסים</span>
          </label>
        ) : null}
        {mode === 'register' && becomeSellerNow ? (
          <fieldset className="become-seller-bank-fieldset sell-inline-seller-fieldset">
            <legend>פרטי זיכוי למוכר</legend>
            <div className="become-seller-payout-methods">
              <label className="become-seller-radio">
                <input type="radio" name="inline_payout_method" checked={payoutMethod === 'bank'} onChange={() => setPayoutMethod('bank')} />
                <span>העברה בנקאית</span>
              </label>
              <label className="become-seller-radio">
                <input type="radio" name="inline_payout_method" checked={payoutMethod === 'bit'} onChange={() => setPayoutMethod('bit')} />
                <span>ביט</span>
              </label>
            </div>
            {payoutMethod === 'bit' ? (
              <p className="sell-inline-bit-disclaimer">אפשר להזין רק מספר טלפון לקבלה בביט</p>
            ) : null}
            {payoutMethod === 'bank' ? (
              <>
                <label className="become-seller-label">
                  שם בעל החשבון
                  <input type="text" value={sellerBank.account_holder_name} onChange={(e) => setSellerBankField('account_holder_name', e.target.value)} required />
                  {sellerFieldErrors.account_holder_name ? <span className="become-seller-field-error">{sellerFieldErrors.account_holder_name}</span> : null}
                </label>
                <label className="become-seller-label">
                  תעודת זהות
                  <input type="text" dir="ltr" value={sellerBank.id_number} onChange={(e) => setSellerBankField('id_number', e.target.value)} required />
                  {sellerFieldErrors.id_number ? <span className="become-seller-field-error">{sellerFieldErrors.id_number}</span> : null}
                </label>
                <label className="become-seller-label">
                  בנק (שם או מספר בנק)
                  <input type="text" value={sellerBank.bank_name_or_code} onChange={(e) => setSellerBankField('bank_name_or_code', e.target.value)} required />
                  {sellerFieldErrors.bank_name_or_code ? <span className="become-seller-field-error">{sellerFieldErrors.bank_name_or_code}</span> : null}
                </label>
                <div className="become-seller-row">
                  <label className="become-seller-label">
                    סניף
                    <input type="text" dir="ltr" value={sellerBank.branch_number} onChange={(e) => setSellerBankField('branch_number', e.target.value)} required />
                    {sellerFieldErrors.branch_number ? <span className="become-seller-field-error">{sellerFieldErrors.branch_number}</span> : null}
                  </label>
                  <label className="become-seller-label">
                    מספר חשבון
                    <input type="text" dir="ltr" value={sellerBank.account_number} onChange={(e) => setSellerBankField('account_number', e.target.value)} required />
                    {sellerFieldErrors.account_number ? <span className="become-seller-field-error">{sellerFieldErrors.account_number}</span> : null}
                  </label>
                </div>
              </>
            ) : (
              <>
                <label className="become-seller-label">
                  תעודת זהות
                  <input type="text" dir="ltr" value={sellerBank.id_number} onChange={(e) => setSellerBankField('id_number', e.target.value)} required />
                  {sellerFieldErrors.id_number ? <span className="become-seller-field-error">{sellerFieldErrors.id_number}</span> : null}
                </label>
                <div className="become-seller-row">
                  <label className="become-seller-label">
                    אימות מספר טלפון לביט
                    <input type="tel" dir="ltr" value={bitPhoneConfirm} onChange={(e) => setBitPhoneConfirm(e.target.value)} required />
                    {sellerFieldErrors.bit_phone_number_confirm ? <span className="become-seller-field-error">{sellerFieldErrors.bit_phone_number_confirm}</span> : null}
                  </label>
                </div>
              </>
            )}
            <label className="become-seller-check">
              <input type="checkbox" checked={acceptedEscrow} onChange={(e) => setAcceptedEscrow(e.target.checked)} />
              <span>אני מסכים לקבל את התשלום רק לאחר קיום האירוע, בהתאם לתקנון האתר</span>
            </label>
            {sellerFieldErrors.acceptedEscrow ? (
              <span className="become-seller-field-error become-seller-field-error--block">{sellerFieldErrors.acceptedEscrow}</span>
            ) : null}
          </fieldset>
        ) : null}
        <button type="submit" className="auth-button" disabled={saving}>
          {saving ? 'שומר…' : mode === 'login' ? 'התחברות' : 'הרשמה'}
        </button>
      </form>
      <button
        type="button"
        className="sell-inline-switch-btn"
        onClick={() => {
          setMode((prev) => (prev === 'login' ? 'register' : 'login'));
          setError('');
        }}
      >
        {mode === 'login' ? 'אין חשבון? מעבר להרשמה' : 'יש חשבון? מעבר להתחברות'}
      </button>
    </div>
  );
}

function InlineBecomeSellerSection({ onSuccess }) {
  const [expanded, setExpanded] = useState(false);
  const [phone, setPhone] = useState('');
  const [payoutMethod, setPayoutMethod] = useState('bank');
  const [bitPhoneConfirm, setBitPhoneConfirm] = useState('');
  const [acceptedEscrow, setAcceptedEscrow] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [bank, setBank] = useState({
    account_holder_name: '',
    id_number: '',
    bank_name_or_code: '',
    branch_number: '',
    account_number: '',
  });

  const setBankField = (k, v) => setBank((prev) => ({ ...prev, [k]: v }));

  const validate = () => {
    const fe = {};
    if ((phone || '').trim().length < 8) fe.phone = 'נא להזין מספר טלפון תקין.';
    if ((bank.account_holder_name || '').trim().length < 2) fe.account_holder_name = 'נא להזין שם בעל חשבון.';
    const idRaw = (bank.id_number || '').replace(/[\s-]/g, '');
    if (!/^\d+$/.test(idRaw) || idRaw.length < 5 || idRaw.length > 9) fe.id_number = 'נא להזין מספר תעודת זהות תקין.';
    if (!acceptedEscrow) fe.acceptedEscrow = 'יש לאשר את תנאי הנאמנות כדי להמשיך.';
    if (payoutMethod === 'bank') {
      if (!(bank.bank_name_or_code || '').trim()) fe.bank_name_or_code = 'נא לציין בנק.';
      if (!/^\d+$/.test((bank.branch_number || '').trim())) fe.branch_number = 'נא להזין מספר סניף תקין.';
      if (!/^\d{4,}$/.test((bank.account_number || '').trim())) fe.account_number = 'נא להזין מספר חשבון תקין.';
    } else {
      const normalize = (v) => String(v || '').replace(/\D/g, '').replace(/^972/, '0');
      const one = normalize(phone);
      const two = normalize(bitPhoneConfirm);
      if (!/^05\d{8}$/.test(one)) fe.bit_phone_number = 'נא להזין מספר טלפון ביט ישראלי תקין.';
      if (one !== two) fe.bit_phone_number_confirm = 'מספרי הטלפון לביט אינם תואמים.';
    }
    return fe;
  };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    const fe = validate();
    if (Object.keys(fe).length) {
      setFieldErrors(fe);
      return;
    }
    setFieldErrors({});
    setSaving(true);
    try {
      await authAPI.getCsrf();
      await authAPI.upgradeToSeller({
        phone_number: phone.trim(),
        payout_method: payoutMethod,
        bit_phone_number: payoutMethod === 'bit' ? phone.replace(/\D/g, '').replace(/^972/, '0') : '',
        account_holder_name: bank.account_holder_name.trim(),
        id_number: bank.id_number.replace(/[\s-]/g, ''),
        bank_name_or_code: payoutMethod === 'bank' ? bank.bank_name_or_code.trim() : '',
        branch_number: payoutMethod === 'bank' ? bank.branch_number.trim() : '',
        account_number: payoutMethod === 'bank' ? bank.account_number.trim() : '',
        accepted_escrow_terms: true,
      });
      onSuccess?.();
    } catch (err) {
      setError(parseApiMessage(err.response?.data, err.message || 'שגיאה בשדרוג החשבון.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="listing-card sell-inline-card">
      <button type="button" className="sell-onboarding-toggle" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
        <span>הפוך למוכר</span>
        <span>{expanded ? '▲' : '▼'}</span>
      </button>
      <div className={`sell-onboarding-accordion ${expanded ? 'expanded' : ''}`}>
        <form onSubmit={submit} className="become-seller-form">
          <label className="become-seller-label">מספר טלפון
            <input type="tel" dir="ltr" value={phone} onChange={(e) => setPhone(e.target.value)} required />
            {fieldErrors.phone ? <span className="become-seller-field-error">{fieldErrors.phone}</span> : null}
          </label>
          <fieldset className="become-seller-bank-fieldset">
            <legend>איך תרצה לקבל את התשלום?</legend>
            <div className="become-seller-payout-methods">
              <label className="become-seller-radio"><input type="radio" checked={payoutMethod === 'bank'} onChange={() => setPayoutMethod('bank')} />העברה בנקאית</label>
              <label className="become-seller-radio"><input type="radio" checked={payoutMethod === 'bit'} onChange={() => setPayoutMethod('bit')} />ביט</label>
            </div>
            {payoutMethod === 'bit' ? (
              <p className="sell-inline-bit-disclaimer">אפשר להזין רק מספר טלפון לקבלה בביט — ללא פרטי בנק</p>
            ) : null}
            <label className="become-seller-label">שם בעל החשבון
              <input type="text" value={bank.account_holder_name} onChange={(e) => setBankField('account_holder_name', e.target.value)} required />
              {fieldErrors.account_holder_name ? <span className="become-seller-field-error">{fieldErrors.account_holder_name}</span> : null}
            </label>
            <label className="become-seller-label">תעודת זהות
              <input type="text" dir="ltr" value={bank.id_number} onChange={(e) => setBankField('id_number', e.target.value)} required />
              {fieldErrors.id_number ? <span className="become-seller-field-error">{fieldErrors.id_number}</span> : null}
            </label>
            {payoutMethod === 'bank' ? (
              <>
                <label className="become-seller-label">בנק (שם או מספר בנק)<input type="text" value={bank.bank_name_or_code} onChange={(e) => setBankField('bank_name_or_code', e.target.value)} required /></label>
                {fieldErrors.bank_name_or_code ? <span className="become-seller-field-error">{fieldErrors.bank_name_or_code}</span> : null}
                <div className="become-seller-row">
                  <label className="become-seller-label">סניף<input type="text" dir="ltr" value={bank.branch_number} onChange={(e) => setBankField('branch_number', e.target.value)} required /></label>
                  <label className="become-seller-label">מספר חשבון<input type="text" dir="ltr" value={bank.account_number} onChange={(e) => setBankField('account_number', e.target.value)} required /></label>
                </div>
                {fieldErrors.branch_number ? <span className="become-seller-field-error">{fieldErrors.branch_number}</span> : null}
                {fieldErrors.account_number ? <span className="become-seller-field-error">{fieldErrors.account_number}</span> : null}
              </>
            ) : (
              <label className="become-seller-label">אימות מספר טלפון לביט
                <input type="tel" dir="ltr" value={bitPhoneConfirm} onChange={(e) => setBitPhoneConfirm(e.target.value)} required />
                {fieldErrors.bit_phone_number ? <span className="become-seller-field-error">{fieldErrors.bit_phone_number}</span> : null}
                {fieldErrors.bit_phone_number_confirm ? <span className="become-seller-field-error">{fieldErrors.bit_phone_number_confirm}</span> : null}
              </label>
            )}
          </fieldset>
          <label className="become-seller-check"><input type="checkbox" checked={acceptedEscrow} onChange={(e) => setAcceptedEscrow(e.target.checked)} /><span>אני מסכים לקבל את התשלום רק לאחר קיום האירוע, בהתאם לתקנון האתר</span></label>
          {fieldErrors.acceptedEscrow ? <span className="become-seller-field-error become-seller-field-error--block">{fieldErrors.acceptedEscrow}</span> : null}
          {error ? <div className="become-seller-error">{error}</div> : null}
          <button type="submit" className="become-seller-submit" disabled={saving}>{saving ? 'שומר…' : 'אישור והמשך'}</button>
        </form>
      </div>
    </div>
  );
}

const rangeOptions = (start, end) =>
  Array.from({ length: end - start + 1 }, (_, i) => {
    const value = String(start + i);
    return { value, label: `גוש ${value}`, structured: false };
  });

const BLOOMFIELD_SECTION_OPTIONS = [
  ...rangeOptions(201, 209),
  ...rangeOptions(214, 216),
  ...rangeOptions(221, 229),
  ...rangeOptions(234, 236),
  ...rangeOptions(301, 338),
  ...rangeOptions(404, 406),
  ...rangeOptions(419, 431),
];

const BLOOMFIELD_CONCERT_SECTION_OPTIONS = CONCERT_SECTION_NAMES.map((name) => ({
  value: name,
  label: `גוש ${name}`,
  structured: false,
}));

/** Merge for_sell artists API with concert artists inferred from for_sell events (belt-and-suspenders). */
function mergeSellCatalogArtists(artistsFromApi, upcomingEvents) {
  const byId = new Map();
  for (const artist of artistsFromApi || []) {
    if (artist?.id != null) {
      byId.set(Number(artist.id), artist);
    }
  }
  for (const ev of upcomingEvents || []) {
    const cat = String(ev.category || '').toLowerCase();
    if (cat !== 'concert') continue;
    const detail = ev.artist_detail;
    const id = detail?.id ?? ev.artist;
    if (id == null) continue;
    const numId = Number(id);
    if (byId.has(numId)) continue;
    byId.set(numId, {
      id: numId,
      name: detail?.name || ev.artist_name || `Artist #${numId}`,
      image_url: detail?.image_url,
      total_tickets_count: 0,
    });
  }
  return [...byId.values()].sort((a, b) => (a.name || '').localeCompare(b.name || '', 'he'));
}

function isBloomfieldConcertEvent(eventLike) {
  if (!eventLike) return false;
  const venue = String(eventLike.venue || '').trim();
  const category = String(eventLike.category || '').toLowerCase();
  const hay = [
    eventLike.venue_detail?.name,
    eventLike.venue,
    eventLike.name,
  ]
    .filter(Boolean)
    .join(' ');
  return (
    venue === VENUE_BLOOMFIELD_CONCERT
    || (hay.includes('בלומפילד') && category === 'concert')
    || (hay.includes('אייל גולן') && hay.includes('בלומפילד'))
  );
}

function canonicalVenueName(eventLike) {
  const values = [
    eventLike?.venue_detail?.name,
    eventLike?.venue,
    eventLike?.selectedEvent?.venue_detail?.name,
    eventLike?.selectedEvent?.venue,
  ]
    .filter(Boolean)
    .map((v) => String(v).trim());
  const haystack = values.join(' ');
  if (values.some((v) => v === VENUE_BLOOMFIELD_CONCERT) || isBloomfieldConcertEvent(eventLike)) {
    return VENUE_BLOOMFIELD_CONCERT;
  }
  if (haystack.includes('בלומפילד')) return 'אצטדיון בלומפילד';
  if (haystack.includes('פיס ארנה') || haystack.includes('ארנה ירושלים')) return 'פיס ארנה ירושלים';
  if (haystack.includes('מנורה') || haystack.includes('מבטחים')) return 'היכל מנורה מבטחים';
  if (isCaesareaVenueEvent(eventLike)) return VENUE_CAESAREA;
  if (isRamatGanVenueEvent(eventLike)) return VENUE_RAMAT_GAN;
  return values[0] || '';
}

function generatedSectionOptionsForVenue(venueName) {
  if (venueName === 'היכל מנורה מבטחים') {
    return Array.from({ length: 12 }, (_, i) => {
      const number = i + 1;
      return [
        { value: `${number} תחתון`, label: `גוש ${number} תחתון`, structured: false },
        { value: `${number} עליון`, label: `גוש ${number} עליון`, structured: false },
      ];
    }).flat();
  }
  if (venueName === VENUE_BLOOMFIELD_CONCERT) {
    return BLOOMFIELD_CONCERT_SECTION_OPTIONS;
  }
  if (venueName === 'אצטדיון בלומפילד') {
    return BLOOMFIELD_SECTION_OPTIONS;
  }
  if (venueName === 'פיס ארנה ירושלים') {
    return [...rangeOptions(101, 122), ...rangeOptions(301, 330)];
  }
  if (venueName === VENUE_RAMAT_GAN) {
    return ramatGanSellSectionOptions();
  }
  if (venueName === VENUE_CAESAREA) {
    return caesareaSellSectionOptions();
  }
  return [];
}

/** Visual confirmation before submit: image thumbnail or PDF badge. */
/* eslint-disable react/prop-types */
function TicketAttachmentPreview({ file }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!file) {
      setUrl(null);
      return undefined;
    }
    if (isPdfFile(file)) {
      setUrl(null);
      return undefined;
    }
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);

  if (!file) return null;
  if (url) {
    return (
      <div className="sell-file-preview sell-file-preview--image">
        <img src={url} alt="" loading="lazy" decoding="async" />
        <span className="sell-file-preview-label">מוכן להעלאה</span>
        <span className="sell-file-preview-meta">{formatFileSize(file.size)}</span>
      </div>
    );
  }
  return (
    <div className="sell-file-preview sell-file-preview--pdf">
      <span className="sell-file-preview-pdf-icon" aria-hidden>
        PDF
      </span>
      <span className="sell-file-preview-label">מוכן להעלאה</span>
      <span className="sell-file-preview-meta">{formatFileSize(file.size)}</span>
    </div>
  );
}
/* eslint-enable react/prop-types */

const Sell = () => {
  const sellDraft = useMemo(() => readSellListingDraft(), []);
  // ALL HOOKS MUST BE CALLED FIRST - BEFORE ANY EARLY RETURNS
  const { user, loading: authLoading, refreshProfile } = useAuth();
  const [formData, setFormData] = useState(() => {
    const base = defaultSellFormData();
    const draftForm = sellDraft?.formData;
    if (!draftForm) return base;
    return {
      ...base,
      ...draftForm,
      selectedEvent: null,
      singleMultiPagePdf: null,
      ticket_packages: (draftForm.ticket_packages || []).map((pkg) => ({
        seat_number: pkg?.seat_number || '',
        pdf_file: null,
      })),
    };
  });
  const [uploadMethod, setUploadMethod] = useState(sellDraft?.uploadMethod || 'single_file');
  const [selectedCategory, setSelectedCategory] = useState(sellDraft?.selectedCategory || 'concert');
  const [selectedArtistId, setSelectedArtistId] = useState(sellDraft?.selectedArtistId || '');
  const [artists, setArtists] = useState([]);
  const [events, setEvents] = useState([]);
  /** Concert only: rows from GET ?for_sell=1&artist=<id> — sole source for the event <select> (no merged catalog). */
  const [artistEvents, setArtistEvents] = useState([]);
  const [artistEventsLoading, setArtistEventsLoading] = useState(false);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [artistsLoading, setArtistsLoading] = useState(true);
  const [catalogError, setCatalogError] = useState(null);
  const [catalogRetryKey, setCatalogRetryKey] = useState(0);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [success, setSuccess] = useState(false);
  const [successWasIsrael, setSuccessWasIsrael] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadPhase, setUploadPhase] = useState('');
  /** Single mandatory compliance checkbox — label depends on event.country (venue), not artist. */
  const [sellerListingTermsAccepted, setSellerListingTermsAccepted] = useState(
    Boolean(sellDraft?.sellerListingTermsAccepted)
  );
  const [eventRequestOpen, setEventRequestOpen] = useState(false);
  const [eventRequestHint, setEventRequestHint] = useState('');
  const [eventRequestDetails, setEventRequestDetails] = useState('');
  const [eventRequestSubmitting, setEventRequestSubmitting] = useState(false);
  const [eventRequestFeedback, setEventRequestFeedback] = useState(null);
  const submitAttemptedRef = useRef(false);
  /** Full event from GET /events/:id/ — includes venue_detail.sections for seating UI. */
  const [eventDetail, setEventDetail] = useState(null);

  useEffect(() => {
    if (!submitAttemptedRef.current) return;
    if (!error && Object.keys(fieldErrors).length === 0) return;

    window.setTimeout(() => {
      const firstError = document.querySelector(
        '#sell-listing-form .sell-field-error, .sell-listing-card--mobile-cta .error-message'
      );
      firstError?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 60);
  }, [error, fieldErrors]);

  /**
   * IL rules (receipt + price cap + pending approval) use ONLY the event venue country code,
   * never the artist nationality. Taylor Swift in Tel Aviv → IL; Israeli act in NYC → US.
   */
  const isIsraelEvent = (ev) => {
    if (!ev) return false;
    const c = String(ev.country ?? 'IL').trim().toUpperCase();
    return c === '' || c === 'IL';
  };

  const WHATSAPP_SUPPORT_PHONE = '972557214170';
  const missingEventWhatsAppHref = `https://wa.me/${WHATSAPP_SUPPORT_PHONE}?text=${encodeURIComponent(
    'היי TradeTix, אני רוצה למכור כרטיס לאירוע שלא קיים באתר — נא לפרט: שם אמן/קבוצות, תאריך, אולם/עיר.'
  )}`;

  // ALL useEffect HOOKS MUST ALSO BE CALLED BEFORE EARLY RETURNS
  // Parallel fetch: faster Sell page load; backend uses select_related / aggregates for events & artists
  useEffect(() => {
    const { signal, clear, abort } = createListFetchAbort();
    let cancelled = false;
    const load = async () => {
      setArtistsLoading(true);
      setEventsLoading(true);
      setCatalogError(null);
      try {
        const [artRes, evRes] = await Promise.all([
          artistAPI.getArtists({ signal, params: { for_sell: '1' } }),
          eventAPI.getEvents({ signal, params: { for_sell: '1' } }),
        ]);
        let artistsData = [];
        if (artRes.data) {
          if (Array.isArray(artRes.data)) artistsData = artRes.data;
          else if (artRes.data.results && Array.isArray(artRes.data.results)) artistsData = artRes.data.results;
        }
        let eventsData = [];
        if (evRes.data) {
          if (Array.isArray(evRes.data)) eventsData = evRes.data;
          else if (evRes.data.results && Array.isArray(evRes.data.results)) eventsData = evRes.data.results;
        }
        const now = new Date();
        const upcomingEvents = eventsData
          .filter((event) => {
            if (!event.date) return false;
            return new Date(event.date) >= now;
          })
          .sort((a, b) => new Date(a.date) - new Date(b.date));
        artistsData = mergeSellCatalogArtists(artistsData, upcomingEvents);
        if (!cancelled) {
          setArtists(artistsData);
          setEvents(upcomingEvents);
        }
      } catch (err) {
        if (!cancelled) {
          const code = err?.code;
          const aborted =
            code === 'ERR_CANCELED' || err?.name === 'CanceledError' || String(err?.message || '').toLowerCase().includes('canceled');
          setCatalogError(aborted ? 'timeout' : 'error');
          setArtists([]);
          setEvents([]);
          if (!aborted) {
            toastError('לא ניתן לטעון אמנים ואירועים. בדקו את החיבור ונסו שוב.');
          }
        }
      } finally {
        clear();
        if (!cancelled) {
          setArtistsLoading(false);
          setEventsLoading(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
      abort();
      clear();
    };
  }, [catalogRetryKey]);

  // Concerts: ONLY source for dropdown — GET ?for_sell=1&artist=<id>. No extra client filters (date/category) that can drop valid rows.
  useEffect(() => {
    if (selectedCategory !== 'concert' || !selectedArtistId) {
      setArtistEvents([]);
      setArtistEventsLoading(false);
      return undefined;
    }
    const { signal, clear, abort } = createListFetchAbort();
    let cancelled = false;
    setArtistEventsLoading(true);
    setArtistEvents([]);
    (async () => {
      try {
        const evRes = await eventAPI.getEvents({
          signal,
          params: { for_sell: '1', artist: String(selectedArtistId) },
        });
        let eventsData = [];
        if (evRes.data) {
          if (Array.isArray(evRes.data)) eventsData = evRes.data;
          else if (evRes.data.results && Array.isArray(evRes.data.results)) eventsData = evRes.data.results;
        }
        const sorted = [...eventsData].sort((a, b) => {
          const da = a?.date ? new Date(a.date).getTime() : 0;
          const db = b?.date ? new Date(b.date).getTime() : 0;
          return da - db;
        });
        if (!cancelled) {
          setArtistEvents(sorted);
        }
      } catch (err) {
        if (!cancelled) {
          const code = err?.code;
          const aborted =
            code === 'ERR_CANCELED' || err?.name === 'CanceledError' || String(err?.message || '').toLowerCase().includes('canceled');
          setArtistEvents([]);
          if (!aborted) {
            toastError('לא ניתן לטעון אירועים לאמן שנבחר. נסו שוב.');
          }
        }
      } finally {
        clear();
        if (!cancelled) {
          setArtistEventsLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
      abort();
      clear();
    };
  }, [selectedCategory, selectedArtistId, catalogRetryKey]);

  useEffect(() => {
    const id = formData.event_id;
    if (!id) {
      setEventDetail(null);
      return undefined;
    }
    let cancelled = false;
    const { signal, clear, abort } = createListFetchAbort();
    (async () => {
      try {
        const res = await eventAPI.getEvent(id, { signal });
        if (!cancelled && res.data) {
          setEventDetail(res.data);
        }
      } catch (err) {
        const code = err?.code;
        const aborted =
          code === 'ERR_CANCELED' || err?.name === 'CanceledError' || String(err?.message || '').toLowerCase().includes('canceled');
        if (!cancelled && !aborted) {
          setEventDetail(null);
        }
      } finally {
        clear();
      }
    })();
    return () => {
      cancelled = true;
      abort();
      clear();
    };
  }, [formData.event_id]);

  // Helper function to get event display name (handles sports events)
  const getEventDisplayName = (event) => {
    // For sports events with teams, show team matchup
    if ((event.category === 'sport' || event.category === 'ספורט') && event.home_team && event.away_team) {
      const tournamentStr = event.tournament ? ` - ${event.tournament}` : '';
      return `${event.home_team} vs ${event.away_team}${tournamentStr}`;
    }
    // Standard format for all other events
    return event.name || `Event #${event.id}`;
  };

  /** Exactly what the event <select> maps over — concerts use only `artistEvents` from the artist-scoped API. */
  const eventsForDropdown = useMemo(() => {
    if (selectedCategory === 'concert') {
      if (!selectedArtistId || artistEventsLoading) return [];
      return artistEvents;
    }
    return events.filter((event) => {
      const cat = (event.category || '').toLowerCase();
      if (selectedCategory === 'sport') {
        return cat === 'sport' || cat === 'משחקי ספורט' || cat === 'ספורט';
      }
      if (selectedCategory === 'theater') {
        return cat === 'theater' || cat === 'הצגות תיאטרון' || cat === 'הצגה';
      }
      if (selectedCategory === 'festival') {
        return cat === 'festival' || cat === 'פסטיבלים' || cat === 'פסטיבל';
      }
      if (selectedCategory === 'standup') {
        return cat === 'standup' || cat === 'סטנדאפ';
      }
      return false;
    });
  }, [events, artistEvents, artistEventsLoading, selectedCategory, selectedArtistId]);

  useEffect(() => {
    if (!formData.event_id || formData.selectedEvent) return;
    const match = eventsForDropdown.find((ev) => String(ev.id) === String(formData.event_id));
    if (!match) return;
    setFormData((prev) => ({
      ...prev,
      selectedEvent: match,
      event_name: getEventDisplayName(match),
    }));
  }, [formData.event_id, formData.selectedEvent, eventsForDropdown]);

  useEffect(() => {
    const hasMeaningfulDraft = Boolean(
      formData.event_id ||
      formData.section ||
      formData.row ||
      formData.listing_price ||
      selectedArtistId
    );
    if (!hasMeaningfulDraft) {
      writeSellListingDraft(null);
      return;
    }
    writeSellListingDraft(
      buildSellListingDraftSnapshot({
        formData,
        uploadMethod,
        selectedCategory,
        selectedArtistId,
        sellerListingTermsAccepted,
      })
    );
  }, [formData, uploadMethod, selectedCategory, selectedArtistId, sellerListingTermsAccepted]);

  const submitEventRequest = async (e) => {
    e.preventDefault();
    setEventRequestFeedback(null);
    if ((eventRequestDetails || '').trim().length < 8) {
      setEventRequestFeedback({ type: 'error', text: 'נא למלא לפחות כמה מילים עם פרטי האירוע.' });
      return;
    }
    setEventRequestSubmitting(true);
    try {
      await eventRequestAPI.create({
        event_hint: (eventRequestHint || '').trim(),
        details: eventRequestDetails.trim(),
        category: selectedCategory,
      });
      setEventRequestFeedback({ type: 'ok', text: 'הבקשה נשלחה. הצוות יקבל אותה בלוח הבקרה.' });
      setEventRequestHint('');
      setEventRequestDetails('');
    } catch (err) {
      const data = err.response?.data;
      const msg =
        typeof data === 'object' && data !== null
          ? Object.values(data).flat().filter(Boolean).join(' ') || err.message
          : err.message;
      setEventRequestFeedback({ type: 'error', text: msg || 'שגיאה בשליחה. נסו שוב.' });
    } finally {
      setEventRequestSubmitting(false);
    }
  };

  // Initialize ticket_packages array when quantity changes (seat_number only - row is global)
  useEffect(() => {
    const quantity = formData.available_quantity || 1;
    setFormData(prev => {
      if (prev.ticket_packages && prev.ticket_packages.length === quantity) {
        return prev;
      }
      return {
        ...prev,
        ticket_packages: Array(quantity).fill(null).map(() => ({ seat_number: '', pdf_file: null })),
      };
    });
  }, [formData.available_quantity]);

  const sellCurrency = useMemo(() => {
    const ev = formData.selectedEvent;
    if (!ev) return 'ILS';
    if (ev.currency) return String(ev.currency).toUpperCase();
    return iso4217FromCountry(ev.country);
  }, [formData.selectedEvent]);
  const sellSym = currencySymbol(sellCurrency);

  const sectionOptions = useMemo(() => {
    const selectedEventId = formData.event_id ? String(formData.event_id) : '';
    const detailMatchesSelection = eventDetail && String(eventDetail.id) === selectedEventId;
    const eventForSections = detailMatchesSelection ? eventDetail : formData.selectedEvent;
    const venueDetail = eventForSections?.venue_detail;
    const structured = venueDetail?.sections;
    const concertLayout = isBloomfieldConcertEvent(eventForSections);
    const staticFallback = generatedSectionOptionsForVenue(canonicalVenueName(eventForSections || {}));

    if (Array.isArray(structured) && structured.length > 0) {
      const selectedVenueId = venueDetail?.id ? String(venueDetail.id) : '';
      const concertNameSet = concertLayout ? new Set(CONCERT_SECTION_NAMES) : null;
      return [...structured]
        .filter((section) => !selectedVenueId || String(section.venue_id || selectedVenueId) === selectedVenueId)
        .filter((section) => {
          if (!concertNameSet) return true;
          return concertNameSet.has(String(section.name || '').trim());
        })
        .sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'he', { numeric: true }))
        .map((section) => ({
          value: String(section.id),
          label: `גוש ${section.name}`,
          structured: true,
          venueId: venueDetail?.id ? String(venueDetail.id) : '',
        }));
    }

    if (staticFallback.length > 0) {
      return staticFallback;
    }

    // Venue exists in DB but sections not seeded yet — wait only if no static map exists
    if (venueDetail?.id && selectedEventId && !detailMatchesSelection) {
      return [];
    }
    return [];
  }, [eventDetail, formData.event_id, formData.selectedEvent]);

  const sectionsStillLoading = useMemo(() => {
    if (!formData.event_id) return false;
    if (sectionOptions.length > 0) return false;
    const selectedEventId = String(formData.event_id);
    const detailMatchesSelection = eventDetail && String(eventDetail.id) === selectedEventId;
    if (detailMatchesSelection) return false;
    const eventForSections = formData.selectedEvent;
    const staticFallback = generatedSectionOptionsForVenue(canonicalVenueName(eventForSections || {}));
    return staticFallback.length === 0;
  }, [formData.event_id, formData.selectedEvent, eventDetail, sectionOptions.length]);

  const selectedVenueLabel = canonicalVenueName(
    eventDetail && String(eventDetail.id) === String(formData.event_id)
      ? eventDetail
      : formData.selectedEvent || {}
  );

  // NOW ALL EARLY RETURNS CAN HAPPEN AFTER ALL HOOKS
  // Wait for auth to finish loading
  if (authLoading) {
    return (
      <div className="sell-container">
        <div className="listing-card">
          <p>טוען...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="sell-container">
        <InlineAuthFunnel onAuthed={refreshProfile} />
      </div>
    );
  }

  if (user.role !== 'seller') {
    return (
      <div className="sell-container">
        <InlineBecomeSellerSection onSuccess={refreshProfile} />
      </div>
    );
  }

  const handleCategoryChange = (e) => {
    const newCategory = e.target.value;
    setSelectedCategory(newCategory);
    setSelectedArtistId(''); // Reset artist when category changes
    setEventDetail(null);
    setFormData({
      ...formData,
      event_id: '', // Reset event when category changes
      event_name: '',
      selectedEvent: null,
      section: '',
    });
    setSellerListingTermsAccepted(false);
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.event;
      return next;
    });
  };

  const handleArtistChange = (e) => {
    const artistId = e.target.value;
    setSelectedArtistId(artistId);
    setArtistEvents([]);
    setEventDetail(null);
    setFormData({
      ...formData,
      event_id: '', // Reset event when artist changes
      event_name: '',
      selectedEvent: null,
      section: '',
    });
    setSellerListingTermsAccepted(false);
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.event;
      return next;
    });
  };

  const handleEventChange = (e) => {
    const eventId = e.target.value;
    setEventDetail(null);
    if (!eventId) {
      setFormData({
        ...formData,
        event_id: '',
        event_name: '',
        selectedEvent: null,
        section: '',
        listing_price: '',
      });
      setSellerListingTermsAccepted(false);
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next.event;
        return next;
      });
      return;
    }
    
    // Must use same pool as the dropdown (server-scoped concerts vs global events list)
    const selectedEvent = eventsForDropdown.find((ev) => String(ev.id) === String(eventId));
    if (selectedEvent) {
      const displayName = getEventDisplayName(selectedEvent);
      setFormData({
        ...formData,
        event_id: selectedEvent.id,
        event_name: displayName,
        selectedEvent: selectedEvent,
        section: '',
        listing_price: '',
      });
      setSellerListingTermsAccepted(false);
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next.event;
        return next;
      });
    }
  };

  const handleChange = (e) => {
    const { name, value, files, type, checked } = e.target;
    
    if (name === 'pdf_files') {
      // Handle multiple ticket file uploads - one per ticket
      if (files && files.length > 0) {
        const fileArray = Array.from(files);

        const fileError = validateTicketFiles(fileArray);
        if (fileError) {
          setFieldErrors((prev) => ({ ...prev, upload_packages: fileError }));
          toastError(fileError);
          return;
        }

        // Validate number of files matches quantity
        const requiredCount = formData.available_quantity || 1;
        if (fileArray.length !== requiredCount) {
          setFieldErrors((prev) => ({
            ...prev,
            upload_packages: `נדרשים בדיוק ${requiredCount} קבצים (אחד לכל כרטיס). העלית ${fileArray.length} קבצים.`,
          }));
          toastError(`נדרשים בדיוק ${requiredCount} קבצים (אחד לכל כרטיס).`);
          return;
        }

        setFormData({
          ...formData,
          pdf_files: fileArray,
        });
        setFieldErrors((prev) => {
          const next = { ...prev };
          delete next.upload_packages;
          delete next.upload_mode;
          return next;
        });
        setError('');
      }
    } else if (name === 'single_multi_page_pdf') {
      // Single file: multi-page PDF auto-split when quantity > 1; otherwise PDF or image OK
      if (files && files.length > 0) {
        const file = files[0];
        const qty = formData.available_quantity || 1;
        const fileError = ticketFileValidationError(file, { requirePdf: qty > 1 });
        if (fileError) {
          setFieldErrors((prev) => ({ ...prev, upload_single: fileError }));
          toastError(fileError);
          return;
        }
        setFormData((prev) => ({
          ...prev,
          singleMultiPagePdf: file,
          ticket_packages: (prev.ticket_packages || []).map((pkg) => ({ ...pkg, pdf_file: null })),
        }));
        setFieldErrors((prev) => {
          const next = { ...prev };
          delete next.upload_single;
          delete next.upload_mode;
          return next;
        });
        setError('');
      }
    } else if (name && name.startsWith('pdf_file_package_')) {
      // Handle individual package PDF file uploads (uploadMethod === 'separate_files')
      const index = parseInt(name.replace('pdf_file_package_', ''), 10);
      if (!isNaN(index) && files && files.length > 0) {
        const file = files[0];
        const fileError = ticketFileValidationError(file);
        if (fileError) {
          setFieldErrors((prev) => ({ ...prev, upload_packages: fileError }));
          toastError(fileError);
          return;
        }
        // Always use functional updates so ticket_packages is never copied from a stale closure.
        setFormData((prev) => {
          const newPackages = [...(prev.ticket_packages || [])];
          const cur = newPackages[index] || { seat_number: '', pdf_file: null };
          newPackages[index] = { ...cur, pdf_file: file };
          return { ...prev, ticket_packages: newPackages, singleMultiPagePdf: null };
        });
        setFieldErrors((prev) => {
          const next = { ...prev };
          delete next.upload_packages;
          delete next.upload_mode;
          return next;
        });
        setError('');
      }
    } else if (name && name.startsWith('seat_number_pkg_')) {
      const index = parseInt(name.replace('seat_number_pkg_', ''), 10);
      if (!isNaN(index)) {
        setFormData((prev) => {
          const newPackages = [...(prev.ticket_packages || [])];
          const cur = newPackages[index] || { seat_number: '', pdf_file: null };
          newPackages[index] = { ...cur, seat_number: value };
          return { ...prev, ticket_packages: newPackages };
        });
        setFieldErrors((prev) => {
          if (!prev.seats) return prev;
          const n = { ...prev };
          delete n.seats;
          return n;
        });
      }
    } else if (name === 'start_seat') {
      // Handle start seat input - auto-generate seat numbers
      setFormData({
        ...formData,
        [name]: value,
      });
      setFieldErrors((prev) => {
        if (!prev.start_seat) return prev;
        const n = { ...prev };
        delete n.start_seat;
        return n;
      });
    } else if (type === 'checkbox') {
      setFormData({
        ...formData,
        [name]: Boolean(checked),
      });
    } else if (name === 'listing_price') {
      setFormData({ ...formData, listing_price: value });
      setFieldErrors((prev) => {
        if (!prev.listing_price) return prev;
        const n = { ...prev };
        delete n.listing_price;
        return n;
      });
    } else {
      setFormData({
        ...formData,
        [name]: value,
      });
      setFieldErrors((prev) => {
        if (!prev[name]) return prev;
        const n = { ...prev };
        delete n[name];
        return n;
      });
    }

  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    submitAttemptedRef.current = true;
    setError('');
    setFieldErrors({});
    setSuccess(false);
    setUploadProgress(5);
    setUploadPhase('בודק את פרטי הכרטיס והקבצים...');
    setLoading(true);
    let progressTimer = null;

    if (!sellerListingTermsAccepted) {
      setFieldErrors({ terms: 'יש לאשר את תנאי ההצהרה כדי להמשיך' });
      setLoading(false);
      return;
    }

    // Validate required fields
    if (!formData.event_id) {
      setFieldErrors({ event: 'אנא בחר אירוע מהרשימה.' });
      setLoading(false);
      return;
    }

    const ilEvent = isIsraelEvent(formData.selectedEvent);
    if (formData.listing_price === '' || formData.listing_price == null) {
      setFieldErrors({ listing_price: 'נא להזין מחיר מכירה.' });
      setLoading(false);
      return;
    }
    const askVal = parseFloat(String(formData.listing_price).replace(',', '.'));
    if (!Number.isFinite(askVal) || askVal <= 0) {
      setFieldErrors({ listing_price: 'מחיר המכירה חייב להיות מספר חיובי.' });
      setLoading(false);
      return;
    }

    // Validate ticket packages — seating + files (hybrid: structured section id or free-text גוש)
    const requiredCount = formData.available_quantity || 1;

    // Ensure ticket_packages array is initialized
    if (!formData.ticket_packages || formData.ticket_packages.length !== requiredCount) {
      setFieldErrors({ packages: `אנא השלם את כל פרטי הכרטיסים (${requiredCount} כרטיסים נדרשים).` });
      setLoading(false);
      return;
    }

    const secValStrict = (formData.section || '').trim();
    if (!secValStrict) {
      setFieldErrors({ section: 'נא לבחור גוש מהרשימה.' });
      setLoading(false);
      return;
    }
    if (!(formData.row || '').trim()) {
      setFieldErrors({ row: 'נא להזין שורה.' });
      setLoading(false);
      return;
    }
    const incompleteSeats = formData.ticket_packages.some(
      (pkg) => !pkg || !(pkg.seat_number || '').trim()
    );
    if (incompleteSeats) {
      setFieldErrors({ seats: 'נא להזין מספר כיסא לכל כרטיס.' });
      setLoading(false);
      return;
    }

    const useSingleFile = uploadMethod === 'single_file' && formData.singleMultiPagePdf && requiredCount >= 1;
    const useSeparateFiles = uploadMethod === 'separate_files';

    if (requiredCount > 1) {
      if (useSingleFile) {
        const singleFileError = ticketFileValidationError(formData.singleMultiPagePdf, { requirePdf: true });
        if (singleFileError) {
          setFieldErrors({ upload_single: singleFileError });
          setLoading(false);
          return;
        }
      } else if (useSeparateFiles) {
        const incompletePackages = formData.ticket_packages.some((pkg) => !pkg || !pkg.pdf_file);
        if (incompletePackages) {
          setFieldErrors({
            upload_packages: 'כל כרטיס חייב לכלול קובץ כרטיס (PDF או תמונה) ייחודי. אנא השלם את כל הפרטים.',
          });
          setLoading(false);
          return;
        }
        const pdfFiles = formData.ticket_packages.map((p) => p?.pdf_file).filter(Boolean);
        const uniquePdfs = new Set(pdfFiles.map((f) => f.name));
        if (uniquePdfs.size !== pdfFiles.length) {
          setFieldErrors({
            upload_packages: 'כל כרטיס חייב להיות עם קובץ ייחודי. לא ניתן להשתמש באותו קובץ פעמיים.',
          });
          setLoading(false);
          return;
        }
        const invalidFiles = pdfFiles.filter((f) => !isTicketAttachmentFile(f));
        const fileError = validateTicketFiles(pdfFiles);
        if (invalidFiles.length > 0 || fileError) {
          setFieldErrors({
            upload_packages: fileError || 'נא להעלות לכל כרטיס קובץ PDF או תמונה (JPG, PNG).',
          });
          setLoading(false);
          return;
        }
      } else {
        setFieldErrors({
          upload_mode:
            uploadMethod === 'single_file'
              ? 'אנא העלה קובץ PDF אחד המכיל את כל הכרטיסים.'
              : 'אנא העלה קובץ (PDF או תמונה) לכל כרטיס.',
        });
        setLoading(false);
        return;
      }
    } else {
      // Single ticket (quantity === 1)
      if (useSeparateFiles) {
        if (!formData.ticket_packages?.[0]?.pdf_file) {
          setFieldErrors({ upload_packages: 'אנא העלה קובץ כרטיס (PDF או תמונה).' });
          setLoading(false);
          return;
        }
        const pdfFile = formData.ticket_packages[0].pdf_file;
        const fileError = ticketFileValidationError(pdfFile);
        if (fileError) {
          setFieldErrors({ upload_packages: fileError });
          setLoading(false);
          return;
        }
      } else if (useSingleFile) {
        if (!formData.singleMultiPagePdf) {
          setFieldErrors({ upload_single: 'אנא העלה קובץ כרטיס (PDF או תמונה).' });
          setLoading(false);
          return;
        }
        const fileError = ticketFileValidationError(formData.singleMultiPagePdf);
        if (fileError) {
          setFieldErrors({ upload_single: fileError });
          setLoading(false);
          return;
        }
      } else {
        setFieldErrors({ upload_mode: 'אנא העלה קובץ כרטיס (PDF או תמונה).' });
        setLoading(false);
        return;
      }
    }

    setUploadProgress(30);
    setUploadPhase('מכין את הקבצים להעלאה...');

    // Create FormData for file upload — never append undefined/null as values (multipart-safe scalars).
    const fdText = (v) => (v === undefined || v === null ? '' : String(v));
    const qtyNum = Math.max(1, Math.min(10, parseInt(String(formData.available_quantity ?? 1), 10) || 1));
    const listingPriceNum = Math.max(
      0,
      parseFloat(String(formData.listing_price ?? '').replace(',', '.')) || 0
    );
    const listingPriceStr = fdText(listingPriceNum);

    const submitData = new FormData();
    submitData.append('event_id', fdText(formData.event_id));
    const evNameTrim = fdText(formData.event_name).trim();
    if (evNameTrim) {
      submitData.append('event_name', evNameTrim);
    }
    submitData.append('seat_row', fdText(formData.seat_row)); // Legacy field
    const secVal = (formData.section || '').trim();
    const selectedSection = sectionOptions.find((option) => String(option.value) === String(secVal));
    if (selectedSection?.structured && secVal) {
      submitData.append('venue_section', fdText(secVal));
    } else if (secVal) {
      submitData.append('custom_section_text', fdText(secVal));
    }
    submitData.append('row', fdText(formData.row));
    submitData.append('original_price', listingPriceStr);
    const askForApi = String(Math.max(0, Math.round(listingPriceNum)));
    submitData.append('listing_price', fdText(askForApi));
    if (ilEvent) {
      submitData.append('il_legal_declaration', 'true');
    }
    submitData.append('delivery_method', 'instant');
    submitData.append('available_quantity', fdText(qtyNum));
    submitData.append('is_together', formData.is_together ? 'true' : 'false');
    // Master Architecture fields
    submitData.append('ticket_type', 'כרטיס אלקטרוני (PDF או תמונה)');
    submitData.append('split_type', fdText(formData.split_type || 'כל כמות'));
    // Multipart: send explicit boolean strings (avoid FormData coercing booleans oddly).
    submitData.append('is_obstructed_view', formData.is_obstructed_view ? 'true' : 'false');
    
    const packages = formData.ticket_packages || [];
    const globalRow = formData.row || '';

    if (useSingleFile) {
      // Single PDF auto-split: backend receives pdf_file_0, pdf_files_count=1
      const pdf0 = formData.singleMultiPagePdf;
      if (!(pdf0 instanceof File) && !(pdf0 instanceof Blob)) {
        setFieldErrors({ upload_single: 'שגיאה פנימית: קובץ כרטיס חסר. נסו לבחור את הקובץ שוב.' });
        setLoading(false);
        return;
      }
      const fname0 = pdf0 instanceof File ? pdf0.name : 'ticket.pdf';
      submitData.append('pdf_files_count', '1');
      submitData.append('pdf_file_0', pdf0, fname0);
      packages.forEach((pkg, index) => {
        submitData.append(`row_number_${index}`, fdText(globalRow));
        submitData.append(`seat_number_${index}`, fdText(pkg?.seat_number));
      });
    } else {
      // Separate files: each ticket gets its own PDF (third arg = filename; required by some stacks)
      packages.forEach((pkg, index) => {
        if (pkg?.pdf_file) {
          const f = pkg.pdf_file;
          const fn = f instanceof File ? f.name : `ticket_${index}.pdf`;
          submitData.append(`pdf_file_${index}`, f, fn);
        }
        submitData.append(`row_number_${index}`, fdText(globalRow));
        submitData.append(`seat_number_${index}`, fdText(pkg?.seat_number));
      });
      submitData.append('pdf_files_count', fdText(packages.length));
    }

    try {
      setUploadProgress(55);
      setUploadPhase('מעלה את הכרטיסים לאימות מאובטח...');
      progressTimer = window.setInterval(() => {
        setUploadProgress((prev) => Math.min(90, prev + 4));
      }, 700);
      await ticketAPI.createTicket(submitData);
      setUploadProgress(100);
      setUploadPhase('הכרטיסים נשמרו בהצלחה.');
      submitAttemptedRef.current = false;
      setSuccessWasIsrael(ilEvent);
      writeSellListingDraft(null);
      setSuccess(true);
    } catch (err) {
      const raw = `${err?.message || ''} ${JSON.stringify(err?.response?.data || {})}`;
      const errorMessage = /cloudinary|storage|upload|media/i.test(raw)
        ? 'העלאת הקובץ נכשלה מול שירות האחסון. בדקו שהקובץ תקין ועד 5MB ונסו שוב בעוד רגע.'
        : apiErrorMessageHe(err, 'יצירת רשימת הכרטיס נכשלה. אנא נסה שוב.');
      setFieldErrors({});
      setError(errorMessage);
      toastError(errorMessage);
    } finally {
      if (progressTimer != null) window.clearInterval(progressTimer);
      setLoading(false);
      setUploadProgress(0);
      setUploadPhase('');
    }
  };

  if (success) {
    return (
      <div className="sell-container">
        <div className="listing-card success-message">
          <div className="success-icon-large">✓</div>
          <h2 className="success-title">Listing Created Successfully!</h2>
          <h3 className="success-subtitle-hebrew">הכרטיס הועלה בהצלחה!</h3>
          {successWasIsrael ? (
            <p className="success-text">
              הכרטיס הועלה בהצלחה! הוא יפורסם באתר לאחר בדיקת צוות קצרה (עד 24 שעות).
            </p>
          ) : (
            <p className="success-text">הכרטיס פורסם באתר וזמין למכירה.</p>
          )}
          <p className="success-redirect-text">מעבר לדף הבית...</p>
        </div>
      </div>
    );
  }

  const ilSelected = isIsraelEvent(formData.selectedEvent);
  const feeBasis = parseFloat(String(formData.listing_price || 0)) || 0;

  return (
    <div className="sell-container">
      {loading && (
        <div className="sell-upload-overlay" role="status" aria-live="polite" aria-busy="true">
          <div className="sell-upload-overlay-card">
            <div className="sell-upload-spinner" aria-hidden />
            <p className="sell-upload-overlay-title">מעלה את הכרטיס...</p>
            <p className="sell-upload-overlay-hint">נא להמתין — אל תסגרו את הדף</p>
            <p className="sell-upload-overlay-phase">{uploadPhase || 'מכין העלאה מאובטחת...'}</p>
            <div
              className="sell-upload-progress-track"
              role="progressbar"
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={Math.max(0, Math.min(100, uploadProgress))}
            >
              <div
                className="sell-upload-progress-bar sell-upload-progress-bar--determinate"
                style={{ width: `${Math.max(8, Math.min(100, uploadProgress || 8))}%` }}
              />
            </div>
          </div>
        </div>
      )}
      <div className="listing-card sell-form-compact sell-listing-card--mobile-cta">
        <div className="listing-card-header">
          <div className="secure-listing-header">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10 1L3 4V9C3 13.55 6.16 17.74 10 19C13.84 17.74 17 13.55 17 9V4L10 1Z" fill="currentColor"/>
              <path d="M8 9L9 10L12 7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <h2>תהליך הצעת כרטיס מאובטח</h2>
          </div>
          <p className="listing-subtitle">הצע את הכרטיס שלך בצורה בטוחה ומאובטחת</p>
          <p className="listing-build-id" dir="ltr" style={{ fontSize: '0.72rem', opacity: 0.75, marginTop: '0.35rem' }}>
            Frontend build: {SELL_PAGE_BUILD_TAG}
          </p>
        </div>
        {error && <div className="error-message">{error}</div>}
        {Object.keys(fieldErrors).length > 0 && (
          <div className="error-message sell-validation-summary" role="alert">
            יש שדות שדורשים תיקון לפני פרסום הכרטיס. גללו לשדה המסומן ונסו שוב.
          </div>
        )}
        
        <form id="sell-listing-form" onSubmit={handleSubmit} noValidate>
          {catalogError && (
            <div className="catalog-error-banner" role="alert">
              <p>
                {catalogError === 'timeout'
                  ? 'הטעינה ארכה יותר מדי. לחצו לנסות שוב (השרת אולי מתעורר ממצב שינה).'
                  : 'לא ניתן לטעון את רשימת האירועים. בדקו חיבור ונסו שוב.'}
              </p>
              <button type="button" className="catalog-retry-btn" onClick={() => setCatalogRetryKey((k) => k + 1)}>
                נסה שוב
              </button>
            </div>
          )}
          {/* Step 1: Category Selection */}
          <div className="form-group">
            <label htmlFor="category_select">סוג אירוע *</label>
            <select
              id="category_select"
              name="category_select"
              value={selectedCategory}
              onChange={handleCategoryChange}
              className="premium-select"
              required
            >
              <option value="concert">הופעות</option>
              <option value="sport">משחקי ספורט</option>
              <option value="theater">הצגות תיאטרון</option>
              <option value="festival">פסטיבלים</option>
              <option value="standup">סטנדאפ</option>
            </select>
          </div>

          {selectedCategory === 'concert' && artistsLoading && eventsLoading ? (
            <div className="form-group">
              <label>טוען אמנים ואירועים…</label>
              <SellFormSkeleton />
            </div>
          ) : (
            <>
              {/* Step 2: Artist Selection (ONLY for concerts) */}
              {selectedCategory === 'concert' && (
                <div className="form-group">
                  <label htmlFor="artist_select">בחר אמן *</label>
                  {artistsLoading ? (
                    <SellFormSkeleton />
                  ) : (
                    <select
                      id="artist_select"
                      name="artist_select"
                      value={selectedArtistId}
                      onChange={handleArtistChange}
                      className="premium-select"
                      required
                    >
                      <option value="">-- בחר אמן --</option>
                      {artists.map((artist) => (
                        <option key={artist.id} value={String(artist.id)}>
                          {artist.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              )}

              {/* Step 3: Event Selection */}
              <div className="form-group">
                <label htmlFor="event_select">בחר אירוע *</label>
                {eventsLoading ||
                (selectedCategory === 'concert' && selectedArtistId && artistEventsLoading) ? (
                  <SellFormSkeleton />
                ) : (
                  <select
                    id="event_select"
                    name="event_select"
                    value={formData.event_id ? String(formData.event_id) : ''}
                    onChange={handleEventChange}
                    className="premium-select"
                    required
                    disabled={
                      selectedCategory === 'concert' && (!selectedArtistId || artistEventsLoading)
                    }
                  >
                    <option value="">-- בחר אירוע --</option>
                    {eventsForDropdown.map((event) => (
                      <option key={event.id} value={String(event.id)}>
                        {formatEventDropdownLabel(event)}
                      </option>
                    ))}
                  </select>
                )}
                {selectedCategory === 'concert' && !selectedArtistId && (
                  <small className="field-hint">אנא בחר אמן תחילה</small>
                )}
                <SellFieldError message={fieldErrors.event} />
              </div>

              {formData.selectedEvent ? (
                <div className="selected-event-summary" role="status" aria-live="polite">
                  <div>
                    <strong>{getEventDisplayName(formData.selectedEvent)}</strong>
                    <span>
                      {formatEventLocation(formData.selectedEvent)} ·{' '}
                      {sectionOptions.length > 0
                        ? isBloomfieldConcertEvent(formData.selectedEvent)
                          ? `${CONCERT_BLOCK_COUNT} גושים בפריסת הופעה (${sectionOptions.length} זמינים לבחירה)`
                          : `${sectionOptions.length} גושים זמינים לבחירה`
                        : sectionsStillLoading
                          ? 'טוען גושים לאולם'
                          : 'לא נמצאו גושים לאולם זה'}
                    </span>
                  </div>
                </div>
              ) : null}

              {!formData.selectedEvent ? (
              <div className="missing-event-banner" role="region" aria-label="בקשה להוספת אירוע">
                <div className="missing-event-banner-text">
                  <strong>לא מצאת את ההופעה או המשחק שלך?</strong>
                  <span>ספרו לנו באיזה אירוע מדובר — נוסיף אותו לקטלוג כשאפשר.</span>
                </div>
                <div className="missing-event-banner-actions">
                  <button
                    type="button"
                    className="missing-event-primary-btn"
                    onClick={() => {
                      setEventRequestOpen(true);
                      setEventRequestFeedback(null);
                    }}
                  >
                    שליחת בקשה מהירה
                  </button>
                  <a
                    className="missing-event-whatsapp-link"
                    href={missingEventWhatsAppHref}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    WhatsApp (הודעה מוכנה)
                  </a>
                </div>
              </div>
              ) : null}
              {!formData.selectedEvent && eventRequestOpen ? (
                <div className="event-request-inline-panel">
                  <h3>בקשה להוספת אירוע</h3>
                  <p className="event-request-modal-lead">
                    נתאר בקצרה את האירוע החסר. צוות TradeTix יעדכן את הקטלוג כשהפרטים מאומתים.
                  </p>
                  <form onSubmit={submitEventRequest}>
                    <div className="form-group">
                      <label htmlFor="event_request_hint">שם אמן / קבוצות / כותרת (אופציונלי)</label>
                      <input
                        id="event_request_hint"
                        type="text"
                        value={eventRequestHint}
                        onChange={(e) => setEventRequestHint(e.target.value)}
                        placeholder="לדוגמה: הפועל ת״א נגד בי״ס"
                        className="premium-select"
                        style={{ width: '100%', padding: '0.65rem' }}
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="event_request_details">פרטים * (תאריך, עיר, אולם…)</label>
                      <textarea
                        id="event_request_details"
                        value={eventRequestDetails}
                        onChange={(e) => setEventRequestDetails(e.target.value)}
                        required
                        rows={4}
                        placeholder="ככל שתפרטו יותר — נוכל להוסיף מהר יותר."
                        className="premium-select"
                        style={{ width: '100%', padding: '0.65rem', resize: 'vertical' }}
                      />
                      {eventRequestFeedback?.type === 'error' ? (
                        <SellFieldError message={eventRequestFeedback.text} />
                      ) : null}
                    </div>
                    {eventRequestFeedback?.type === 'ok' ? (
                      <p className="event-request-feedback ok" role="status">
                        {eventRequestFeedback.text}
                      </p>
                    ) : null}
                    <div className="event-request-inline-actions">
                      <button type="button" className="missing-event-whatsapp-link" disabled={eventRequestSubmitting} onClick={() => setEventRequestOpen(false)}>
                        סגירה
                      </button>
                      <button type="submit" className="missing-event-primary-btn" disabled={eventRequestSubmitting}>
                        {eventRequestSubmitting ? 'שולח…' : 'שליחה'}
                      </button>
                    </div>
                  </form>
                </div>
              ) : null}
            </>
          )}

          <div className="form-group">
            <label htmlFor="available_quantity">כמה כרטיסים ברצונך למכור? *</label>
            <select
              id="available_quantity"
              name="available_quantity"
              value={formData.available_quantity}
              onChange={(e) => {
                const newQuantity = parseInt(e.target.value, 10);
                handleChange(e);
                // Clear ticket packages when quantity changes - user must re-enter
                if (newQuantity !== formData.available_quantity) {
                  if (newQuantity === 1) {
                    setUploadMethod('single_file');
                  }
                  setFormData((prev) => ({
                    ...prev,
                    available_quantity: newQuantity,
                    ticket_packages: Array(newQuantity).fill(null).map(() => ({ seat_number: '', pdf_file: null })),
                    singleMultiPagePdf: null,
                    start_seat: '',
                  }));
                  setFieldErrors((prev) => {
                    const next = { ...prev };
                    delete next.packages;
                    delete next.seats;
                    delete next.upload_packages;
                    delete next.upload_single;
                    delete next.upload_mode;
                    return next;
                  });
                  setError('');
                }
              }}
              required
              className="quantity-select"
            >
              {Array.from({ length: 10 }, (_, i) => i + 1).map((num) => (
                <option key={num} value={num}>
                  {num} {num === 1 ? 'כרטיס' : 'כרטיסים'}
                </option>
              ))}
            </select>
            <small>בחר את מספר הכרטיסים שברצונך למכור (1-10).</small>
          </div>

          {/* Seating + optional auto seat numbers (single compact section) */}
          <div className="seating-and-seats-compact">
            <h3 className="seating-section-title">פרטי ישיבה ומושבים</h3>
            <small className="section-hint">
              גוש, שורה ומספר כיסא נדרשים לכל רשימה. גוש ושורה משותפים לכל הכרטיסים; כיסא לכל כרטיס למטה. ניתן למלא רצף מושבים אוטומטית כשמוכרים יותר מכרטיס אחד.
            </small>
            <div className="form-row seating-row-compact">
              <div className="form-group">
                <label htmlFor="section">גוש *</label>
                <select
                  id="section"
                  name="section"
                  value={formData.section}
                  onChange={handleChange}
                  className="section-dropdown premium-select"
                  required
                  disabled={!formData.event_id || sectionOptions.length === 0 || sectionsStillLoading}
                >
                  <option value="">
                    {!formData.event_id
                      ? 'בחרו אירוע תחילה'
                      : sectionOptions.length === 0
                        ? 'לא נמצאו גושים לאולם זה'
                        : 'בחר גוש / אזור'}
                  </option>
                  {sectionOptions.map((section) => (
                    <option key={`${section.structured ? 'vs' : 'custom'}-${section.value}`} value={section.value}>
                      {section.label}
                    </option>
                  ))}
                </select>
                {formData.event_id && sectionOptions.length > 0 ? (
                  <small className="field-hint">
                    מוצגים רק הגושים התקינים לאולם שנבחר.
                  </small>
                ) : null}
                <SellFieldError message={fieldErrors.section} />
              </div>
              <div className="form-group">
                <label htmlFor="row">שורה *</label>
                <input
                  type="text"
                  id="row"
                  name="row"
                  value={formData.row}
                  onChange={handleChange}
                  placeholder="לדוגמה: 5"
                  required
                  inputMode="numeric"
                  autoComplete="off"
                />
                <SellFieldError message={fieldErrors.row} />
              </div>
            </div>
            {formData.available_quantity > 1 && (
              <div className="auto-seat-inline">
                <div className="form-row auto-seat-row">
                  <div className="form-group">
                    <label htmlFor="start_seat">מושב התחלה (מלאה אוטומטית)</label>
                    <input
                      type="number"
                      id="start_seat"
                      name="start_seat"
                      value={formData.start_seat || ''}
                      onChange={handleChange}
                      placeholder="לדוגמה: 1"
                      min="1"
                      inputMode="numeric"
                    />
                  </div>
                  <div className="form-group auto-seat-btn-wrap">
                    <span className="auto-seat-btn-label" aria-hidden="true">
                      &nbsp;
                    </span>
                    <button
                      type="button"
                      className="auto-fill-btn"
                      onClick={() => {
                        const startSeat = parseInt(formData.start_seat, 10);
                        const quantity = formData.available_quantity || 1;
                        if (!startSeat || isNaN(startSeat)) {
                          setFieldErrors((prev) => ({ ...prev, start_seat: 'אנא הזן מושב התחלה.' }));
                          return;
                        }
                        const newPackages = Array.from({ length: quantity }, (_, i) => {
                          const existing = formData.ticket_packages[i] || { seat_number: '', pdf_file: null };
                          return { ...existing, seat_number: String(startSeat + i) };
                        });
                        setFormData((prev) => ({ ...prev, ticket_packages: newPackages }));
                        setFieldErrors((prev) => {
                          const next = { ...prev };
                          delete next.start_seat;
                          delete next.seats;
                          return next;
                        });
                      }}
                    >
                      צור מספרי מושבים
                    </button>
                  </div>
                </div>
                <SellFieldError message={fieldErrors.start_seat} />
                <small className="auto-seat-range-hint">
                  ימלא כיסאות {formData.start_seat || 'X'} עד{' '}
                  {formData.start_seat
                    ? parseInt(formData.start_seat, 10) + (formData.available_quantity || 1) - 1
                    : '?'}
                </small>
              </div>
            )}
          </div>

          {formData.available_quantity > 1 ? (
          <div className="form-group pdf-upload-toggle-section">
            <label>אופן העלאת קבצי הכרטיס</label>
            <div className="upload-method-options" role="radiogroup" aria-label="אופן העלאת קבצי הכרטיס">
              <div
                role="radio"
                aria-checked={uploadMethod === 'single_file'}
                tabIndex={0}
                className={`upload-method-option ${uploadMethod === 'single_file' ? 'selected' : ''}`}
                onClick={() => {
                  setUploadMethod('single_file');
                  setFormData((prev) => ({
                    ...prev,
                    ticket_packages: (prev.ticket_packages || []).map((p) => ({ ...p, pdf_file: null })),
                  }));
                  setFieldErrors((prev) => {
                    const next = { ...prev };
                    delete next.upload_mode;
                    delete next.upload_packages;
                    return next;
                  });
                  setError('');
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    e.currentTarget.click();
                  }
                }}
              >
                <div className="option-content">
                  <span className="option-title">קובץ PDF אחד המכיל את כל הכרטיסים (אנו נטפל בפיצול)</span>
                  <span className="option-desc">העלה קובץ PDF עם עמוד נפרד לכל כרטיס – המערכת תפצל אוטומטית</span>
                </div>
              </div>
              <div
                role="radio"
                aria-checked={uploadMethod === 'separate_files'}
                tabIndex={0}
                className={`upload-method-option ${uploadMethod === 'separate_files' ? 'selected' : ''}`}
                onClick={() => {
                  setUploadMethod('separate_files');
                  setFormData((prev) => ({ ...prev, singleMultiPagePdf: null }));
                  setFieldErrors((prev) => {
                    const next = { ...prev };
                    delete next.upload_mode;
                    delete next.upload_single;
                    return next;
                  });
                  setError('');
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    e.currentTarget.click();
                  }
                }}
              >
                <div className="option-content">
                  <span className="option-title">קובץ נפרד לכל כרטיס (PDF או תמונה)</span>
                  <span className="option-desc">העלה קובץ ייחודי (PDF, JPG, PNG) לכל כרטיס</span>
                </div>
              </div>
            </div>
            <div className="upload-constraints-card" role="note">
              <strong>הנחיות לקובץ הכרטיס</strong>
              <span>{TICKET_FILE_CONSTRAINTS_HE}</span>
              <span>
                לכמה כרטיסים בקובץ יחיד: העלו PDF מרובה עמודים, עמוד אחד לכל כרטיס. תמונות מתאימות רק במצב קובץ נפרד לכל כרטיס.
              </span>
            </div>
            <SellFieldError message={fieldErrors.upload_mode} />
          </div>
          ) : (
            <div className="upload-constraints-card upload-constraints-card--compact" role="note">
              <span>{TICKET_FILE_CONSTRAINTS_HE}</span>
            </div>
          )}

          {/* Single file dropzone (Option A) */}
          {uploadMethod === 'single_file' && (
            <div className="form-group single-pdf-dropzone">
              <label htmlFor="single_multi_page_pdf">קובץ כרטיס (PDF או תמונה) *</label>
              <div className="file-dropzone-box">
                <input
                  type="file"
                  id="single_multi_page_pdf"
                  name="single_multi_page_pdf"
                  onChange={handleChange}
                  accept={TICKET_FILE_INPUT_ACCEPT}
                />
                {formData.singleMultiPagePdf ? (
                  <>
                    <TicketAttachmentPreview file={formData.singleMultiPagePdf} />
                    <span className="uploaded-file-name">✓ {formData.singleMultiPagePdf.name}</span>
                  </>
                ) : (
                  <span className="dropzone-placeholder">
                    {formData.available_quantity > 1
                      ? `העלה קובץ PDF עם ${formData.available_quantity} עמודים (עמוד לכל כרטיס)`
                      : 'העלה קובץ PDF או תמונה (JPG, PNG) של הכרטיס'}
                  </span>
                )}
              </div>
              {formData.available_quantity > 1 && (
                <small>המערכת תפצל רק קובצי PDF מרובי עמודים – כל עמוד יהפוך לכרטיס נפרד</small>
              )}
              <SellFieldError message={fieldErrors.upload_single} />
            </div>
          )}

          {/* Ticket Cards - Seat only (+ PDF when separate_files) */}
          <div className="form-group ticket-packages-section">
            <label>כרטיסים למכירה *</label>
            <SellFieldError message={fieldErrors.packages} />
            <SellFieldError message={fieldErrors.seats} />
            <SellFieldError message={fieldErrors.upload_packages} />
            {Array.from({ length: formData.available_quantity }, (_, index) => {
              const packageData = formData.ticket_packages[index] || { seat_number: '', pdf_file: null };
              return (
                <div key={index} className="ticket-package-row">
                  <div className="package-header">
                    <h4>כרטיס {index + 1}</h4>
                    {uploadMethod === 'separate_files' && packageData.pdf_file && (
                      <span className="package-status">✓ קובץ הועלה</span>
                    )}
                  </div>
                  <div className="package-content">
                    <div className="form-group">
                      <label htmlFor={`seat_number_pkg_${index}`}>
                        כיסא * {formData.row && <span className="package-context">(שורה {formData.row})</span>}
                      </label>
                      <input
                        type="text"
                        id={`seat_number_pkg_${index}`}
                        name={`seat_number_pkg_${index}`}
                        value={packageData.seat_number || ''}
                        onChange={handleChange}
                        required
                        placeholder="לדוגמה: 12"
                        inputMode="numeric"
                        autoComplete="off"
                      />
                    </div>
                    {uploadMethod === 'separate_files' && (
                      <div className="form-group">
                        <label htmlFor={`pdf_file_package_${index}`}>קובץ כרטיס (PDF או תמונה) *</label>
                        <input
                          type="file"
                          id={`pdf_file_package_${index}`}
                          name={`pdf_file_package_${index}`}
                          onChange={handleChange}
                          accept={TICKET_FILE_INPUT_ACCEPT}
                          required={uploadMethod === 'separate_files'}
                        />
                        {packageData.pdf_file && (
                          <>
                            <TicketAttachmentPreview file={packageData.pdf_file} />
                            <span className="uploaded-file-name">✓ {packageData.pdf_file.name}</span>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Ticket Details & Restrictions Section */}
          <div className="ticket-details-section">
            <h3 className="ticket-details-section-title">פרטי הכרטיס והגבלות</h3>
            
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="ticket_type">סוג כרטיס *</label>
                <select
                  id="ticket_type"
                  name="ticket_type"
                  value="pdf"
                  disabled
                  required
                  className="premium-select"
                >
                  <option value="pdf">כרטיס אלקטרוני (PDF או תמונה)</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="split_type">אפשרויות פיצול וקנייה *</label>
                <select
                  id="split_type"
                  name="split_type"
                  value={formData.split_type}
                  onChange={handleChange}
                  required
                  className="premium-select"
                >
                  <option value="כל כמות">כל כמות</option>
                  <option value="זוגות בלבד">זוגות בלבד</option>
                  <option value="מכור הכל יחד">מכור הכל יחד</option>
                </select>
              </div>
            </div>

            <div className="form-group checkbox-group">
              <div className="checkbox-wrapper">
                <input
                  type="checkbox"
                  id="is_obstructed_view"
                  name="is_obstructed_view"
                  checked={formData.is_obstructed_view}
                  onChange={handleChange}
                  className="checkbox-input"
                />
                <label htmlFor="is_obstructed_view" className="checkbox-label">
                  הנוף מוסתר חלקית (Restricted View)
                </label>
              </div>
              <small className="checkbox-hint">
                סמן אם הכרטיסים שלך נמצאים באזור עם נוף מוגבל או מוסתר חלקית. זה עוזר למנוע תלונות מהקונים.
              </small>
            </div>
          </div>

          {/* Show checkbox only if quantity is 2 or more */}
          {formData.available_quantity >= 2 && (
            <div className="form-group checkbox-group">
              <div className="checkbox-wrapper">
                <input
                  type="checkbox"
                  id="is_together"
                  name="is_together"
                  checked={formData.is_together}
                  onChange={handleChange}
                  className="checkbox-input"
                />
                <label htmlFor="is_together" className="checkbox-label">
                  המקומות הם אחד ליד השני (מקומות יחד)
                </label>
              </div>
              <small className="checkbox-hint">
                סימון זה מעלה את האמון של הקונים ועוזר למכור מהר יותר
              </small>
            </div>
          )}

          <div className="form-group sell-pricing-block">
            <label htmlFor="listing_price">מחיר מכירה לכרטיס בודד *</label>
            <input
              type="number"
              id="listing_price"
              name="listing_price"
              value={formData.listing_price}
              onChange={handleChange}
              required
              min="1"
              step={sellCurrency === 'ILS' ? '1' : '0.01'}
              placeholder={sellSym}
              inputMode={sellCurrency === 'ILS' ? 'numeric' : 'decimal'}
            />
            <SellFieldError message={fieldErrors.listing_price} />
            <small className="sell-il-pricing-hint">
              זה המחיר עבור כרטיס אחד שיוצג לקונים לפני עמלת ביטחון. (אם העלית מספר כרטיסים, המערכת תכפיל את הסכום אוטומטית). אין צורך להזין מחיר מקורי או להעלות קבלה.
            </small>

            {feeBasis > 0 ? (
              <div className="price-breakdown-container">
                <div className="price-breakdown-row fee-row">
                  <span>עמלת מכירה (0% — ללא עמלה!):</span>
                  <span dir="ltr" style={{ color: '#16a34a', fontWeight: 700 }}>חינם ✓</span>
                </div>
                <div className="price-breakdown-row net-row">
                  <strong>הסכום שתקבלו (100% מהמחיר):</strong>
                  <strong dir="ltr">{sellSym}{formatAmountForCurrency(feeBasis, sellCurrency)}</strong>
                </div>
              </div>
            ) : null}
          </div>

          <div className="terms-checkbox-container sell-single-compliance">
            <label className="terms-checkbox-label">
              <input
                type="checkbox"
                id="sellerListingTerms"
                name="sellerListingTerms"
                checked={sellerListingTermsAccepted}
                onChange={(e) => {
                  setSellerListingTermsAccepted(e.target.checked);
                  setFieldErrors((prev) => {
                    if (!prev.terms) return prev;
                    const next = { ...prev };
                    delete next.terms;
                    return next;
                  });
                }}
                className="terms-checkbox-input"
                required
              />
              <span>
                אני מאשר/ת את{' '}
                <a href="/terms" target="_blank" rel="noopener noreferrer">
                  תקנון האתר
                </a>
                , ומצהיר/ה כי המחיר המבוקש אינו עולה על העלות המקורית של הכרטיס. כמו כן, ידוע לי שהתשלום
                יועבר אליי לאחר קיום האירוע, כדי להבטיח קנייה בטוחה לרוכש.
              </span>
            </label>
          </div>
          <SellFieldError message={fieldErrors.terms} />

          <button type="submit" disabled={loading} className="submit-button sell-submit--desktop-only">
            {loading ? (
              <>
                מפרסם כרטיס… <span className="button-spinner" aria-hidden />
              </>
            ) : (
              'הצע כרטיס למכירה'
            )}
          </button>
        </form>

        <div className="sell-submit-sticky-wrap">
          <button
            type="submit"
            form="sell-listing-form"
            disabled={loading}
            className="submit-button sell-submit-sticky-btn"
          >
            {loading ? (
              <>
                מפרסם כרטיס… <span className="button-spinner" aria-hidden />
              </>
            ) : (
              'הצע כרטיס למכירה'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Sell;
