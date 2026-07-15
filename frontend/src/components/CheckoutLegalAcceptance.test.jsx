import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CheckoutLegalAcceptance, { validateLegalAcceptance } from './CheckoutLegalAcceptance';

describe('validateLegalAcceptance', () => {
  it('blocks when unchecked and passes when checked', () => {
    expect(validateLegalAcceptance(false)).toMatch(/תקנון/);
    expect(validateLegalAcceptance(true)).toBe('');
  });
});

describe('CheckoutLegalAcceptance', () => {
  it('requires checkbox before success path and links open in new tab', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { rerender } = render(
      <CheckoutLegalAcceptance checked={false} onChange={onChange} error="" />
    );

    const terms = screen.getByRole('link', { name: 'התקנון' });
    const refunds = screen.getByRole('link', { name: 'מדיניות ההחזרים' });
    expect(terms).toHaveAttribute('href', '/terms');
    expect(terms).toHaveAttribute('target', '_blank');
    expect(refunds).toHaveAttribute('href', '/refunds');
    expect(refunds).toHaveAttribute('target', '_blank');

    expect(validateLegalAcceptance(false)).not.toBe('');

    const checkbox = screen.getByRole('checkbox');
    await user.click(checkbox);
    expect(onChange).toHaveBeenCalledWith(true);

    rerender(<CheckoutLegalAcceptance checked onChange={onChange} error="" />);
    expect(validateLegalAcceptance(true)).toBe('');
  });

  it('shows error message when provided', () => {
    render(
      <CheckoutLegalAcceptance
        checked={false}
        onChange={() => {}}
        error="יש לאשר את התקנון ומדיניות ההחזרים לפני המשך לתשלום."
      />
    );
    expect(screen.getByRole('alert')).toHaveTextContent('יש לאשר');
  });
});
