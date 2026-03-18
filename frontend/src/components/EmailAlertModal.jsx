import { useState } from 'react';
import { alertAPI } from '../services/api';
import './EmailAlertModal.css';

const EmailAlertModal = ({ event, onClose, onSuccess }) => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (!email || !email.includes('@')) {
      setError('אנא הזן כתובת אימייל תקינה');
      setLoading(false);
      return;
    }

    try {
      const response = await alertAPI.createAlert({
        event: event.id,
        email: email.trim(),
      });

      if (response.status === 201 || response.status === 200) {
        setSuccess(true);
        setTimeout(() => {
          if (onSuccess) onSuccess();
          onClose();
        }, 1500);
      }
    } catch (err) {
      const errorMessage = err.response?.data?.error || err.response?.data?.email?.[0] || 'שגיאה בהוספה לרשימת ההמתנה';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="email-alert-modal-overlay" onClick={onClose}>
        <div className="email-alert-modal" onClick={(e) => e.stopPropagation()}>
          <div className="email-alert-modal-success">
            <div className="success-icon">✓</div>
            <h3>נוסף בהצלחה!</h3>
            <p>נודיע לך כשיהיו כרטיסים זמינים לאירוע זה</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="email-alert-modal-overlay" onClick={onClose}>
      <div className="email-alert-modal" onClick={(e) => e.stopPropagation()}>
        <button className="email-alert-modal-close" onClick={onClose}>×</button>
        <h2>קבל התראה על כרטיסים</h2>
        <p className="email-alert-modal-description">
          אין כרטיסים זמינים כרגע לאירוע זה. הזן את כתובת האימייל שלך ונודיע לך כשיהיו כרטיסים זמינים.
        </p>
        <form onSubmit={handleSubmit}>
          <div className="email-alert-form-group">
            <label htmlFor="email">כתובת אימייל</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              required
              disabled={loading}
            />
          </div>
          {error && <div className="email-alert-error">{error}</div>}
          <div className="email-alert-modal-actions">
            <button type="button" onClick={onClose} disabled={loading}>
              ביטול
            </button>
            <button type="submit" disabled={loading || !email}>
              {loading ? 'שולח...' : 'הוסף לרשימת ההמתנה'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default EmailAlertModal;




