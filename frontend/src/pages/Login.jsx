import { Link } from 'react-router-dom';
import { LoginForm } from '../components/LoginModal';
import './Auth.css';

const Login = () => {
  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>התחברות</h2>
        <LoginForm />
        <p className="auth-footer">
          אין לך חשבון? <Link to="/register">הירשם כאן</Link>
        </p>
      </div>
    </div>
  );
};

export default Login;
