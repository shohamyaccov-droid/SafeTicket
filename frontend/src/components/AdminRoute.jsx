import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './ProtectedRoute.css';

/** Staff or superuser only (TradeTix admin control panel). */
const AdminRoute = ({ children }) => {
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

  if (!user.is_staff && !user.is_superuser) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

export default AdminRoute;
