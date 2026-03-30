import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toastError, toastSuccess } from '../utils/toast';
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
        navigate('/', { replace: true });
        return;
      }

      let exact =
        typeof result.error === 'string'
          ? result.error
          : responseDetail(result.error) ||
            result.error?.message ||
            (typeof result.error?.error === 'string' ? result.error.error : null);
      if (exact == null && result.error != null) {
        exact =
          typeof result.error === 'object'
            ? JSON.stringify(result.error)
            : String(result.error);
      }
      if (!exact) exact = 'Login Failed';

      const friendly =
        result.errorHebrew ||
        (typeof result.error === 'string' && result.error.length < 200
          ? result.error
          : null) ||
        'שם משתמש או סיסמה אינם נכונים';
      setError(friendly);
      toastError(exact);
    } catch (err) {
      const exact =
        responseDetail(err?.response?.data) ||
        err?.message ||
        'Login Failed';
      const friendly =
        !err?.response || err?.message === 'Network Error'
          ? 'שגיאת תקשורת עם השרת'
          : exact;
      setError(friendly);
      toastError(exact);
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
