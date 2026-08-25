/* eslint-disable react/prop-types */
import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import LoginQuickModal from '../components/LoginQuickModal';

const AuthModalContext = createContext(null);

export function useAuthModal() {
  const ctx = useContext(AuthModalContext);
  if (!ctx) {
    return {
      mode: null,
      openLogin: () => {},
      openRegister: () => {},
      closeAuthModal: () => {},
    };
  }
  return ctx;
}

export function AuthModalProvider({ children }) {
  const [mode, setMode] = useState(null);

  const openLogin = useCallback(() => setMode('login'), []);
  const openRegister = useCallback(() => setMode('register'), []);
  const closeAuthModal = useCallback(() => setMode(null), []);

  const value = useMemo(
    () => ({ mode, openLogin, openRegister, closeAuthModal }),
    [mode, openLogin, openRegister, closeAuthModal],
  );

  return (
    <AuthModalContext.Provider value={value}>
      {children}
      {mode ? (
        <LoginQuickModal
          mode={mode}
          onClose={closeAuthModal}
          onSwitchToLogin={openLogin}
          onSwitchToRegister={openRegister}
        />
      ) : null}
    </AuthModalContext.Provider>
  );
}
