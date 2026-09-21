import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MarketingConsentCheckbox, { MARKETING_CONSENT_LABEL } from './MarketingConsentCheckbox';

describe('MarketingConsentCheckbox', () => {
  it('is unchecked by default and uses the required Hebrew label', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<MarketingConsentCheckbox checked={false} onChange={onChange} />);

    const checkbox = screen.getByRole('checkbox', { name: MARKETING_CONSENT_LABEL });
    expect(checkbox).not.toBeChecked();
    expect(checkbox).not.toHaveAttribute('checked');

    await user.click(checkbox);
    expect(onChange).toHaveBeenCalledWith(true);
  });
});
