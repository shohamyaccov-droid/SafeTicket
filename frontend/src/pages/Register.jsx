import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toastError, toastSuccess } from '../utils/toast';
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
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleChange = (e) => {
    if (error) setError('');
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.password2) {
      setError('הסיסמאות אינן תואמות');
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
      let msg = 'ההרשמה נכשלה. אנא נסה שוב.';
      if (typeof result.error === 'string') {
        msg = result.error;
        setError(result.error);
      } else if (result.error && typeof result.error === 'object') {
        const vals = Object.values(result.error);
        const flat = vals.flat().filter(Boolean);
        msg = flat.length ? flat.join(', ') : msg;
        setError(flat.length ? flat.join(', ') : 'ההרשמה נכשלה');
      } else {
        msg = result.error?.message || msg;
        setError(result.error?.message || 'ההרשמה נכשלה. אנא נסה שוב.');
      }
      toastError(msg);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>הרשמה</h2>
        {error && <div className="error-message">{error}</div>}
        <form onSubmit={handleSubmit}>
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
            />
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
            />
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
            />
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

