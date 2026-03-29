import { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../services/api';

const AuthContext = createContext(null);

function broadcastAuthEvent(type) {
  try {
    if (typeof BroadcastChannel === 'undefined') return;
    const ch = new BroadcastChannel('safeticket-auth');
    ch.postMessage({ type });
    ch.close();
  } catch {
    /* ignore */
  }
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const applyProfile = (response) => {
    const userData = response.data.user || response.data;
    if (userData && typeof userData.is_superuser === 'undefined') {
      userData.is_superuser = false;
    }
    if (userData && typeof userData.is_staff === 'undefined') {
      userData.is_staff = false;
    }
    setUser(userData);
  };

  useEffect(() => {
    // Auth check: NO localStorage - tokens are HttpOnly cookies.
    // Unconditionally call getProfile(); 200 = set user, 401 = set null (interceptor
    // does NOT redirect on getProfile 401 to avoid infinite loop).
    authAPI.getProfile()
      .then((response) => {
        applyProfile(response);
        setLoading(false);
      })
      .catch(() => {
        setUser(null);
        setLoading(false);
      });
  }, []);

  // Multi-tab: login/logout in another tab updates HttpOnly cookies — refresh profile from server.
  useEffect(() => {
    const ch =
      typeof BroadcastChannel !== 'undefined'
        ? new BroadcastChannel('safeticket-auth')
        : null;
    const onMessage = (ev) => {
      const t = ev?.data?.type;
      if (t === 'login' || t === 'logout') {
        authAPI
          .getProfile()
          .then((response) => applyProfile(response))
          .catch(() => setUser(null));
      }
    };
    if (ch) {
      ch.addEventListener('message', onMessage);
    }
    return () => {
      if (ch) {
        ch.removeEventListener('message', onMessage);
        ch.close();
      }
    };
  }, []);

  const login = async (username, password) => {
    try {
      // Cross-origin: establish csrftoken on API host before POST (CSRF + CORS credentials)
      await authAPI.getCsrf();
      const response = await authAPI.login({ username, password });
      // Tokens are in HttpOnly cookies; response has user only
      let user = response.data?.user;
      if (!user) {
        try {
          const profileResponse = await authAPI.getProfile();
          user = profileResponse.data.user || profileResponse.data;
        } catch {
          user = { username: username, is_superuser: false, is_staff: false };
        }
      }
      if (user && typeof user.is_superuser === 'undefined') {
        user.is_superuser = false;
      }
      if (user && typeof user.is_staff === 'undefined') {
        user.is_staff = false;
      }
      setUser(user);
      broadcastAuthEvent('login');
      return { success: true };
    } catch (error) {
      console.error('FULL LOGIN ERROR:', error);
      // Network/CORS errors: error.response is undefined
      if (!error.response || error.message === 'Network Error') {
        return { success: false, error: 'שגיאת תקשורת עם השרת' };
      }
      // 500 or HTML/undefined response - server error
      const status = error.response?.status;
      const data = error.response?.data;
      const is500 = status === 500;
      const isHtml = typeof data === 'string' && data.trim().startsWith('<');
      if (is500 || isHtml || (status >= 500 && (data === undefined || data === null))) {
        return { success: false, error: 'שגיאת שרת פנימית (500) או שגיאה לא ידועה.' };
      }
      let errorMessage = 'שם משתמש או סיסמה אינם נכונים';
      if (typeof data?.detail === 'string') {
        errorMessage = data.detail;
      } else if (Array.isArray(data?.non_field_errors) && data.non_field_errors.length > 0) {
        errorMessage = data.non_field_errors[0];
      } else if (data?.error) {
        errorMessage = typeof data.error === 'string' ? data.error : data.error?.message || errorMessage;
      } else if (data?.message) {
        errorMessage = data.message;
      } else if (error.message) {
        errorMessage = error.message;
      }
      return { success: false, error: errorMessage };
    }
  };

  const register = async (userData) => {
    try {
      await authAPI.getCsrf();
      const response = await authAPI.register(userData);
      const newUser = response.data?.user;
      if (newUser && typeof newUser.is_superuser === 'undefined') {
        newUser.is_superuser = false;
      }
      if (newUser && typeof newUser.is_staff === 'undefined') {
        newUser.is_staff = false;
      }
      setUser(newUser || response.data);
      broadcastAuthEvent('login');
      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data || { message: 'Registration failed' },
      };
    }
  };

  const logout = async () => {
    try {
      await authAPI.getCsrf();
      await authAPI.logout();
    } catch {
      // Ignore - cookies may already be cleared
    }
    setUser(null);
    broadcastAuthEvent('logout');
  };

  const refreshProfile = async () => {
    try {
      const response = await authAPI.getProfile();
      applyProfile(response);
    } catch {
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshProfile }}>
      {children}
    </AuthContext.Provider>
  );
};

