/* eslint-disable react/prop-types */
import { useState } from 'react';
import { authAPI } from '../services/api';
import { toastError } from '../utils/toast';
import './BecomeSellerModal.css';

const initialBank = {
  account_holder_name: '',
  id_number: '',
  bank_name_or_code: '',
  branch_number: '',
  account_number: '',
};

/**
 * Escrow-style seller onboarding (Viagogo-inspired): payout + mandatory escrow acceptance.
 * Bank details are sent as discrete fields; API stores JSON in payout_details.
 */
export default function BecomeSellerModal({
  open,
  onClose,
  onSuccess,
  title = 'הפוך למוכר',
  lead = 'התשלום לך ישוחרר רק לאחר קיום האירוע, בהתאם לתקנון האתר — כמו מודל נאמנות (escrow).',
}) {
  const [phone, setPhone] = useState('');
  const [payoutMethod, setPayoutMethod] = useState('bank');
  const [bitPhoneConfirm, setBitPhoneConfirm] = useState('');
  const [bank, setBank] = useState(initialBank);
  const [acceptedEscrow, setAcceptedEscrow] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [saving, setSaving] = useState(false);

  if (!open) return null;

  const setBankField = (key, value) => {
    setFieldErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setBank((prev) => ({ ...prev, [key]: value }));
  };

  const validateClientSide = () => {
    const fe = {};
    if (!acceptedEscrow) {
      fe.acceptedEscrow = 'יש לאשר את תנאי הנאמנות כדי להמשיך.';
    }
    const ph = phone.trim();
    if (ph.length < 8) {
      fe.phone = 'נא להזין מספר טלפון תקין.';
    }
    const name = bank.account_holder_name.trim();
    if (name.length < 2) {
      fe.account_holder_name = 'נא להזין שם בעל חשבון.';
    }
    const idRaw = bank.id_number.replace(/[\s-]/g, '');
    if (!/^\d+$/.test(idRaw) || idRaw.length < 5 || idRaw.length > 9) {
      fe.id_number = 'נא להזין מספר תעודת זהות תקין (ספרות בלבד).';
    }
    if (payoutMethod === 'bank') {
      if (!bank.bank_name_or_code.trim()) {
        fe.bank_name_or_code = 'נא לציין בנק (שם או מספר).';
      }
      const br = bank.branch_number.trim();
      if (!/^\d+$/.test(br) || !br.length) {
        fe.branch_number = 'נא להזין מספר סניף (ספרות בלבד).';
      }
      const ac = bank.account_number.trim();
      if (!/^\d+$/.test(ac) || ac.length < 4) {
        fe.account_number = 'נא להזין מספר חשבון בנק (ספרות בלבד).';
      }
    } else {
      const normalize = (v) => {
        const digits = String(v || '').replace(/\D/g, '');
        if (digits.startsWith('972')) return `0${digits.slice(3)}`;
        return digits;
      };
      const phoneNorm = normalize(phone);
      const bitConfirmNorm = normalize(bitPhoneConfirm);
      if (!/^05\d{8}$/.test(phoneNorm)) {
        fe.bit_phone_number = 'נא להזין מספר טלפון ביט ישראלי תקין.';
      }
      if (phoneNorm !== bitConfirmNorm) {
        fe.bit_phone_number_confirm = 'מספרי הטלפון לביט אינם תואמים.';
      }
    }
    return fe;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const fe = validateClientSide();
    if (Object.keys(fe).length > 0) {
      setFieldErrors(fe);
      return;
    }
    setFieldErrors({});
    setSaving(true);
    try {
      await authAPI.getCsrf();
      const idNorm = bank.id_number.replace(/[\s-]/g, '');
      const bitNorm = phone.replace(/\D/g, '').replace(/^972/, '0');
      await authAPI.upgradeToSeller({
        phone_number: phone.trim(),
        payout_method: payoutMethod,
        bit_phone_number: payoutMethod === 'bit' ? bitNorm : '',
        account_holder_name: bank.account_holder_name.trim(),
        id_number: idNorm,
        bank_name_or_code: payoutMethod === 'bank' ? bank.bank_name_or_code.trim() : '',
        branch_number: payoutMethod === 'bank' ? bank.branch_number.trim() : '',
        account_number: payoutMethod === 'bank' ? bank.account_number.trim() : '',
        accepted_escrow_terms: true,
      });
      onSuccess?.();
    } catch (err) {
      const d = err.response?.data;
      let msg =
        typeof d === 'object' && d !== null
          ? Object.values(d).flat().filter(Boolean).join(' ') || err.message
          : err.message;
      if (err.response?.status === 403) {
        msg = 'תקשורת לשרת נדחתה, אנא רענן את העמוד ונסה שוב';
      }
      toastError(msg || 'שגיאה בשדרוג החשבון.');
      setError(msg || 'שגיאה בשדרוג החשבון.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="become-seller-overlay" role="presentation" onClick={onClose}>
      <div
        className="become-seller-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="become-seller-title"
        data-e2e="become-seller-modal"
        onClick={(ev) => ev.stopPropagation()}
      >
        <button type="button" className="become-seller-close" onClick={onClose} aria-label="סגור">
          ×
        </button>
        <h2 id="become-seller-title">{title}</h2>
        <p className="become-seller-lead">{lead}</p>
        <form onSubmit={handleSubmit} className="become-seller-form">
          <label className="become-seller-label">
            מספר טלפון
            <input
              type="tel"
              dir="ltr"
              value={phone}
              onChange={(e) => {
                setFieldErrors((prev) => {
                  if (!prev.phone) return prev;
                  const next = { ...prev };
                  delete next.phone;
                  return next;
                });
                setPhone(e.target.value);
              }}
              required
              placeholder="050-0000000"
              autoComplete="tel"
              inputMode="tel"
            />
            {fieldErrors.phone ? <span className="become-seller-field-error">{fieldErrors.phone}</span> : null}
          </label>

          <fieldset className="become-seller-bank-fieldset">
            <legend>איך תרצה לקבל את התשלום?</legend>

            <div className="become-seller-payout-methods" role="radiogroup" aria-label="בחירת שיטת זיכוי">
              <label className="become-seller-radio">
                <input
                  type="radio"
                  name="payout_method"
                  value="bank"
                  checked={payoutMethod === 'bank'}
                  onChange={() => setPayoutMethod('bank')}
                />
                <span>העברה בנקאית</span>
              </label>
              <label className="become-seller-radio">
                <input
                  type="radio"
                  name="payout_method"
                  value="bit"
                  checked={payoutMethod === 'bit'}
                  onChange={() => setPayoutMethod('bit')}
                />
                <span>ביט</span>
              </label>
            </div>

            {payoutMethod === 'bit' ? (
              <p className="sell-inline-bit-disclaimer">אפשר להזין רק מספר טלפון לקבלה בביט — ללא פרטי בנק</p>
            ) : null}

            <label className="become-seller-label">
              שם בעל החשבון
              <input
                type="text"
                value={bank.account_holder_name}
                onChange={(e) => setBankField('account_holder_name', e.target.value)}
                required
                autoComplete="name"
                placeholder="כפי שמופיע בבנק"
              />
              {fieldErrors.account_holder_name ? (
                <span className="become-seller-field-error">{fieldErrors.account_holder_name}</span>
              ) : null}
            </label>

            <label className="become-seller-label">
              תעודת זהות
              <input
                type="text"
                dir="ltr"
                inputMode="numeric"
                value={bank.id_number}
                onChange={(e) => setBankField('id_number', e.target.value)}
                required
                placeholder="9 ספרות"
                autoComplete="off"
              />
              {fieldErrors.id_number ? <span className="become-seller-field-error">{fieldErrors.id_number}</span> : null}
            </label>

            {payoutMethod === 'bank' ? (
              <>
                <label className="become-seller-label">
                  בנק (שם או מספר בנק)
                  <input
                    type="text"
                    value={bank.bank_name_or_code}
                    onChange={(e) => setBankField('bank_name_or_code', e.target.value)}
                    required
                    placeholder="למשל: לאומי או 10"
                    inputMode="text"
                  />
                  {fieldErrors.bank_name_or_code ? (
                    <span className="become-seller-field-error">{fieldErrors.bank_name_or_code}</span>
                  ) : null}
                </label>

                <div className="become-seller-row">
                  <label className="become-seller-label">
                    סניף
                    <input
                      type="text"
                      dir="ltr"
                      inputMode="numeric"
                      value={bank.branch_number}
                      onChange={(e) => setBankField('branch_number', e.target.value)}
                      required
                      placeholder="מספר סניף"
                      autoComplete="off"
                    />
                    {fieldErrors.branch_number ? (
                      <span className="become-seller-field-error">{fieldErrors.branch_number}</span>
                    ) : null}
                  </label>
                  <label className="become-seller-label">
                    מספר חשבון
                    <input
                      type="text"
                      dir="ltr"
                      inputMode="numeric"
                      value={bank.account_number}
                      onChange={(e) => setBankField('account_number', e.target.value)}
                      required
                      placeholder="מספר חשבון"
                      autoComplete="off"
                    />
                    {fieldErrors.account_number ? (
                      <span className="become-seller-field-error">{fieldErrors.account_number}</span>
                    ) : null}
                  </label>
                </div>
              </>
            ) : (
              <label className="become-seller-label">
                אימות מספר טלפון לביט
                <input
                  type="tel"
                  dir="ltr"
                  inputMode="tel"
                  value={bitPhoneConfirm}
                  onChange={(e) => setBitPhoneConfirm(e.target.value)}
                  required
                  placeholder="הכנס שוב את המספר"
                  autoComplete="tel"
                />
                {fieldErrors.bit_phone_number ? (
                  <span className="become-seller-field-error">{fieldErrors.bit_phone_number}</span>
                ) : null}
                {fieldErrors.bit_phone_number_confirm ? (
                  <span className="become-seller-field-error">{fieldErrors.bit_phone_number_confirm}</span>
                ) : null}
              </label>
            )}
          </fieldset>

          <label className="become-seller-check">
            <input
              type="checkbox"
              checked={acceptedEscrow}
              onChange={(e) => {
                setFieldErrors((prev) => {
                  if (!prev.acceptedEscrow) return prev;
                  const next = { ...prev };
                  delete next.acceptedEscrow;
                  return next;
                });
                setAcceptedEscrow(e.target.checked);
              }}
              data-e2e="escrow-terms-checkbox"
            />
            <span>
              אני מסכים לקבל את התשלום רק לאחר קיום האירוע, בהתאם לתקנון האתר
            </span>
          </label>
          {fieldErrors.acceptedEscrow ? (
            <span className="become-seller-field-error become-seller-field-error--block">
              {fieldErrors.acceptedEscrow}
            </span>
          ) : null}
          {error ? (
            <div className="become-seller-error" role="alert">
              {error}
            </div>
          ) : null}
          <button type="submit" className="become-seller-submit" disabled={saving} data-e2e="become-seller-submit">
            {saving ? 'שומר…' : 'אישור והמשך'}
          </button>
        </form>
      </div>
    </div>
  );
}
