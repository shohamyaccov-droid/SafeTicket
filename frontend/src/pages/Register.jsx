import { useAuthModal } from '../context/AuthModalContext';
import RegisterForm from '../components/RegisterForm';
import './Auth.css';

const Register = () => {
  const { openLogin } = useAuthModal();

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>הרשמה</h2>
        <RegisterForm onRequestLogin={openLogin} />
      </div>
    </div>
  );
};

export default Register;
