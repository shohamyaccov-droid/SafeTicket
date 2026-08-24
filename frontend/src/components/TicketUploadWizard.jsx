import { CalendarDays, Check, CircleDollarSign, FileUp, UserRound } from 'lucide-react';
import './TicketUploadWizard.css';
import { canGoToSellWizardStep, previousSellWizardStep } from '../utils/sellWizard';

const STEPS = [
  { id: 1, label: 'האירוע', Icon: CalendarDays },
  { id: 2, label: 'מחיר ומושבים', Icon: CircleDollarSign },
  { id: 3, label: 'חשבון', Icon: UserRound },
  { id: 4, label: 'העלאת כרטיס', Icon: FileUp },
];

/**
 * Presentation shell for the seller funnel. Listing data remains owned by Sell,
 * so changing steps never unmounts or loses selected File objects.
 * Conversion: guests see all 4 steps; logged-in sellers skip auth (step 3).
 * Stepper is backward-only so sellers can fix a mistake without losing draft state.
 */
/* eslint-disable-next-line react/prop-types */
export default function TicketUploadWizard({ step, skipAuth = false, onBack, onGoToStep, children }) {
  const visibleCount = 4;
  const previousStep = previousSellWizardStep(step, skipAuth);

  return (
    <section className="ticket-upload-wizard" aria-label="תהליך העלאת כרטיס">
      <div className="ticket-upload-wizard__topbar">
        {previousStep ? (
          <button
            type="button"
            className="ticket-upload-wizard__home-link"
            onClick={() => onBack?.(previousStep)}
          >
            ← חזרה לשלב הקודם
          </button>
        ) : null}
      </div>
      <div className="ticket-upload-wizard__progress">
        <p className="ticket-upload-wizard__eyebrow">
          שלב {step} מתוך {visibleCount}
        </p>
        <ol className="ticket-upload-wizard__steps">
          {STEPS.map(({ id, label, Icon }) => {
            const isSkippedAuth = skipAuth && id === 3;
            const isComplete = id < step || isSkippedAuth;
            const isCurrent = !isSkippedAuth && id === step;
            const canGoBack = canGoToSellWizardStep(step, id, skipAuth);
            return (
              <li
                key={id}
                className={[
                  'ticket-upload-wizard__step',
                  isComplete ? 'is-complete' : '',
                  isCurrent ? 'is-current' : '',
                  isSkippedAuth ? 'is-skipped' : '',
                  canGoBack ? 'is-clickable' : '',
                ].filter(Boolean).join(' ')}
                aria-current={isCurrent ? 'step' : undefined}
              >
                {canGoBack ? (
                  <button
                    type="button"
                    className="ticket-upload-wizard__step-btn"
                    aria-label={label}
                    onClick={() => onGoToStep?.(id)}
                  >
                    <span className="ticket-upload-wizard__step-icon" aria-hidden="true">
                      {isComplete ? <Check size={18} strokeWidth={3} /> : <Icon size={18} />}
                    </span>
                    <span>{label}</span>
                  </button>
                ) : (
                  <>
                    <span className="ticket-upload-wizard__step-icon" aria-hidden="true">
                      {isComplete ? <Check size={18} strokeWidth={3} /> : <Icon size={18} />}
                    </span>
                    <span>{isSkippedAuth ? `${label} (מחוברים)` : label}</span>
                  </>
                )}
              </li>
            );
          })}
        </ol>
      </div>
      {children}
    </section>
  );
}
