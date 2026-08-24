/* eslint-disable react/prop-types */
import { useState } from 'react';
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
              <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}

/**
 * Conversion: guests only sign up / log in here — no bank, Bit, ID, or escrow.
 * Payout details are collected later in profile after a ticket sells.
 */
export default function SellCompletionModal({
  saving,
  error,
  fieldErrors,
  onBack,
  onSubmit,
}) {
  const [authMode, setAuthMode] = useState('register');
  const [authForm, setAuthForm] = useState({
    first_name: '',
    email: '',
    password: '',
  });

  const onAuthChange = (e) => {
    const { name, value } = e.target;
    setAuthForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (saving) return;
    onSubmit({ authMode: authMode, authForm: authForm });
  };

  return (
    <div className="sell-auth-step" role="region" aria-labelledby="sell-auth-title">
      <h2 id="sell-auth-title" className="sell-completion-title">
        {authMode === 'register' ? 'יצירת חשבון מהירה' : 'התחברות'}
      </h2>
      <p className="sell-completion-lead">
        רק שם, אימייל וסיסמה. הוספת חשבון בנק או ביט תתבצע לאחר העלאת הכרטיס.
      </p>

      {error ? (
        <div className="become-seller-error" role="alert">
          {error}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="sell-completion-form sell-auth-form">
        {authMode === 'register' ? (
          <div className="form-group sell-completion-field">
            <label htmlFor="sell_auth_first_name">שם</label>
            <input
              id="sell_auth_first_name"
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
          <label htmlFor="sell_auth_email">אימייל</label>
          <input
            id="sell_auth_email"
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
        <PasswordField
          id="sell_auth_password"
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

        <div className="sell-wizard-actions">
          <button type="button" className="sell-wizard-back" onClick={onBack} disabled={saving}>
            חזרה
          </button>
          <button type="submit" className="become-seller-submit sell-completion-submit" disabled={saving}>
            {saving ? 'מפרסם…' : 'פרסם כרטיס'}
          </button>
        </div>
      </form>
    </div>
  );
}
