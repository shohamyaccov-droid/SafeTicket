import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Auth.css';

const Login = () => {
  const [formData, setFormData] = useState({
    username: '',
    password: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleChange = (e) => {
    // Clear error when user starts typing
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
    setError('');
    setLoading(true);

    try {
      const result = await login(formData.username, formData.password);
      
      if (result.success) {
        // Add a small delay to ensure state is updated before navigation
        setTimeout(() => {
          navigate('/');
        }, 100);
      } else {
        // ALWAYS render error when success is false - never fail silently
        let errorMessage = 'שם משתמש או סיסמה אינם נכונים';
        if (typeof result.error === 'string') {
          errorMessage = result.error;
        } else if (result.error?.detail) {
          errorMessage = result.error.detail;
        } else if (result.error?.message) {
          errorMessage = result.error.message;
        } else if (result.error != null) {
          errorMessage = typeof result.error === 'object'
            ? JSON.stringify(result.error)
            : String(result.error);
        }
        setError(errorMessage);
        setLoading(false);
      }
    } catch (err) {
      console.error('Login error:', err);
      // Network/CORS errors: err.response is undefined
      const isNetworkError = !err?.response || err?.message === 'Network Error';
      const errorMessage = isNetworkError
        ? 'שגיאת תקשורת עם השרת'
        : (err?.response?.data?.detail ||
           err?.response?.data?.error ||
           err?.response?.data?.message ||
           'שם משתמש או סיסמה אינם נכונים');
      setError(errorMessage);
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>התחברות</h2>
        {error && <div className="error-box">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">שם משתמש</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              required
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
              placeholder="הזן סיסמה"
            />
          </div>
          <button type="submit" disabled={loading} className="auth-button">
            {loading ? 'מתחבר...' : 'התחברות'}
          </button>
        </form>
        <p className="auth-footer">
          אין לך חשבון? <Link to="/register">הירשם כאן</Link>
        </p>
      </div>
    </div>
  );
};

export default Login;

