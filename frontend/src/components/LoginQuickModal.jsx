/* eslint-disable react/prop-types */
import { LoginForm } from './LoginModal';
import RegisterForm from './RegisterForm';
import '../pages/Auth.css';
import './LoginQuickModal.css';

export default function LoginQuickModal({
  onClose,
  mode = 'login',
  onSwitchToLogin,
  onSwitchToRegister,
}) {
  const isRegister = mode === 'register';
  const title = isRegister ? 'הרשמה' : 'התחברות';
  const titleId = isRegister ? 'register-quick-modal-title' : 'login-quick-modal-title';

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
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" className="login-quick-modal__close" onClick={onClose} aria-label="סגירה">
          ×
        </button>
        <h2 id={titleId}>{title}</h2>
        {isRegister ? (
          <RegisterForm
            idPrefix="register-modal"
            onSuccess={onClose}
            onRequestLogin={onSwitchToLogin || onClose}
          />
        ) : (
          <>
            <LoginForm onSuccess={onClose} />
            <p className="auth-footer">
              אין לך חשבון?{' '}
              <button
                type="button"
                className="auth-text-link"
                onClick={onSwitchToRegister}
              >
                הירשם כאן
              </button>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
