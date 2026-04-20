/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import BuyerListingPrice from './BuyerListingPrice';

function TrophyIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M6 9H4a2 2 0 00-2 2v1h4M18 9h2a2 2 0 012 2v1h-4M6 9V7a2 2 0 012-2h8a2 2 0 012 2v2M6 9v8a2 2 0 002 2h8a2 2 0 002-2V9"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function PeopleIcon() {
  return (
    <svg className="h-4 w-4 text-emerald-600" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zM23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg className="h-4 w-4 text-slate-500" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"
        stroke="currentColor"
        strokeWidth="2"
      />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

function FilterIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M3 6H21M7 12H17M10 18H14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export default function BloomfieldTicketListPanel({
  rows = [],
  listingQuantity = 1,
  onListingQuantityChange,
  onOpenFilters,
  highlightStableId = null,
  activeTicketId = null,
  onHoverRow,
  onToggleRow,
  onBuy,
  onOffer,
  user,
  isSellerFn,
  totalListingsBeforeQuantityFilter = 0,
}) {
  return (
    <div className="flex min-w-0 flex-col rounded-xl border border-slate-200 bg-white shadow-sm" dir="rtl">
      {totalListingsBeforeQuantityFilter > 0 && totalListingsBeforeQuantityFilter <= 8 ? (
        <div className="border-b border-rose-100 bg-rose-50 px-3 py-2 text-center text-xs font-semibold text-rose-700">
          נותרו מעט כרטיסים לאירוע זה — אל תחכו לרגע האחרון
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-3 py-2.5">
        <p className="text-sm font-semibold text-slate-800">
          {rows.length} מודעות
          {listingQuantity > 1 ? (
            <span className="mr-1 font-normal text-slate-500">· לפחות {listingQuantity} כרטיסים</span>
          ) : null}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenFilters}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-emerald-600 shadow-sm hover:bg-slate-50"
            aria-label="סינון מתקדם"
          >
            <FilterIcon />
          </button>
          <label className="sr-only" htmlFor="bloomfield-qty-select">
            מספר כרטיסים
          </label>
          <select
            id="bloomfield-qty-select"
            value={listingQuantity}
            onChange={(e) => onListingQuantityChange(Number(e.target.value))}
            className="rounded-lg border border-slate-200 bg-white py-1.5 pl-8 pr-2 text-sm font-medium text-slate-800 shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          >
            {[1, 2, 3, 4, 5, 6, 8].map((n) => (
              <option key={n} value={n}>
                {n} {n === 1 ? 'כרטיס' : 'כרטיסים'}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="max-h-[min(68vh,640px)] divide-y divide-slate-100 overflow-y-auto overscroll-contain">
        {rows.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-slate-600">
            אין מודעות שמתאימות לכמות הכרטיסים שבחרת. נסו להקטין את הכמות או לנקות סינון.
          </div>
        ) : (
          rows.map(({ stableId, group, bloomfield, firstTicket }) => {
            const groupId = group.listing_group_id ?? group.id;
            const isExpanded =
              activeTicketId != null && String(activeTicketId) === String(groupId);
            const isHi =
              highlightStableId != null && String(highlightStableId) === String(stableId);
            const sellerOwns = isSellerFn(user, firstTicket, group);

            return (
              <article
                key={stableId}
                data-ticket-group-id={groupId}
                data-e2e-ticket-id={firstTicket?.id}
                className={`px-3 py-3 transition-colors ${
                  isHi ? 'bg-sky-50 ring-1 ring-inset ring-sky-200' : 'bg-white hover:bg-slate-50/80'
                }`}
                onMouseEnter={() => onHoverRow(stableId)}
                onMouseLeave={() => onHoverRow(null)}
              >
                <button
                  type="button"
                  className="flex w-full min-w-0 flex-col gap-2 text-right"
                  onClick={() => onToggleRow(groupId)}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="text-base font-bold text-slate-900">
                        גוש {bloomfield.sectionId}
                        <span className="mr-1 font-semibold text-slate-600">· שורה {bloomfield.row}</span>
                      </h3>
                    </div>
                    <div className="flex flex-shrink-0 flex-wrap items-center justify-end gap-2">
                      <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-bold text-white">
                        {bloomfield.rating.score} {bloomfield.rating.label}
                      </span>
                      <div className="text-left">
                        <BuyerListingPrice ticket={firstTicket} compact />
                      </div>
                    </div>
                  </div>

                  {bloomfield.features.length > 0 ? (
                    <div className="flex flex-wrap gap-3 text-xs text-slate-600">
                      {bloomfield.features.map((f) => (
                        <span key={f.key} className="inline-flex items-center gap-1">
                          {f.key === 'together' ? <PeopleIcon /> : <EyeIcon />}
                          {f.label}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  <div className="flex flex-wrap items-center gap-2">
                    {bloomfield.isTopChoice ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-lime-100 px-2 py-0.5 text-xs font-semibold text-lime-900">
                        <TrophyIcon />
                        בחירה מובילה
                      </span>
                    ) : null}
                    {bloomfield.lastTickets ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-800">
                        כרטיסים אחרונים
                      </span>
                    ) : null}
                  </div>

                  {bloomfield.urgencyNote ? (
                    <p className="text-xs font-semibold text-rose-600">{bloomfield.urgencyNote}</p>
                  ) : null}
                </button>

                {isExpanded ? (
                  <div className="mt-3 border-t border-slate-100 pt-3">
                    {sellerOwns ? (
                      <div
                        className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900"
                        role="status"
                      >
                        זה המודעה שלך — לא ניתן לרכוש או להציע
                      </div>
                    ) : (
                      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                        <button
                          type="button"
                          className="rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white shadow-sm hover:bg-emerald-700"
                          disabled={group.available_count <= 0}
                          onClick={(e) => {
                            e.stopPropagation();
                            onBuy(group);
                          }}
                        >
                          קנה עכשיו
                        </button>
                        {user ? (
                          <button
                            type="button"
                            className="rounded-lg border-2 border-emerald-600 bg-white px-4 py-2.5 text-sm font-bold text-emerald-700 hover:bg-emerald-50"
                            disabled={group.available_count <= 0}
                            onClick={(e) => {
                              e.stopPropagation();
                              onOffer(group);
                            }}
                          >
                            הצע מחיר
                          </button>
                        ) : (
                          <p className="text-xs text-slate-500">התחברו כדי להציע מחיר</p>
                        )}
                      </div>
                    )}
                  </div>
                ) : null}
              </article>
            );
          })
        )}
      </div>
    </div>
  );
}
