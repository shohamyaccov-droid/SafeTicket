import { CalendarDays, Check, CircleDollarSign, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import './TicketUploadWizard.css';
import { canGoToSellWizardStep, previousSellWizardStep } from '../utils/sellWizard';

const STEPS = [
  { id: 1, label: 'האירוע', Icon: CalendarDays },
  { id: 2, label: 'מחיר והעלאה', Icon: CircleDollarSign },
  { id: 3, label: 'חשבון', Icon: UserRound },
];

/**
 * Presentation shell for the seller funnel. Listing data remains owned by Sell,
 * so changing steps never unmounts or loses selected File objects.
 * Conversion: guests see 3 steps; logged-in sellers skip auth (step 3).
 * Stepper is backward-only so sellers can fix a mistake without losing draft state.
 */
/* eslint-disable-next-line react/prop-types */
export default function TicketUploadWizard({ step, skipAuth = false, onBack, onGoToStep, children }) {
  const visibleSteps = STEPS.filter((item) => !(skipAuth && item.id === 3));
  const visibleCount = visibleSteps.length;
  const previousStep = previousSellWizardStep(step, skipAuth);
  const displayStep = skipAuth && step > 2 ? 2 : Math.min(step, visibleCount);

  return (
    <section className="ticket-upload-wizard" aria-label="תהליך העלאת כרטיס">
      <div className="ticket-upload-wizard__topbar">
        <Link to="/" className="ticket-upload-wizard__home-link">
          חזרה לעמוד הבית של TradeTix
        </Link>
        {previousStep ? (
          <button
            type="button"
            className="ticket-upload-wizard__back-link"
            onClick={() => onBack?.(previousStep)}
          >
            ← חזרה לשלב הקודם
          </button>
        ) : null}
      </div>
      <div className="ticket-upload-wizard__progress">
        <p className="ticket-upload-wizard__eyebrow">
          שלב {displayStep} מתוך {visibleCount}
        </p>
        <ol
          className="ticket-upload-wizard__steps"
          style={{ gridTemplateColumns: `repeat(${visibleCount}, minmax(0, 1fr))` }}
        >
          {visibleSteps.map(({ id, label, Icon }) => {
            const isComplete = id < step;
            const isCurrent = id === step;
            const canGoBack = canGoToSellWizardStep(step, id, skipAuth);
            return (
              <li
                key={id}
                className={[
                  'ticket-upload-wizard__step',
                  isComplete ? 'is-complete' : '',
                  isCurrent ? 'is-current' : '',
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
                    <span>{label}</span>
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
