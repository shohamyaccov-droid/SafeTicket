/* eslint-disable react/prop-types */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { adminAPI } from '../services/api';
import { currencySymbol, formatAmountForCurrency } from '../utils/priceFormat';
import { toastError } from '../utils/toast';
import './AdminDashboard.css';
import './AdminOffersPage.css';

const STATUS_LABELS = {
  pending: 'ממתינה',
  accepted: 'אושרה',
  rejected: 'נדחתה',
  countered: 'הצעת נגד',
  expired: 'פגה',
};

function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('he-IL', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
}

function MetricCard({ label, value, sub }) {
  return (
    <article className="admin-stat-card admin-offer-metric">
      <div className="admin-stat-label">{label}</div>
      <div className="admin-stat-value">{value}</div>
      {sub ? <div className="admin-stat-sub">{sub}</div> : null}
    </article>
  );
}

export default function AdminOffersPage() {
  const { user } = useAuth();
  const [metrics, setMetrics] = useState(null);
  const [offers, setOffers] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [daysFilter, setDaysFilter] = useState('30');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await adminAPI.getOffersDashboard({
        status: statusFilter,
        days: daysFilter,
        q: search || undefined,
        page,
        page_size: pageSize,
      });
      setMetrics(response.data?.metrics || null);
      setOffers(response.data?.results || []);
      setCount(Number(response.data?.count || 0));
    } catch (error) {
      const message =
        error?.response?.data?.error ||
        error?.response?.data?.detail ||
        'לא ניתן לטעון את נתוני ההצעות';
      toastError(typeof message === 'string' ? message : 'לא ניתן לטעון את נתוני ההצעות');
    } finally {
      setLoading(false);
    }
  }, [daysFilter, page, search, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.max(1, Math.ceil(count / pageSize));
  const maxDaily = useMemo(
    () => Math.max(1, ...(metrics?.daily_activity || []).map((row) => Number(row.count || 0))),
    [metrics],
  );

  const applySearch = (event) => {
    event.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  };

  return (
    <div className="admin-dashboard-page admin-offers-page" dir="rtl">
      <header className="admin-dash-header">
        <div className="admin-dash-header-inner">
          <div>
            <h1 className="admin-dash-title">מעקב הצעות מחיר</h1>
            <p className="admin-dash-sub">
              שלום {user?.username || 'מנהל'} — סטטוסים, המרות ומעורבות במשא ומתן
            </p>
          </div>
          <div className="admin-dash-header-actions">
            <Link to="/admin-panel" className="admin-dash-link-secondary">
              ← לוח בקרה
            </Link>
            <button type="button" className="admin-dash-refresh" onClick={load} disabled={loading}>
              {loading ? 'טוען...' : 'רענון'}
            </button>
          </div>
        </div>
      </header>

      {metrics && (
        <>
          <section className="admin-stats-grid" aria-label="מדדי הצעות">
            <MetricCard
              label="שיחות משא ומתן"
              value={metrics.total_conversations ?? 0}
              sub={`${metrics.total_offers ?? 0} הצעות כולל הצעות נגד`}
            />
            <MetricCard
              label="ממתינות לתגובה"
              value={metrics.status_counts?.pending ?? 0}
              sub={`${metrics.response_rate_percent ?? '0.00'}% קיבלו תגובה`}
            />
            <MetricCard
              label="שיעור קבלה"
              value={`${metrics.acceptance_rate_percent ?? '0.00'}%`}
              sub={`${metrics.accepted_offers ?? 0} הצעות שאושרו`}
            />
            <MetricCard
              label="המרה לרכישה"
              value={`${metrics.purchase_conversion_percent ?? '0.00'}%`}
              sub={`${metrics.completed_purchases ?? 0} רכישות מהצעה`}
            />
            <MetricCard
              label="קונים פעילים"
              value={metrics.unique_buyers ?? 0}
              sub={`${metrics.unique_sellers ?? 0} מוכרים קיבלו הצעה`}
            />
            <MetricCard
              label="שיחות עם הצעת נגד"
              value={metrics.countered_conversations ?? 0}
              sub="מדד עומק שימוש"
            />
          </section>

          <section className="admin-section admin-offer-activity">
            <div className="admin-offer-section-heading">
              <div>
                <h2 className="admin-section-title">פעילות ב־14 הימים האחרונים</h2>
                <p className="admin-muted">מספר הצעות והצעות נגד שנוצרו בכל יום</p>
              </div>
              <div className="admin-offer-currencies">
                {(metrics.by_currency || []).map((row) => (
                  <span key={row.currency}>
                    {row.currency}: {row.count} · ממוצע {currencySymbol(row.currency)}
                    {formatAmountForCurrency(row.average_amount, row.currency)}
                  </span>
                ))}
              </div>
            </div>
            <div className="admin-offer-chart" aria-label="גרף פעילות הצעות">
              {(metrics.daily_activity || []).map((row) => (
                <div className="admin-offer-chart-column" key={row.date}>
                  <span className="admin-offer-chart-value">{row.count}</span>
                  <div
                    className="admin-offer-chart-bar"
                    style={{ height: `${Math.max(4, (Number(row.count || 0) / maxDaily) * 100)}%` }}
                  />
                  <span className="admin-offer-chart-date">
                    {new Date(`${row.date}T00:00:00`).toLocaleDateString('he-IL', {
                      day: 'numeric',
                      month: 'numeric',
                    })}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      <section className="admin-section">
        <div className="admin-offer-toolbar">
          <div className="admin-offer-filter-group">
            <label>
              סטטוס
              <select
                value={statusFilter}
                onChange={(event) => {
                  setStatusFilter(event.target.value);
                  setPage(1);
                }}
              >
                <option value="all">הכול</option>
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <option value={value} key={value}>{label}</option>
                ))}
              </select>
            </label>
            <label>
              תקופה
              <select
                value={daysFilter}
                onChange={(event) => {
                  setDaysFilter(event.target.value);
                  setPage(1);
                }}
              >
                <option value="7">7 ימים</option>
                <option value="30">30 ימים</option>
                <option value="90">90 ימים</option>
                <option value="all">כל התקופה</option>
              </select>
            </label>
          </div>
          <form className="admin-offer-search" onSubmit={applySearch}>
            <input
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="חיפוש משתמש, אימייל, אירוע או מזהה"
              aria-label="חיפוש הצעות"
            />
            <button type="submit">חיפוש</button>
          </form>
        </div>

        <div className="admin-table-wrap">
          <table className="admin-transactions-table admin-offers-table">
            <thead>
              <tr>
                <th>נוצרה</th>
                <th>אירוע / כרטיס</th>
                <th>צדדים</th>
                <th>סכום</th>
                <th>סטטוס</th>
                <th>תוצאה</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="admin-empty-cell">טוען הצעות...</td></tr>
              ) : offers.length === 0 ? (
                <tr><td colSpan={6} className="admin-empty-cell">לא נמצאו הצעות לפי הסינון</td></tr>
              ) : (
                offers.map((offer) => (
                  <tr key={offer.id}>
                    <td data-label="נוצרה">
                      <strong>#{offer.id}</strong>
                      <div className="admin-muted">{formatDateTime(offer.created_at)}</div>
                      <div className="admin-muted">שיחה #{offer.conversation_id}</div>
                    </td>
                    <td data-label="אירוע">
                      <strong>{offer.event_name || '—'}</strong>
                      <div className="admin-muted">כרטיס #{offer.ticket_id} · {offer.quantity} יח׳</div>
                    </td>
                    <td data-label="צדדים">
                      <div>קונה: {offer.buyer?.username || '—'}</div>
                      <div>מוכר: {offer.seller?.username || '—'}</div>
                      <div className="admin-muted">
                        {offer.sender_username} ← שולח · סבב {offer.round}
                      </div>
                    </td>
                    <td data-label="סכום" dir="ltr">
                      <strong>
                        {currencySymbol(offer.currency)}
                        {formatAmountForCurrency(offer.amount, offer.currency)}
                      </strong>
                      <div className="admin-muted">
                        מחיר מבוקש {currencySymbol(offer.currency)}
                        {formatAmountForCurrency(offer.asking_total, offer.currency)}
                      </div>
                      {offer.discount_percent != null && (
                        <div className="admin-muted">{offer.discount_percent}% הנחה</div>
                      )}
                    </td>
                    <td data-label="סטטוס">
                      <span className={`admin-offer-status admin-offer-status--${offer.status}`}>
                        {STATUS_LABELS[offer.status] || offer.status}
                      </span>
                      {offer.checkout_expired && (
                        <div className="admin-offer-warning">חלון התשלום פג</div>
                      )}
                    </td>
                    <td data-label="תוצאה">
                      {offer.purchase_completed ? (
                        <span className="admin-offer-purchased">נרכשה · הזמנה #{offer.order_id}</span>
                      ) : offer.status === 'accepted' ? (
                        <span>ממתין לתשלום</span>
                      ) : (
                        <span className="admin-muted">ללא רכישה</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="admin-offer-pagination">
          <button
            type="button"
            disabled={page <= 1 || loading}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            הקודם
          </button>
          <span>עמוד {page} מתוך {totalPages} · {count} תוצאות</span>
          <button
            type="button"
            disabled={page >= totalPages || loading}
            onClick={() => setPage((current) => current + 1)}
          >
            הבא
          </button>
        </div>
      </section>
    </div>
  );
}
