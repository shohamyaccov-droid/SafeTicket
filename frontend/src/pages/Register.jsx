import { useAuthModal } from '../context/AuthModalContext';
import RegisterForm from '../components/RegisterForm';
import PageSeo from '../components/PageSeo';
import { getStaticPageMeta, staticPageBreadcrumbs } from '../content/staticPageMeta';
import './Auth.css';

const Register = () => {
  const { openLogin } = useAuthModal();
  const meta = getStaticPageMeta('/register');

  return (
    <div className="auth-container">
      <PageSeo
        title={meta.title}
        description={meta.description}
        path="/register"
        breadcrumbs={staticPageBreadcrumbs('/register')}
        robots="noindex, nofollow"
      />
      <section className="auth-card">
        <h1>הרשמה</h1>
        <RegisterForm onRequestLogin={openLogin} />
      </section>
    </div>
  );
};

export default Register;
