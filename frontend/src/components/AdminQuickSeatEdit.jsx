/**
 * Inline גוש/שורה editors for the admin pending-ticket queue.
 */
/* eslint-disable react/prop-types */
import './AdminQuickSeatEdit.css';

export default function AdminQuickSeatEdit({ values, onChange, disabled = false }) {
  return (
    <div className="admin-quick-seat" dir="rtl">
      <label className="admin-quick-seat-field">
        <span>גוש</span>
        <input
          type="text"
          value={values.section}
          onChange={(event) => onChange({ ...values, section: event.target.value })}
          placeholder="למשל 12 / דשא"
          disabled={disabled}
          autoComplete="off"
          aria-label="גוש"
        />
      </label>
      <label className="admin-quick-seat-field">
        <span>שורה</span>
        <input
          type="text"
          value={values.row}
          onChange={(event) => onChange({ ...values, row: event.target.value })}
          placeholder="למשל 5"
          disabled={disabled}
          autoComplete="off"
          aria-label="שורה"
        />
      </label>
    </div>
  );
}
