import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TakenBuyButton from './TakenBuyButton';

describe('TakenBuyButton', () => {
  it('renders disabled נתפס CTA that cannot be clicked', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <div onClick={onClick}>
        <TakenBuyButton />
      </div>
    );
    const btn = screen.getByRole('button', { name: 'נתפס' });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('aria-disabled', 'true');
    expect(btn.className).toContain('viagogo-buy-button--taken');
    await user.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('renders disabled הכרטיס שלך CTA for own listings', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <div onClick={onClick}>
        <TakenBuyButton label="הכרטיס שלך" variant="own" />
      </div>
    );
    const btn = screen.getByRole('button', { name: 'הכרטיס שלך' });
    expect(btn).toBeDisabled();
    expect(btn.className).toContain('viagogo-buy-button--own');
    await user.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });
});
