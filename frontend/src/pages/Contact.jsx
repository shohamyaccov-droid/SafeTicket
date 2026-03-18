import { useState } from 'react';
import { contactAPI } from '../services/api';
import './Contact.css';

const Contact = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    order_number: '',
    message: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
    setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await contactAPI.createContactMessage(formData);
      setShowSuccess(true);
      setFormData({
        name: '',
        email: '',
        order_number: '',
        message: ''
      });
      
      // Hide success message after 5 seconds
      setTimeout(() => {
        setShowSuccess(false);
      }, 5000);
    } catch (err) {
      setError(err.response?.data?.message || 'אירעה שגיאה. אנא נסה שוב מאוחר יותר.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="contact-container">
      <div className="contact-header">
        <h1>צור קשר</h1>
        <p>אנחנו כאן לעזור לך. שלח לנו הודעה ונחזור אליך בהקדם</p>
      </div>

      {showSuccess && (
        <div className="contact-success">
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M20 6L9 17L4 12"
              stroke="#10b981"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span>פנייתך התקבלה ונחזור אליך בהקדם</span>
        </div>
      )}

      <form className="contact-form" onSubmit={handleSubmit}>
        {error && (
          <div className="contact-error">
            {error}
          </div>
        )}

        <div className="form-group">
          <label htmlFor="name">שם מלא *</label>
          <input
            type="text"
            id="name"
            name="name"
            value={formData.name}
            onChange={handleChange}
            required
            placeholder="הכנס את שמך המלא"
          />
        </div>

        <div className="form-group">
          <label htmlFor="email">אימייל *</label>
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
          <label htmlFor="order_number">מספר הזמנה (אופציונלי)</label>
          <input
            type="text"
            id="order_number"
            name="order_number"
            value={formData.order_number}
            onChange={handleChange}
            placeholder="אם יש לך מספר הזמנה, הכנס אותו כאן"
          />
        </div>

        <div className="form-group">
          <label htmlFor="message">הודעה *</label>
          <textarea
            id="message"
            name="message"
            value={formData.message}
            onChange={handleChange}
            required
            rows="6"
            placeholder="כתוב את הודעתך כאן..."
          />
        </div>

        <button
          type="submit"
          className="contact-submit-btn"
          disabled={isSubmitting}
        >
          {isSubmitting ? 'שולח...' : 'שלח הודעה'}
        </button>
      </form>
    </div>
  );
};

export default Contact;
