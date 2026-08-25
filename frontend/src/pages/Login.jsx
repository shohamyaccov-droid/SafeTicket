import { LoginForm } from '../components/LoginModal';
import { useAuthModal } from '../context/AuthModalContext';
import './Auth.css';

const Login = () => {
  const { openRegister } = useAuthModal();

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>התחברות</h2>
        <LoginForm />
        <p className="auth-footer">
          אין לך חשבון?{' '}
          <button type="button" className="auth-text-link" onClick={openRegister}>
            הירשם כאן
          </button>
        </p>
      </div>
    </div>
  );
};

export default Login;
