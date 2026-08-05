/* eslint-disable react/prop-types */
import { useState } from 'react';
import { authAPI } from '../services/api';
import './BuyerIdentityInlineForm.css';

/**
 * Collect missing PayMe identity (first/last name + phone) without leaving checkout.
 */
export default function BuyerIdentityInlineForm({
  user,
  initialFirstName = '',
  initialLastName = '',
  initialPhone = '',
  missingFields = ['name', 'phone'],
  submitLabel = 'שמור והמשך לתשלום',
  onSaved,
  onCancel,
}) {
  const needName = missingFields.includes('name');
  const needPhone = missingFields.includes('phone');
  const [firstName, setFirstName] = useState(
    () => String(initialFirstName || user?.first_name || '').trim()
  );
  const [lastName, setLastName] = useState(
    () => String(initialLastName || user?.last_name || '').trim()
  );
  const [phone, setPhone] = useState(
    () => String(initialPhone || user?.phone_number || user?.bit_phone_number || '').trim()
  );
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const fn = firstName.trim();
    const ln = lastName.trim();
    const ph = phone.trim();
    if (needName) {
      if (fn.length < 2) {
        setError('נא להזין שם פרטי תקין');
        return;
      }
      if (ln.length < 2) {
        setError('נא להזין שם משפחה תקין');
        return;
      }
    }
    if (needPhone) {
      const digits = ph.replace(/\D/g, '');
      if (digits.length < 9 || digits.length > 15) {
        setError('נא להזין מספר טלפון תקין (לפחות 9 ספרות)');
        return;
      }
    }

    const payload = {};
    if (needName) {
      payload.first_name = fn;
      payload.last_name = ln;
    }
    if (needPhone) {
      payload.phone_number = ph;
    }

    setSaving(true);
    try {
      let savedUser = null;
      if (user) {
        const res = await authAPI.updateProfile(payload);
        savedUser = res.data?.user || null;
      }
      await onSaved?.({
        firstName: needName ? fn : String(user?.first_name || '').trim(),
        lastName: needName ? ln : String(user?.last_name || '').trim(),
        phone: needPhone ? ph : String(user?.phone_number || '').trim(),
        user: savedUser,
      });
    } catch (err) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        'לא הצלחנו לשמור את הפרטים. נסו שוב.';
      setError(typeof msg === 'string' ? msg : 'לא הצלחנו לשמור את הפרטים. נסו שוב.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="buyer-identity-inline" onSubmit={handleSubmit} dir="rtl" noValidate>
      <p className="buyer-identity-inline__lead">
        חסרים פרטים להשלמת התשלום. מלאו אותם כאן והמשיכו בלי לעזוב את העמוד.
      </p>
      {needName ? (
        <div className="buyer-identity-inline__row">
          <div className="buyer-identity-inline__field">
            <label htmlFor="buyer-id-first">שם פרטי</label>
            <input
              id="buyer-id-first"
              type="text"
              autoComplete="given-name"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              disabled={saving}
              required
            />
          </div>
          <div className="buyer-identity-inline__field">
            <label htmlFor="buyer-id-last">שם משפחה</label>
            <input
              id="buyer-id-last"
              type="text"
              autoComplete="family-name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              disabled={saving}
              required
            />
          </div>
        </div>
      ) : null}
      {needPhone ? (
        <div className="buyer-identity-inline__field">
          <label htmlFor="buyer-id-phone">טלפון נייד</label>
          <input
            id="buyer-id-phone"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            placeholder="05XXXXXXXX"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            disabled={saving}
            required
            dir="ltr"
          />
        </div>
      ) : null}
      {error ? (
        <p className="buyer-identity-inline__error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="buyer-identity-inline__actions">
        {onCancel ? (
          <button type="button" className="buyer-identity-inline__cancel" onClick={onCancel} disabled={saving}>
            ביטול
          </button>
        ) : null}
        <button type="submit" className="buyer-identity-inline__submit" disabled={saving}>
          {saving ? 'שומר…' : submitLabel}
        </button>
      </div>
    </form>
  );
}
