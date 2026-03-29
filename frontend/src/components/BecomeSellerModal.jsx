import { useState } from 'react';
import { authAPI } from '../services/api';
import './BecomeSellerModal.css';

/**
 * Escrow-style seller onboarding (Viagogo-inspired): payout + mandatory escrow acceptance.
 */
export default function BecomeSellerModal({ open, onClose, onSuccess }) {
  const [phone, setPhone] = useState('');
  const [payoutDetails, setPayoutDetails] = useState('');
  const [acceptedEscrow, setAcceptedEscrow] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  if (!open) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!acceptedEscrow) {
      setError('יש לאשר את תנאי הנאמנות כדי להמשיך.');
      return;
    }
    setSaving(true);
    try {
      await authAPI.getCsrf();
      await authAPI.upgradeToSeller({
        phone_number: phone.trim(),
        payout_details: payoutDetails.trim(),
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
        <form onSubmit={handleSubmit}>
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
          <label className="become-seller-label">
            פרטי תשלום (PayPal או פרטי בנק)
            <textarea
              rows={4}
              value={payoutDetails}
              onChange={(e) => setPayoutDetails(e.target.value)}
              required
              minLength={4}
              placeholder="אימייל PayPal או בנק / סניף / חשבון"
            />
          </label>
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
