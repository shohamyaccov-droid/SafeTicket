/**
 * Split-view admin review: ticket file on the left, גוש/שורה/כיסא on the right.
 */
/* eslint-disable react/prop-types */
import { useEffect, useMemo, useState } from 'react';
import {
  fillSequentialSeatsByTicketId,
  initialSeatsByTicketId,
  listingGroupTickets,
  matchZoneFromOcr,
  seatForTicket,
  seatingFromTicket,
  ticketFileKind,
  venueSectionNamesForTicket,
} from '../utils/adminTicketSeating';
import './AdminReviewModal.css';
import { useBodyScrollLock } from '../hooks/useBodyScrollLock';

const EMPTY_TICKETS = [];

export default function AdminReviewModal({
  ticket,
  tickets = EMPTY_TICKETS,
  sectionNames: sectionNamesProp,
  busy = false,
  onClose,
  onSave,
  onApprove,
}) {
  useBodyScrollLock(true);
  const group = useMemo(() => listingGroupTickets(tickets, ticket), [tickets, ticket]);
  const groupIds = useMemo(() => group.map((row) => row.id).join(','), [group]);
  const [previewId, setPreviewId] = useState(ticket?.id);
  const sectionNames = useMemo(() => {
    if (Array.isArray(sectionNamesProp) && sectionNamesProp.length > 0) {
      return [...new Set(sectionNamesProp.map((name) => String(name || '').trim()).filter(Boolean))];
    }
    return venueSectionNamesForTicket(ticket);
  }, [sectionNamesProp, ticket]);
  const [values, setValues] = useState(() => {
    const next = seatingFromTicket(ticket);
    next.seatsByTicketId = initialSeatsByTicketId(group, next.seat);
    return next;
  });

  useEffect(() => {
    setPreviewId(ticket?.id);
    const next = seatingFromTicket(ticket);
    const zones =
      Array.isArray(sectionNamesProp) && sectionNamesProp.length > 0
        ? sectionNamesProp
        : venueSectionNamesForTicket(ticket);
    if (!next.section) {
      const hit = matchZoneFromOcr(ticket?.extracted_pdf_text, zones);
      if (hit) next.section = hit;
    }
    next.seatsByTicketId = initialSeatsByTicketId(group, next.seat);
    setValues(next);
  }, [ticket, sectionNamesProp, groupIds]);

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
  const selectOptions = sectionNames.includes(values.section) || !values.section
    ? sectionNames
    : [values.section, ...sectionNames];
  const isGroup = group.length > 1;

  const patch = (partial) => setValues((prev) => ({ ...prev, ...partial }));

  const handleGlobalSeatChange = (seat) => {
    setValues((prev) => ({
      ...prev,
      seat,
      seatsByTicketId: fillSequentialSeatsByTicketId(group, seat),
    }));
  };

  const handleTicketSeatChange = (ticketId, seat) => {
    setValues((prev) => ({
      ...prev,
      seatsByTicketId: { ...prev.seatsByTicketId, [ticketId]: seat },
    }));
  };

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
                inputMode="numeric"
                value={values.seat}
                onChange={(event) => handleGlobalSeatChange(event.target.value)}
                placeholder="למשל 12"
                disabled={busy}
                autoComplete="off"
                aria-label="כיסא"
              />
            </label>

            {isGroup ? (
              <div className="admin-review-bulk" data-testid="admin-review-bulk-preview">
                <p className="admin-review-bulk-lead">
                  אותו גוש ושורה יוחלו על כל הכרטיסים. מספר הכיסא הראשון ממלא את כולם ברצף —
                  אפשר לתקן כיסא בודד כאן בלי לשנות את השאר.
                </p>
                <ul className="admin-review-seat-list">
                  {group.map((row, index) => (
                    <li key={row.id} className="admin-review-seat-row">
                      <span>
                        כרטיס {index + 1} (#{row.id}): גוש {values.section || '—'} · שורה {values.row || '—'} · כיסא
                      </span>
                      <input
                        type="text"
                        inputMode="numeric"
                        className="admin-review-seat-input"
                        value={seatForTicket(values.seatsByTicketId, row.id)}
                        onChange={(event) => handleTicketSeatChange(row.id, event.target.value)}
                        disabled={busy}
                        autoComplete="off"
                        aria-label={`כיסא לכרטיס ${index + 1}`}
                      />
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
