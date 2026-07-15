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
    await user.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });
});
