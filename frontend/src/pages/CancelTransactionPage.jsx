import { useState } from 'react';
import { Link } from 'react-router-dom';
import { contactAPI } from '../services/api';
import { apiErrorMessageHe } from '../utils/apiErrors';
import PageSeo from '../components/PageSeo';
import { getStaticPageMeta, staticPageBreadcrumbs } from '../content/staticPageMeta';
import './Terms.css';
import './Contact.css';

const INITIAL = {
  fullName: '',
  idNumber: '',
  orderOrPhone: '',
  reason: '',
};

/**
 * מדיניות ביטולים + טופס ביטול עסקה (חוק הגנת הצרכן / תקנות ביטול עסקה).
 */
export default function CancelTransactionPage() {
  const meta = getStaticPageMeta('/cancel-transaction');
  const [form, setForm] = useState(INITIAL);
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const onChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError('');
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    setSuccess(false);
    try {
      const message = [
        'בקשת ביטול עסקה (טופס /cancel-transaction)',
        `שם מלא: ${form.fullName.trim()}`,
        `תעודת זהות: ${form.idNumber.trim()}`,
        `מספר הזמנה / טלפון: ${form.orderOrPhone.trim()}`,
        `סיבת הביטול: ${form.reason.trim()}`,
      ].join('\n');
      await contactAPI.createContactMessage({
        name: form.fullName.trim(),
        email: 'cancel-request@tradetix.local',
        order_number: form.orderOrPhone.trim().slice(0, 100),
        message,
      });
      setSuccess(true);
      setForm(INITIAL);
    } catch (err) {
      setError(apiErrorMessageHe(err, 'שליחת הבקשה נכשלה. נסו שוב או פנו דרך צור קשר.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="terms-container">
      <PageSeo
        title={meta?.title || 'ביטול עסקה | TradeTix'}
        description={meta?.description || 'מדיניות ביטולים והחזרים וטופס ביטול עסקה ב-TradeTix.'}
        path="/cancel-transaction"
        breadcrumbs={staticPageBreadcrumbs('/cancel-transaction')}
      />
      <article className="terms-card">
        <h1 className="terms-title">מדיניות ביטולים והחזרים / טופס ביטול עסקה</h1>
        <p style={{ textAlign: 'center', color: '#6b7280', marginBottom: '1.5rem' }}>
          עודכן לאחרונה: ספטמבר 2026
        </p>

        <section className="terms-section">
          <h2>הודעה משפטית</h2>
          <p>
            בהתאם לחוק הגנת הצרכן, התשמ&quot;א–1981 ותקנות ביטול עסקה, כרטיסים למופעים ואירועי בידור
            שנקבעו להם מועד ודאי אינם ניתנים לביטול עקב שינוי דעת לאחר אספקתם הדיגיטלית, אלא במקרים
            של ביטול האירוע על ידי המארגן או בהתאם להוראות הדין. במקרה של זכאות להחזר לפי התקנון,
            הכספים יושבו בהתאם למדיניות מנגנון הנאמנות.
          </p>
          <p>
            לפירוט נוסף ראו גם את עמוד{' '}
            <Link to="/refunds">ביטולים, אחריות והחזרים</Link> ואת{' '}
            <Link to="/terms">תקנון ותנאי השימוש</Link>.
          </p>
        </section>

        <section className="terms-section">
          <h2>טופס ביטול עסקה מקוון</h2>
          <p>
            מלאו את הפרטים להלן. נבחן את הבקשה בהתאם לדין ולתקנון ונחזור אליכם בהקדם האפשרי.
          </p>

          {success ? (
            <div className="contact-success" role="status">
              בקשת הביטול נשלחה בהצלחה. צוות TradeTix יבדוק את הפרטים ויחזור אליכם בהקדם.
            </div>
          ) : null}
          {error ? (
            <div className="contact-error" role="alert">
              {error}
            </div>
          ) : null}

          <form className="contact-form" onSubmit={onSubmit} dir="rtl" style={{ marginTop: '1rem' }}>
            <div className="form-group">
              <label htmlFor="cancel-fullName">שם מלא *</label>
              <input
                id="cancel-fullName"
                name="fullName"
                type="text"
                required
                autoComplete="name"
                value={form.fullName}
                onChange={onChange}
                disabled={busy}
              />
            </div>
            <div className="form-group">
              <label htmlFor="cancel-idNumber">תעודת זהות *</label>
              <input
                id="cancel-idNumber"
                name="idNumber"
                type="text"
                inputMode="numeric"
                required
                autoComplete="off"
                value={form.idNumber}
                onChange={onChange}
                disabled={busy}
              />
            </div>
            <div className="form-group">
              <label htmlFor="cancel-orderOrPhone">מספר הזמנה / טלפון *</label>
              <input
                id="cancel-orderOrPhone"
                name="orderOrPhone"
                type="text"
                required
                autoComplete="tel"
                value={form.orderOrPhone}
                onChange={onChange}
                disabled={busy}
              />
            </div>
            <div className="form-group">
              <label htmlFor="cancel-reason">סיבת הביטול *</label>
              <textarea
                id="cancel-reason"
                name="reason"
                required
                rows={4}
                value={form.reason}
                onChange={onChange}
                disabled={busy}
              />
            </div>
            <button type="submit" className="contact-submit-btn" disabled={busy}>
              {busy ? 'שולח…' : 'שליחת בקשת ביטול'}
            </button>
          </form>
        </section>
      </article>
    </div>
  );
}
