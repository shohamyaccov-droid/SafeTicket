import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './ProtectedRoute.css';

/**
 * Protects routes that require authentication.
 * Fixes the "flash of unauthenticated state" on refresh:
 * - While auth is loading (getProfile with HttpOnly cookies), show a spinner.
 * - Only redirect to login when !loading && !user.
 */
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="protected-route-loading" aria-live="polite">
        <div className="protected-route-spinner" />
        <p>טוען...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

export default ProtectedRoute;
