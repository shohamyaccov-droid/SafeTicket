/* eslint-disable react/prop-types */
import { useState } from 'react';
import { authAPI } from '../services/api';
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
export default function BecomeSellerModal({ open, onClose, onSuccess }) {
  const [phone, setPhone] = useState('');
  const [bank, setBank] = useState(initialBank);
  const [acceptedEscrow, setAcceptedEscrow] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  if (!open) return null;

  const setBankField = (key, value) => {
    setBank((prev) => ({ ...prev, [key]: value }));
  };

  const validateClientSide = () => {
    if (!acceptedEscrow) {
      return 'יש לאשר את תנאי הנאמנות כדי להמשיך.';
    }
    const ph = phone.trim();
    if (ph.length < 8) {
      return 'נא להזין מספר טלפון תקין.';
    }
    const name = bank.account_holder_name.trim();
    if (name.length < 2) {
      return 'נא להזין שם בעל חשבון.';
    }
    const idRaw = bank.id_number.replace(/[\s-]/g, '');
    if (!/^\d+$/.test(idRaw) || idRaw.length < 5 || idRaw.length > 9) {
      return 'נא להזין מספר תעודת זהות תקין (ספרות בלבד).';
    }
    if (!bank.bank_name_or_code.trim()) {
      return 'נא לציין בנק (שם או מספר).';
    }
    const br = bank.branch_number.trim();
    if (!/^\d+$/.test(br) || !br.length) {
      return 'נא להזין מספר סניף (ספרות בלבד).';
    }
    const ac = bank.account_number.trim();
    if (!/^\d+$/.test(ac) || ac.length < 4) {
      return 'נא להזין מספר חשבון בנק (ספרות בלבד).';
    }
    return '';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const localErr = validateClientSide();
    if (localErr) {
      setError(localErr);
      return;
    }
    setSaving(true);
    try {
      await authAPI.getCsrf();
      const idNorm = bank.id_number.replace(/[\s-]/g, '');
      await authAPI.upgradeToSeller({
        phone_number: phone.trim(),
        account_holder_name: bank.account_holder_name.trim(),
        id_number: idNorm,
        bank_name_or_code: bank.bank_name_or_code.trim(),
        branch_number: bank.branch_number.trim(),
        account_number: bank.account_number.trim(),
        accepted_escrow_terms: true,
      });
      onSuccess?.();
    } catch (err) {
      const d = err.response?.data;
      const msg =
        typeof d === 'object' && d !== null
          ? Object.values(d).flat().filter(Boolean).join(' ') || err.message
          : err.message;
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
        <h2 id="become-seller-title">הפוך למוכר</h2>
        <p className="become-seller-lead">
          התשלום לך ישוחרר רק לאחר קיום האירוע, בהתאם לתקנון האתר — כמו מודל נאמנות (escrow).
        </p>
        <form onSubmit={handleSubmit} className="become-seller-form">
          <label className="become-seller-label">
            מספר טלפון
            <input
              type="tel"
              dir="ltr"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
              placeholder="050-0000000"
              autoComplete="tel"
            />
          </label>

          <fieldset className="become-seller-bank-fieldset">
            <legend>פרטי חשבון בנק לזיכוי (ישראל)</legend>

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
              />
            </label>

            <label className="become-seller-label">
              בנק (שם או מספר בנק)
              <input
                type="text"
                value={bank.bank_name_or_code}
                onChange={(e) => setBankField('bank_name_or_code', e.target.value)}
                required
                placeholder="למשל: לאומי או 10"
              />
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
                />
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
                />
              </label>
            </div>
          </fieldset>

          <label className="become-seller-check">
            <input
              type="checkbox"
              checked={acceptedEscrow}
              onChange={(e) => setAcceptedEscrow(e.target.checked)}
              data-e2e="escrow-terms-checkbox"
            />
            <span>
              אני מסכים לקבל את התשלום רק לאחר קיום האירוע, בהתאם לתקנון האתר
            </span>
          </label>
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
