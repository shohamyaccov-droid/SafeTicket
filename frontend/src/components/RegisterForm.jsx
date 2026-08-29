/* eslint-disable react/prop-types */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toastError, toastSuccess } from '../utils/toast';
import { apiErrorMessageHe } from '../utils/apiErrors';
import { isValidRequiredEmail, isValidRequiredPhone, validateRequiredEmail, validateRequiredPhone } from '../utils/contactValidation';
import '../pages/Auth.css';

export default function RegisterForm({ onSuccess, onRequestLogin, idPrefix = 'register' } = {}) {
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone_number: '',
    password: '',
    password2: '',
  });
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();
  const fieldId = (name) => `${idPrefix}-${name}`;

  const handleChange = (e) => {
    const { name } = e.target;
    if (error) setError('');
    if (fieldErrors[name]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
    setFormData({
      ...formData,
      [name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setFieldErrors({});

    const nextFieldErrors = {};
    const emailErr = validateRequiredEmail(formData.email);
    if (emailErr) nextFieldErrors.email = emailErr;
    const phoneErr = validateRequiredPhone(formData.phone_number);
    if (phoneErr) nextFieldErrors.phone_number = phoneErr;
    if (formData.password !== formData.password2) {
      nextFieldErrors.password2 = 'הסיסמאות אינן תואמות';
    }
    if (Object.keys(nextFieldErrors).length) {
      setFieldErrors(nextFieldErrors);
      const firstMsg = nextFieldErrors.phone_number || nextFieldErrors.email || nextFieldErrors.password2;
      if (firstMsg) setError(firstMsg);
      return;
    }

    setLoading(true);
    const registerData = {
      username: formData.email,
      email: formData.email,
      first_name: formData.first_name,
      last_name: formData.last_name,
      phone_number: formData.phone_number.trim(),
      password: formData.password,
      password2: formData.password2,
      role: 'buyer',
    };
    const result = await register(registerData);
    setLoading(false);

    if (result.success) {
      toastSuccess('נרשמת בהצלחה — ברוך הבא!', { duration: 12_000 });
      if (typeof onSuccess === 'function') {
        onSuccess();
        return;
      }
      navigate('/');
    } else {
      const msg = apiErrorMessageHe(result.error, 'ההרשמה נכשלה. אנא נסה שוב.');
      setError(msg);
      toastError(msg);
    }
  };

  const loginFooter = typeof onRequestLogin === 'function' ? (
    <p className="auth-footer">
      כבר יש לך חשבון?{' '}
      <button type="button" className="auth-text-link" onClick={onRequestLogin}>
        התחבר כאן
      </button>
    </p>
  ) : (
    <p className="auth-footer">
      כבר יש לך חשבון? <Link to="/login">התחבר כאן</Link>
    </p>
  );

  return (
    <>
      {error && <div className="error-message">{error}</div>}
      <form onSubmit={handleSubmit} noValidate>
        <div className="form-group">
          <label htmlFor={fieldId('first_name')}>שם פרטי</label>
          <input
            type="text"
            id={fieldId('first_name')}
            name="first_name"
            value={formData.first_name}
            onChange={handleChange}
            placeholder="הזן שם פרטי"
            dir="rtl"
            autoComplete="given-name"
          />
          {fieldErrors.first_name ? <span className="field-error-text">{fieldErrors.first_name}</span> : null}
        </div>
        <div className="form-group">
          <label htmlFor={fieldId('last_name')}>שם משפחה</label>
          <input
            type="text"
            id={fieldId('last_name')}
            name="last_name"
            value={formData.last_name}
            onChange={handleChange}
            placeholder="הזן שם משפחה"
            dir="rtl"
            autoComplete="family-name"
          />
          {fieldErrors.last_name ? <span className="field-error-text">{fieldErrors.last_name}</span> : null}
        </div>
        <div className="form-group">
          <label htmlFor={fieldId('email')}>אימייל *</label>
          <input
            type="email"
            id={fieldId('email')}
            name="email"
            value={formData.email}
            onChange={handleChange}
            required
            placeholder="your.email@example.com"
            inputMode="email"
            autoComplete="email"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck="false"
          />
          {fieldErrors.email ? <span className="field-error-text">{fieldErrors.email}</span> : null}
        </div>
        <div className="form-group">
          <label htmlFor={fieldId('phone_number')}>מספר טלפון *</label>
          <input
            type="tel"
            id={fieldId('phone_number')}
            name="phone_number"
            value={formData.phone_number}
            onChange={handleChange}
            required
            placeholder="050-1234567"
            inputMode="tel"
            autoComplete="tel"
            dir="ltr"
          />
          {fieldErrors.phone_number ? <span className="field-error-text">{fieldErrors.phone_number}</span> : null}
        </div>
        <div className="form-group">
          <label htmlFor={fieldId('password')}>סיסמה</label>
          <input
            type="password"
            id={fieldId('password')}
            name="password"
            value={formData.password}
            onChange={handleChange}
            required
            placeholder="הזן סיסמה"
            autoComplete="new-password"
            autoCapitalize="none"
          />
          {fieldErrors.password ? <span className="field-error-text">{fieldErrors.password}</span> : null}
        </div>
        <div className="form-group">
          <label htmlFor={fieldId('password2')}>אימות סיסמה</label>
          <input
            type="password"
            id={fieldId('password2')}
            name="password2"
            value={formData.password2}
            onChange={handleChange}
            required
            placeholder="הזן סיסמה שוב"
            autoComplete="new-password"
            autoCapitalize="none"
          />
          {fieldErrors.password2 ? <span className="field-error-text">{fieldErrors.password2}</span> : null}
        </div>
        <button
          type="submit"
          disabled={
            loading ||
            !isValidRequiredEmail(formData.email) ||
            !isValidRequiredPhone(formData.phone_number) ||
            !formData.password ||
            !formData.password2
          }
          className="auth-button"
        >
          {loading ? 'נרשם...' : 'הרשמה'}
        </button>
      </form>
      {loginFooter}
    </>
  );
}
