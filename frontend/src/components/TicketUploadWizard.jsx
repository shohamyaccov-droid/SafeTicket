import { Check, FileUp, ShieldCheck, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import './TicketUploadWizard.css';

const STEPS = [
  { id: 1, label: 'פרטי הכרטיס', Icon: FileUp },
  { id: 2, label: 'מחיר ואישור', Icon: ShieldCheck },
  { id: 3, label: 'חשבון ופרסום', Icon: UserRound },
];

/**
 * Presentation shell for the seller funnel. Listing data remains owned by Sell,
 * so changing steps never unmounts or loses selected File objects.
 */
/* eslint-disable-next-line react/prop-types */
export default function TicketUploadWizard({ step, children }) {
  return (
    <section className="ticket-upload-wizard" aria-label="תהליך העלאת כרטיס">
      <div className="ticket-upload-wizard__topbar">
        <Link to="/" className="ticket-upload-wizard__home-link">
          ← חזרה לדף הבית
        </Link>
      </div>
      <div className="ticket-upload-wizard__progress">
        <p className="ticket-upload-wizard__eyebrow">שלב {step} מתוך {STEPS.length}</p>
        <ol className="ticket-upload-wizard__steps">
          {STEPS.map(({ id, label, Icon }) => {
            const isComplete = id < step;
            const isCurrent = id === step;
            return (
              <li
                key={id}
                className={[
                  'ticket-upload-wizard__step',
                  isComplete ? 'is-complete' : '',
                  isCurrent ? 'is-current' : '',
                ].filter(Boolean).join(' ')}
                aria-current={isCurrent ? 'step' : undefined}
              >
                <span className="ticket-upload-wizard__step-icon" aria-hidden="true">
                  {isComplete ? <Check size={18} strokeWidth={3} /> : <Icon size={18} />}
                </span>
                <span>{label}</span>
              </li>
            );
          })}
        </ol>
      </div>
      {children}
    </section>
  );
}
