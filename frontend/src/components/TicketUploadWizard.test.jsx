import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { MemoryRouter } from 'react-router-dom';
import TicketUploadWizard from './TicketUploadWizard';

afterEach(() => {
  cleanup();
});

function renderWizard(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe('TicketUploadWizard navigation', () => {
  it('always offers a homepage exit and goes to the previous step separately', async () => {
    const onBack = vi.fn();
    const user = userEvent.setup();
    renderWizard(
      <TicketUploadWizard step={3} skipAuth={false} onBack={onBack} onGoToStep={() => {}}>
        <p>תוכן</p>
      </TicketUploadWizard>,
    );
    expect(screen.getByRole('link', { name: 'חזרה לעמוד הבית של TradeTix' })).toHaveAttribute('href', '/');
    await user.click(screen.getByRole('button', { name: '← חזרה לשלב הקודם' }));
    expect(onBack).toHaveBeenCalledWith(2);
  });

  it('lets a guest on account creation click Event Details to go back', async () => {
    const onGoToStep = vi.fn();
    const user = userEvent.setup();
    renderWizard(
      <TicketUploadWizard step={3} skipAuth={false} onBack={() => {}} onGoToStep={onGoToStep}>
        <p>תוכן</p>
      </TicketUploadWizard>,
    );
    await user.click(screen.getByRole('button', { name: /האירוע/ }));
    expect(onGoToStep).toHaveBeenCalledWith(1);
  });

  it('does not let users jump forward via the stepper', () => {
    renderWizard(
      <TicketUploadWizard step={2} skipAuth={false} onBack={() => {}} onGoToStep={() => {}}>
        <p>תוכן</p>
      </TicketUploadWizard>,
    );
    expect(screen.queryByRole('button', { name: /חשבון/ })).not.toBeInTheDocument();
    expect(screen.getByText('שלב 2 מתוך 3')).toBeInTheDocument();
  });

  it('hides the previous-step control on the first step but keeps the homepage link', () => {
    renderWizard(
      <TicketUploadWizard step={1} skipAuth={false} onBack={() => {}} onGoToStep={() => {}}>
        <p>תוכן</p>
      </TicketUploadWizard>,
    );
    expect(screen.queryByRole('button', { name: '← חזרה לשלב הקודם' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'חזרה לעמוד הבית של TradeTix' })).toBeInTheDocument();
  });

  it('shows two steps when the seller is already logged in', () => {
    renderWizard(
      <TicketUploadWizard step={2} skipAuth onBack={() => {}} onGoToStep={() => {}}>
        <p>תוכן</p>
      </TicketUploadWizard>,
    );
    expect(screen.getByText('שלב 2 מתוך 2')).toBeInTheDocument();
    expect(screen.queryByText('חשבון')).not.toBeInTheDocument();
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
    renderWizard(<Harness />);
    await user.click(screen.getByRole('button', { name: /האירוע/ }));
    expect(screen.getByLabelText('מחיר')).toHaveValue('120');
  });
});
