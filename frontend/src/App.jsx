import { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import api, { authAPI } from './services/api';
import ProtectedRoute from './components/ProtectedRoute';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import EventGroupPage from './pages/EventGroupPage';
import EventDetailsPage from './pages/EventDetailsPage';
import TicketSelectionPage from './pages/TicketSelectionPage';
import ArtistEventsPage from './pages/ArtistEventsPage';
import Login from './pages/Login';
import Register from './pages/Register';
import Sell from './pages/Sell';
import Profile from './pages/Profile';
import Dashboard from './pages/Dashboard';
import AdminVerificationPage from './pages/AdminVerificationPage';
import AdminDashboard from './pages/AdminDashboard';
import AdminRoute from './components/AdminRoute';
import FAQ from './pages/FAQ';
import Contact from './pages/Contact';
import TermsPage from './pages/TermsPage';
import RefundsPage from './pages/RefundsPage';
import FloatingWhatsApp from './components/FloatingWhatsApp';
import Footer from './components/Footer';
import ScrollToTop from './components/ScrollToTop';
import './App.css';

function App() {
  useEffect(() => {
    authAPI.getCsrf().catch(() => {});
  }, []);

  /**
   * Keep-alive: lightweight GET every 5 min while tab visible to reduce Render cold starts.
   * Uses /api/health/ (no auth); CSRF warmup stays on mount above.
   */
  useEffect(() => {
    const INTERVAL_MS = 5 * 60 * 1000;
    const ping = () => {
      if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return;
      api.get('/health/').catch(() => {});
    };
    const id = window.setInterval(ping, INTERVAL_MS);
    return () => window.clearInterval(id);
  }, []);

  return (
    <AuthProvider>
      <Router>
        <ScrollToTop />
        <div className="App">
          <Navbar />
          <main>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/artist/:artistId" element={<ArtistEventsPage />} />
              <Route path="/event/:eventId" element={<EventDetailsPage />} />
              <Route path="/event-group/:eventName" element={<EventGroupPage />} />
              <Route path="/ticket/:ticketId" element={<TicketSelectionPage />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/sell" element={<Sell />} />
              <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
              <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
              <Route
                path="/admin-panel"
                element={
                  <AdminRoute>
                    <AdminDashboard />
                  </AdminRoute>
                }
              />
              <Route path="/admin/verification" element={<AdminVerificationPage />} />
              <Route path="/faq" element={<FAQ />} />
              <Route path="/contact" element={<Contact />} />
              <Route path="/terms" element={<TermsPage />} />
              <Route path="/refunds" element={<RefundsPage />} />
            </Routes>
          </main>
          <Footer />
          <FloatingWhatsApp />
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
