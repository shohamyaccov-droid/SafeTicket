/**
 * Split-view admin review: ticket file on the left, גוש/שורה/כיסא on the right.
 */
/* eslint-disable react/prop-types */
import { useEffect, useMemo, useState } from 'react';
import {
  listingGroupTickets,
  seatingAssignmentsForGroup,
  seatingFromTicket,
  ticketFileKind,
  venueSectionNamesForTicket,
} from '../utils/adminTicketSeating';
import './AdminReviewModal.css';

export default function AdminReviewModal({
  ticket,
  tickets = [],
  busy = false,
  onClose,
  onSave,
  onApprove,
}) {
  const group = useMemo(() => listingGroupTickets(tickets, ticket), [tickets, ticket]);
  const [previewId, setPreviewId] = useState(ticket?.id);
  const [values, setValues] = useState(() => seatingFromTicket(ticket));

  useEffect(() => {
    setPreviewId(ticket?.id);
    setValues(seatingFromTicket(ticket));
  }, [ticket]);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape' && !busy) onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onClose]);

  if (!ticket) return null;

  const previewTicket = group.find((row) => Number(row.id) === Number(previewId)) || ticket;
  const fileUrl = previewTicket.ticket_file_url || previewTicket.pdf_file_url || '';
  const kind = ticketFileKind(previewTicket);
  const sectionNames = venueSectionNamesForTicket(ticket);
  const selectOptions = sectionNames.includes(values.section) || !values.section
    ? sectionNames
    : [values.section, ...sectionNames];
  const assignments = seatingAssignmentsForGroup({
    tickets: group,
    anchorId: ticket.id,
    section: values.section,
    row: values.row,
    seat: values.seat,
  });
  const isGroup = group.length > 1;

  const patch = (partial) => setValues((prev) => ({ ...prev, ...partial }));

  return (
    <div className="admin-review-overlay" role="presentation" onClick={() => !busy && onClose?.()}>
      <div
        className="admin-review-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="admin-review-title"
        dir="rtl"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="admin-review-header">
          <div>
            <h2 id="admin-review-title">בדיקה ואישור</h2>
            <p className="admin-review-event">
              {ticket.event?.name || ticket.event_name || '—'}
              {isGroup ? ` · ${group.length} כרטיסים באותה העלאה` : ''}
            </p>
          </div>
          <button type="button" className="admin-review-close" onClick={onClose} disabled={busy} aria-label="סגור">
            ×
          </button>
        </header>

        <div className="admin-review-split">
          <section className="admin-review-preview" aria-label="קובץ כרטיס">
            {isGroup ? (
              <div className="admin-review-ticket-switch" role="tablist" aria-label="כרטיסים בקבוצה">
                {group.map((row, index) => (
                  <button
                    key={row.id}
                    type="button"
                    role="tab"
                    aria-selected={Number(previewId) === Number(row.id)}
                    className={
                      Number(previewId) === Number(row.id)
                        ? 'admin-review-ticket-chip admin-review-ticket-chip--active'
                        : 'admin-review-ticket-chip'
                    }
                    onClick={() => setPreviewId(row.id)}
                  >
                    כרטיס {index + 1}
                  </button>
                ))}
              </div>
            ) : null}
            {fileUrl ? (
              kind === 'image' ? (
                <img className="admin-review-image" src={fileUrl} alt={`כרטיס #${previewTicket.id}`} />
              ) : (
                <iframe
                  className="admin-review-frame"
                  title={`תצוגת כרטיס #${previewTicket.id}`}
                  src={fileUrl}
                />
              )
            ) : (
              <p className="admin-review-missing">אין קובץ כרטיס להצגה</p>
            )}
          </section>

          <section className="admin-review-form" aria-label="פרטי מושב">
            <label className="admin-review-field">
              <span>גוש</span>
              {selectOptions.length > 0 ? (
                <select
                  value={values.section}
                  onChange={(event) => patch({ section: event.target.value })}
                  disabled={busy}
                  aria-label="גוש"
                >
                  <option value="">בחירת גוש</option>
                  {selectOptions.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={values.section}
                  onChange={(event) => patch({ section: event.target.value })}
                  placeholder="אין גושים ממופים — הזנה ידנית"
                  disabled={busy}
                  autoComplete="off"
                  aria-label="גוש"
                />
              )}
            </label>
            <label className="admin-review-field">
              <span>שורה</span>
              <input
                type="text"
                value={values.row}
                onChange={(event) => patch({ row: event.target.value })}
                placeholder="למשל 5"
                disabled={busy}
                autoComplete="off"
                aria-label="שורה"
              />
            </label>
            <label className="admin-review-field">
              <span>{isGroup ? 'כיסא (ראשון שנבחר)' : 'כיסא'}</span>
              <input
                type="text"
                value={values.seat}
                onChange={(event) => patch({ seat: event.target.value })}
                placeholder="למשל 12"
                disabled={busy}
                autoComplete="off"
                aria-label="כיסא"
              />
            </label>

            {isGroup ? (
              <div className="admin-review-bulk" data-testid="admin-review-bulk-preview">
                <p className="admin-review-bulk-lead">
                  אותו גוש ושורה יוחלו על כל הכרטיסים. מספרי הכיסאות יעלו אוטומטית.
                </p>
                <ul>
                  {assignments.map((row, index) => (
                    <li key={row.ticketId}>
                      כרטיס {index + 1} (#{row.ticketId}): גוש {row.section || '—'} · שורה {row.row || '—'} · כיסא{' '}
                      {row.seat || '—'}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="admin-review-actions">
              <button
                type="button"
                className="admin-review-save"
                disabled={busy}
                onClick={() => onSave?.(ticket, values, { applyToGroup: isGroup })}
              >
                {busy ? 'שומר…' : 'שמור'}
              </button>
              <button
                type="button"
                className="admin-review-approve"
                disabled={busy}
                onClick={() =>
                  onApprove?.(ticket, values, { applyToGroup: isGroup, approveGroup: isGroup })
                }
              >
                {busy ? 'מאשר…' : isGroup ? 'אישור ופרסום לכל הקבוצה' : 'אישור ופרסום'}
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
