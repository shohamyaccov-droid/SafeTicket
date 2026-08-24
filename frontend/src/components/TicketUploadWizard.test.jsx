import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import TicketUploadWizard from './TicketUploadWizard';

afterEach(() => {
  cleanup();
});

describe('TicketUploadWizard navigation', () => {
  it('goes to the previous step instead of the homepage', async () => {
    const onBack = vi.fn();
    const user = userEvent.setup();
    render(
      <TicketUploadWizard step={3} skipAuth={false} onBack={onBack} onGoToStep={() => {}}>
        <p>תוכן</p>
      </TicketUploadWizard>,
    );
    await user.click(screen.getByRole('button', { name: '← חזרה לשלב הקודם' }));
    expect(onBack).toHaveBeenCalledWith(2);
    expect(screen.queryByRole('link', { name: /דף הבית/ })).not.toBeInTheDocument();
  });

  it('lets a guest on account creation click Event Details to go back', async () => {
    const onGoToStep = vi.fn();
    const user = userEvent.setup();
    render(
      <TicketUploadWizard step={3} skipAuth={false} onBack={() => {}} onGoToStep={onGoToStep}>
        <p>תוכן</p>
      </TicketUploadWizard>,
    );
    await user.click(screen.getByRole('button', { name: /האירוע/ }));
    expect(onGoToStep).toHaveBeenCalledWith(1);
  });

  it('does not let users jump forward via the stepper', () => {
    render(
      <TicketUploadWizard step={2} skipAuth={false} onBack={() => {}} onGoToStep={() => {}}>
        <p>תוכן</p>
      </TicketUploadWizard>,
    );
    expect(screen.queryByRole('button', { name: /העלאת כרטיס/ })).not.toBeInTheDocument();
  });

  it('hides the previous-step control on the first step', () => {
    render(
      <TicketUploadWizard step={1} skipAuth={false} onBack={() => {}} onGoToStep={() => {}}>
        <p>תוכן</p>
      </TicketUploadWizard>,
    );
    expect(screen.queryByRole('button', { name: '← חזרה לשלב הקודם' })).not.toBeInTheDocument();
  });

  it('keeps parent form state when going back via the stepper', async () => {
    const user = userEvent.setup();
    function Harness() {
      const [step, setStep] = useState(3);
      const [price, setPrice] = useState('120');
      return (
        <TicketUploadWizard step={step} skipAuth={false} onBack={setStep} onGoToStep={setStep}>
          <label htmlFor="draft-price">מחיר</label>
          <input id="draft-price" value={price} onChange={(e) => setPrice(e.target.value)} />
        </TicketUploadWizard>
      );
    }
    render(<Harness />);
    await user.click(screen.getByRole('button', { name: /האירוע/ }));
    expect(screen.getByLabelText('מחיר')).toHaveValue('120');
  });
});
