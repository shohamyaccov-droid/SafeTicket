import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import '../pages/Auth.css';

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
        navigate('/', { replace: true });
        return;
      }

      let errorMessage = 'שם משתמש או סיסמה אינם נכונים';
      if (typeof result.error === 'string') {
        errorMessage = result.error;
      } else if (result.error?.detail) {
        errorMessage = result.error.detail;
      } else if (result.error?.message) {
        errorMessage = result.error.message;
      } else if (result.error != null) {
        errorMessage =
          typeof result.error === 'object'
            ? JSON.stringify(result.error)
            : String(result.error);
      }
      setError(errorMessage);
    } catch (err) {
      console.error('Login error:', err);
      const isNetworkError = !err?.response || err?.message === 'Network Error';
      const errorMessage = isNetworkError
        ? 'שגיאת תקשורת עם השרת'
        : err?.response?.data?.detail ||
          err?.response?.data?.error ||
          err?.response?.data?.message ||
          'שם משתמש או סיסמה אינם נכונים';
      setError(errorMessage);
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
