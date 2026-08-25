/* eslint-disable react/prop-types */
import { Link, useLocation } from 'react-router-dom';
import { LoginForm } from './LoginModal';
import '../pages/Auth.css';
import './LoginQuickModal.css';

export default function LoginQuickModal({ onClose }) {
  const location = useLocation();
  const returnTo = `${location.pathname}${location.search}${location.hash}` || '/';
  const registerTo = `/register?returnTo=${encodeURIComponent(returnTo)}`;

  return (
    <div
      className="login-quick-modal-overlay"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="login-quick-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="login-quick-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" className="login-quick-modal__close" onClick={onClose} aria-label="סגירה">
          ×
        </button>
        <h2 id="login-quick-modal-title">התחברות</h2>
        <LoginForm onSuccess={onClose} />
        <p className="auth-footer">
          אין לך חשבון? <Link to={registerTo} onClick={onClose}>הירשם כאן</Link>
        </p>
      </div>
    </div>
  );
}
