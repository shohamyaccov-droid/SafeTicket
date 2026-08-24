import { CalendarDays, Check, CircleDollarSign, FileUp, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import './TicketUploadWizard.css';

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
 */
/* eslint-disable-next-line react/prop-types */
export default function TicketUploadWizard({ step, skipAuth = false, children }) {
  const visibleCount = 4;
  const displayStep = step;

  return (
    <section className="ticket-upload-wizard" aria-label="תהליך העלאת כרטיס">
      <div className="ticket-upload-wizard__topbar">
        <Link to="/" className="ticket-upload-wizard__home-link">
          ← חזרה לדף הבית
        </Link>
      </div>
      <div className="ticket-upload-wizard__progress">
        <p className="ticket-upload-wizard__eyebrow">
          שלב {displayStep} מתוך {visibleCount}
        </p>
        <ol className="ticket-upload-wizard__steps">
          {STEPS.map(({ id, label, Icon }) => {
            const isSkippedAuth = skipAuth && id === 3;
            const isComplete = id < step || isSkippedAuth;
            const isCurrent = !isSkippedAuth && id === step;
            return (
              <li
                key={id}
                className={[
                  'ticket-upload-wizard__step',
                  isComplete ? 'is-complete' : '',
                  isCurrent ? 'is-current' : '',
                  isSkippedAuth ? 'is-skipped' : '',
                ].filter(Boolean).join(' ')}
                aria-current={isCurrent ? 'step' : undefined}
              >
                <span className="ticket-upload-wizard__step-icon" aria-hidden="true">
                  {isComplete ? <Check size={18} strokeWidth={3} /> : <Icon size={18} />}
                </span>
                <span>{isSkippedAuth ? `${label} (מחוברים)` : label}</span>
              </li>
            );
          })}
        </ol>
      </div>
      {children}
    </section>
  );
}
