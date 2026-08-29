import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import LoginQuickModal from './LoginQuickModal';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ login: vi.fn(), register: vi.fn() }),
}));

afterEach(() => {
  cleanup();
});

describe('LoginQuickModal', () => {
  it('renders a login dialog guests can submit', () => {
    render(
      <MemoryRouter>
        <LoginQuickModal onClose={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByRole('dialog', { name: 'התחברות' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'התחברות' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'הירשם כאן' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /הירשם כאן/ })).not.toBeInTheDocument();
  });

  it('renders registration as a modal overlay instead of navigating away', () => {
    render(
      <MemoryRouter>
        <LoginQuickModal mode="register" onClose={vi.fn()} onSwitchToLogin={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByRole('dialog', { name: 'הרשמה' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'הרשמה' })).toBeInTheDocument();
    expect(screen.getByLabelText('שם פרטי')).toBeInTheDocument();
    expect(screen.getByLabelText('שם פרטי')).not.toBeRequired();
    expect(screen.getByLabelText('מספר טלפון *')).toBeRequired();
    expect(screen.getByRole('button', { name: 'הרשמה' })).toBeDisabled();
    expect(screen.queryByRole('link', { name: /הירשם כאן/ })).not.toBeInTheDocument();
  });
});
