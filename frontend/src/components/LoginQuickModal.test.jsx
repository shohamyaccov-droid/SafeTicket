import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import LoginQuickModal from './LoginQuickModal';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ login: vi.fn() }),
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
  });
});
