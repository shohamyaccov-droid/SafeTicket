import { useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toastError, toastSuccess } from '../utils/toast';
import { apiErrorMessageHe } from '../utils/apiErrors';
import '../pages/Auth.css';

function responseDetail(data) {
  const d = data?.detail;
  if (Array.isArray(d)) return d[0];
  if (typeof d === 'string') return d;
  return null;
}

/**
 * Shared login form for /login and future modals.
 * Mobile-oriented: autocomplete, no iOS auto-capitalize, touch-friendly submit, immediate navigation on success.
 */
export function LoginForm() {
  const [formData, setFormData] = useState({
    username: '',
    password: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const resolveReturnTo = () => {
    const fromQuery = searchParams.get('returnTo');
    const fromState = location.state?.returnTo;
    let fromStorage = null;
    try {
      fromStorage = sessionStorage.getItem('tradetix_return_to');
    } catch {
      /* ignore */
    }
    const raw = fromQuery || fromState || fromStorage || '/';
    return typeof raw === 'string' && raw.startsWith('/') && !raw.startsWith('//') && !raw.startsWith('/login')
      ? raw
      : '/';
  };

  const handleChange = (e) => {
    if (error) {
      setError('');
    }
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setError('');
    setLoading(true);

    try {
      const result = await login(formData.username.trim(), formData.password);

      if (result.success) {
        toastSuccess('התחברת בהצלחה');
        const returnTo = resolveReturnTo();
        try {
          sessionStorage.removeItem('tradetix_return_to');
        } catch {
          /* ignore */
        }
        navigate(returnTo, { replace: true });
        return;
      }

      const friendly =
        result.errorHebrew ||
        apiErrorMessageHe(result.error, null) ||
        'שם משתמש או סיסמה אינם נכונים';
      setError(friendly);
      toastError(friendly);
    } catch (err) {
      const friendly =
        !err?.response || err?.message === 'Network Error'
          ? 'שגיאת תקשורת עם השרת'
          : apiErrorMessageHe(err, responseDetail(err?.response?.data) || 'שם משתמש או סיסמה אינם נכונים');
      setError(friendly);
      toastError(friendly);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="login-form-mobile">
      {error && <div className="error-box">{error}</div>}
      <div className="form-group">
        <label htmlFor="username">שם משתמש</label>
        <input
          type="text"
          id="username"
          name="username"
          value={formData.username}
          onChange={handleChange}
          required
          autoComplete="username"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck="false"
          enterKeyHint="next"
          inputMode="text"
          placeholder="הזן שם משתמש"
        />
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
          autoComplete="current-password"
          enterKeyHint="go"
          placeholder="הזן סיסמה"
        />
      </div>
      <button type="submit" disabled={loading} className="auth-button">
        {loading ? 'מתחבר...' : 'התחברות'}
      </button>
    </form>
  );
}
