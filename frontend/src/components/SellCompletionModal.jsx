/* eslint-disable react/prop-types */
import { useEffect, useState } from 'react';
import '../components/BecomeSellerModal.css';
import './SellCompletionModal.css';

function PasswordField({ id, name, label, value, onChange, required }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="form-group sell-completion-field">
      <label htmlFor={id}>{label}</label>
      <div className="sell-password-field-wrap">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          name={name}
          value={value}
          onChange={onChange}
          required={required}
          autoComplete={name === 'password' ? 'new-password' : 'current-password'}
        />
        <button
          type="button"
          className="sell-password-toggle sell-completion-password-toggle"
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

/**
 * Reverse-funnel completion step: payout + optional auth before first listing upload.
 */
export default function SellCompletionModal({
  open,
  needsAuth,
  saving,
  error,
  fieldErrors,
  onClose,
  onSubmit,
}) {
  const [authMode, setAuthMode] = useState('register');
  const [authForm, setAuthForm] = useState({
    first_name: '',
    email: '',
    phone_number: '',
    password: '',
  });
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

  useEffect(() => {
    if (!open) return undefined;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e) => {
      if (e.key === 'Escape' && !saving) onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener('keydown', onKey);
    };
  }, [open, saving, onClose]);

  if (!open) return null;

  const setSellerBankField = (key, value) => {
    setSellerBank((prev) => ({ ...prev, [key]: value }));
  };

  const onAuthChange = (e) => {
    const { name, value } = e.target;
    setAuthForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (saving) return;
    onSubmit({
      authMode,
      authForm,
      payoutMethod,
      sellerBank,
      bitPhoneConfirm,
      acceptedEscrow,
    });
  };

  const showPayoutPhone = !needsAuth || authMode === 'login';
  const handleOverlayClose = () => {
    if (!saving) onClose?.();
  };

  return (
    <div className="sell-completion-overlay" role="presentation" onClick={handleOverlayClose}>
      <div
        className="sell-completion-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="sell-completion-title"
        onClick={(ev) => ev.stopPropagation()}
      >
        <button
          type="button"
          className="sell-completion-close"
          onClick={handleOverlayClose}
          aria-label="סגור"
          disabled={saving}
        >
          ×
        </button>
        <h2 id="sell-completion-title" className="sell-completion-title">
          עוד שלב אחד והכרטיס באוויר!
        </h2>
        <p className="sell-completion-lead">הפרטים שהזנת נשמרו — רק נשלים את פרטי הזיכוי והחשבון.</p>

        {error ? (
          <div className="become-seller-error" role="alert">
            {error}
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="sell-completion-form become-seller-form">
          <fieldset className="become-seller-bank-fieldset sell-completion-section">
            <legend>איך תרצו לקבל את הכסף?</legend>
            <div className="become-seller-payout-methods" role="radiogroup" aria-label="בחירת שיטת זיכוי">
              <label className="become-seller-radio">
                <input
                  type="radio"
                  name="completion_payout_method"
                  checked={payoutMethod === 'bank'}
                  onChange={() => setPayoutMethod('bank')}
                />
                <span>העברה בנקאית</span>
              </label>
              <label className="become-seller-radio">
                <input
                  type="radio"
                  name="completion_payout_method"
                  checked={payoutMethod === 'bit'}
                  onChange={() => setPayoutMethod('bit')}
                />
                <span>ביט</span>
              </label>
            </div>
            {payoutMethod === 'bit' ? (
              <p className="sell-inline-bit-disclaimer">אפשר להזין רק מספר טלפון לקבלה בביט — ללא פרטי בנק</p>
            ) : null}

            {!showPayoutPhone ? null : (
              <label className="become-seller-label sell-completion-field">
                מספר טלפון
                <input
                  type="tel"
                  dir="ltr"
                  name="phone_number"
                  value={authForm.phone_number}
                  onChange={onAuthChange}
                  required
                  inputMode="tel"
                  autoComplete="tel"
                />
                {fieldErrors.phone ? <span className="become-seller-field-error">{fieldErrors.phone}</span> : null}
              </label>
            )}

            <label className="become-seller-label sell-completion-field">
              שם בעל החשבון
              <input
                type="text"
                value={sellerBank.account_holder_name}
                onChange={(e) => setSellerBankField('account_holder_name', e.target.value)}
                required
                autoComplete="name"
              />
              {fieldErrors.account_holder_name ? (
                <span className="become-seller-field-error">{fieldErrors.account_holder_name}</span>
              ) : null}
            </label>

            <label className="become-seller-label sell-completion-field">
              תעודת זהות
              <input
                type="text"
                dir="ltr"
                inputMode="numeric"
                value={sellerBank.id_number}
                onChange={(e) => setSellerBankField('id_number', e.target.value)}
                required
                autoComplete="off"
              />
              {fieldErrors.id_number ? (
                <span className="become-seller-field-error">{fieldErrors.id_number}</span>
              ) : null}
            </label>

            {payoutMethod === 'bank' ? (
              <>
                <label className="become-seller-label sell-completion-field">
                  בנק (שם או מספר בנק)
                  <input
                    type="text"
                    value={sellerBank.bank_name_or_code}
                    onChange={(e) => setSellerBankField('bank_name_or_code', e.target.value)}
                    required
                  />
                  {fieldErrors.bank_name_or_code ? (
                    <span className="become-seller-field-error">{fieldErrors.bank_name_or_code}</span>
                  ) : null}
                </label>
                <div className="become-seller-row">
                  <label className="become-seller-label sell-completion-field">
                    סניף
                    <input
                      type="text"
                      dir="ltr"
                      inputMode="numeric"
                      value={sellerBank.branch_number}
                      onChange={(e) => setSellerBankField('branch_number', e.target.value)}
                      required
                    />
                    {fieldErrors.branch_number ? (
                      <span className="become-seller-field-error">{fieldErrors.branch_number}</span>
                    ) : null}
                  </label>
                  <label className="become-seller-label sell-completion-field">
                    מספר חשבון
                    <input
                      type="text"
                      dir="ltr"
                      inputMode="numeric"
                      value={sellerBank.account_number}
                      onChange={(e) => setSellerBankField('account_number', e.target.value)}
                      required
                    />
                    {fieldErrors.account_number ? (
                      <span className="become-seller-field-error">{fieldErrors.account_number}</span>
                    ) : null}
                  </label>
                </div>
              </>
            ) : (
              <label className="become-seller-label sell-completion-field">
                אימות מספר טלפון לביט
                <input
                  type="tel"
                  dir="ltr"
                  inputMode="tel"
                  value={bitPhoneConfirm}
                  onChange={(e) => setBitPhoneConfirm(e.target.value)}
                  required
                  placeholder={needsAuth ? 'הזינו שוב את מספר הטלפון הראשי' : 'הזינו שוב את המספר למעלה'}
                />
                {fieldErrors.bit_phone_number ? (
                  <span className="become-seller-field-error">{fieldErrors.bit_phone_number}</span>
                ) : null}
                {fieldErrors.bit_phone_number_confirm ? (
                  <span className="become-seller-field-error">{fieldErrors.bit_phone_number_confirm}</span>
                ) : null}
              </label>
            )}

            <label className="become-seller-check">
              <input
                type="checkbox"
                checked={acceptedEscrow}
                onChange={(e) => setAcceptedEscrow(e.target.checked)}
              />
              <span>אני מסכים לקבל את התשלום רק לאחר קיום האירוע, בהתאם לתקנון האתר</span>
            </label>
            {fieldErrors.acceptedEscrow ? (
              <span className="become-seller-field-error become-seller-field-error--block">{fieldErrors.acceptedEscrow}</span>
            ) : null}
          </fieldset>

          {needsAuth ? (
            <fieldset className="sell-completion-section sell-completion-auth">
              <legend>פרטי התחברות</legend>
              {authMode === 'register' ? (
                <div className="form-group sell-completion-field">
                  <label htmlFor="completion_first_name">שם פרטי</label>
                  <input
                    id="completion_first_name"
                    name="first_name"
                    value={authForm.first_name}
                    onChange={onAuthChange}
                    required
                    autoComplete="given-name"
                  />
                  {fieldErrors.first_name ? (
                    <span className="become-seller-field-error">{fieldErrors.first_name}</span>
                  ) : null}
                </div>
              ) : null}
              <div className="form-group sell-completion-field">
                <label htmlFor="completion_email">אימייל</label>
                <input
                  id="completion_email"
                  type="email"
                  name="email"
                  value={authForm.email}
                  onChange={onAuthChange}
                  required
                  dir="ltr"
                  autoComplete="email"
                />
                {fieldErrors.email ? <span className="become-seller-field-error">{fieldErrors.email}</span> : null}
              </div>
              {authMode === 'register' ? (
                <div className="form-group sell-completion-field">
                  <label htmlFor="completion_phone_number">מספר טלפון</label>
                  <input
                    id="completion_phone_number"
                    type="tel"
                    dir="ltr"
                    name="phone_number"
                    value={authForm.phone_number}
                    onChange={onAuthChange}
                    required
                    inputMode="tel"
                    autoComplete="tel"
                  />
                  {fieldErrors.phone_number ? (
                    <span className="become-seller-field-error">{fieldErrors.phone_number}</span>
                  ) : null}
                </div>
              ) : null}
              <PasswordField
                id="completion_password"
                name="password"
                label="סיסמה"
                value={authForm.password}
                onChange={onAuthChange}
                required
              />
              {fieldErrors.password ? (
                <span className="become-seller-field-error">{fieldErrors.password}</span>
              ) : null}
              <button
                type="button"
                className="sell-completion-switch-btn"
                onClick={() => setAuthMode((m) => (m === 'login' ? 'register' : 'login'))}
              >
                {authMode === 'login' ? 'אין חשבון? הרשמה' : 'יש חשבון? התחברות'}
              </button>
            </fieldset>
          ) : null}

          <button type="submit" className="become-seller-submit sell-completion-submit" disabled={saving}>
            {saving ? 'שומר ומעלה…' : 'סיום והעלאת הכרטיס'}
          </button>
        </form>
      </div>
    </div>
  );
}
