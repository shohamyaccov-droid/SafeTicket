import { LoginForm } from '../components/LoginModal';
import { useAuthModal } from '../context/AuthModalContext';
import PageSeo from '../components/PageSeo';
import { getStaticPageMeta, staticPageBreadcrumbs } from '../content/staticPageMeta';
import './Auth.css';

const Login = () => {
  const { openRegister } = useAuthModal();
  const meta = getStaticPageMeta('/login');

  return (
    <div className="auth-container">
      <PageSeo
        title={meta.title}
        description={meta.description}
        path="/login"
        breadcrumbs={staticPageBreadcrumbs('/login')}
        robots="noindex, nofollow"
      />
      <section className="auth-card">
        <h1>התחברות</h1>
        <LoginForm />
        <p className="auth-footer">
          אין לך חשבון?{' '}
          <button type="button" className="auth-text-link" onClick={openRegister}>
            הירשם כאן
          </button>
        </p>
      </section>
    </div>
  );
};

export default Login;
