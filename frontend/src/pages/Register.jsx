import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toastError, toastSuccess } from '../utils/toast';
import { apiErrorMessageHe } from '../utils/apiErrors';
import './Auth.css';

const Register = () => {
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    password: '',
    password2: '',
  });
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

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

    if (formData.password !== formData.password2) {
      setFieldErrors({ password2: 'הסיסמאות אינן תואמות' });
      return;
    }

    setLoading(true);
    const registerData = {
      username: formData.email,
      email: formData.email,
      first_name: formData.first_name,
      last_name: formData.last_name,
      password: formData.password,
      password2: formData.password2,
      role: 'buyer',
    };
    const result = await register(registerData);
    setLoading(false);

    if (result.success) {
      toastSuccess('נרשמת בהצלחה — ברוך הבא!', { duration: 12_000 });
      navigate('/');
    } else {
      const msg = apiErrorMessageHe(result.error, 'ההרשמה נכשלה. אנא נסה שוב.');
      setError(msg);
      toastError(msg);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>הרשמה</h2>
        {error && <div className="error-message">{error}</div>}
        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label htmlFor="first_name">שם פרטי</label>
            <input
              type="text"
              id="first_name"
              name="first_name"
              value={formData.first_name}
              onChange={handleChange}
              required
              placeholder="הזן שם פרטי"
              dir="rtl"
              autoComplete="given-name"
            />
            {fieldErrors.first_name ? <span className="field-error-text">{fieldErrors.first_name}</span> : null}
          </div>
          <div className="form-group">
            <label htmlFor="last_name">שם משפחה</label>
            <input
              type="text"
              id="last_name"
              name="last_name"
              value={formData.last_name}
              onChange={handleChange}
              required
              placeholder="הזן שם משפחה"
              dir="rtl"
              autoComplete="family-name"
            />
            {fieldErrors.last_name ? <span className="field-error-text">{fieldErrors.last_name}</span> : null}
          </div>
          <div className="form-group">
            <label htmlFor="email">אימייל</label>
            <input
              type="email"
              id="email"
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
            <label htmlFor="password">סיסמה</label>
            <input
              type="password"
              id="password"
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
            <label htmlFor="password2">אימות סיסמה</label>
            <input
              type="password"
              id="password2"
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
          <button type="submit" disabled={loading} className="auth-button">
            {loading ? 'נרשם...' : 'הרשמה'}
          </button>
        </form>
        <p className="auth-footer">
          כבר יש לך חשבון? <Link to="/login">התחבר כאן</Link>
        </p>
      </div>
    </div>
  );
};

export default Register;
