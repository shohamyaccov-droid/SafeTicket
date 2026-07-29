import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import LaunchPromoBanner from './LaunchPromoBanner';

afterEach(() => cleanup());

describe('LaunchPromoBanner', () => {
  it('renders text when active', () => {
    render(<LaunchPromoBanner text="מבצע בדיקה" isActive />);
    expect(screen.getByRole('status')).toHaveTextContent('מבצע בדיקה');
  });

  it('hides when inactive or empty', () => {
    const { rerender } = render(<LaunchPromoBanner text="מבצע בדיקה" isActive={false} />);
    expect(screen.queryByRole('status')).toBeNull();

    rerender(<LaunchPromoBanner text="   " isActive />);
    expect(screen.queryByRole('status')).toBeNull();
  });
});
