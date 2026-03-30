import { createContext, useContext, useState, useEffect } from 'react';
import api, {
  authAPI,
  resetCsrfTokenCache,
  setBearerFallback,
  clearBearerFallback,
} from '../services/api';

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
    // JWT in localStorage + Bearer header; getProfile() 200 = logged in, 401 = guest.
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
    let lastError = null;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        if (attempt > 0) {
          resetCsrfTokenCache();
          await new Promise((r) => setTimeout(r, 350 * attempt));
        }
        // Cross-origin: establish csrftoken on API host before POST (CSRF + CORS credentials)
        await authAPI.getCsrf();
        const response = await authAPI.login({ username, password });
        const access = response.data?.access;
        const refresh = response.data?.refresh;
        if (access) {
          setBearerFallback(access, refresh);
          api.defaults.headers.common.Authorization = `Bearer ${access}`;
        }
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
        lastError = error;
        const status = error.response?.status;
        if (status === 403 && attempt < 2) {
          continue;
        }
        break;
      }
    }

    const error = lastError;
    if (!error) {
      return { success: false, error: 'שגיאת התחברות' };
    }
    // Network/CORS: keep technical string on `error` for LoginForm debug toast
    if (!error.response || error.message === 'Network Error') {
      const technical =
        error.message ||
        (typeof error === 'string' ? error : 'Network Error — no response (check CORS)');
      return { success: false, error: technical, errorHebrew: 'שגיאת תקשורת עם השרת' };
    }
    // 5xx / HTML — surface API detail when present (debug: "Server Crash: ..." from backend)
    const status = error.response?.status;
    const data = error.response?.data;
    const isHtml = typeof data === 'string' && data.trim().startsWith('<');
    if ((status != null && status >= 500) || isHtml) {
      let detailStr = null;
      if (data && typeof data === 'object' && data.detail != null) {
        if (typeof data.detail === 'string') {
          detailStr = data.detail;
        } else if (Array.isArray(data.detail) && data.detail.length > 0) {
          detailStr = data.detail
            .map((x) => (typeof x === 'string' ? x : JSON.stringify(x)))
            .join('; ');
        }
      }
      return {
        success: false,
        error: detailStr || 'שגיאת שרת פנימית (500) או שגיאה לא ידועה.',
      };
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
  };

  const register = async (userData) => {
    let lastError = null;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        if (attempt > 0) {
          resetCsrfTokenCache();
          await new Promise((r) => setTimeout(r, 350 * attempt));
        }
        await authAPI.getCsrf();
        const response = await authAPI.register(userData);
        if (response.data?.access) {
          setBearerFallback(response.data.access, response.data.refresh);
        }
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
        lastError = error;
        if (error.response?.status === 403 && attempt < 2) {
          continue;
        }
        break;
      }
    }
    return {
      success: false,
      error: lastError?.response?.data || { message: 'Registration failed' },
    };
  };

  const logout = async () => {
    try {
      await authAPI.getCsrf();
      await authAPI.logout();
    } catch {
      // Ignore - cookies may already be cleared
    }
    clearBearerFallback();
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

