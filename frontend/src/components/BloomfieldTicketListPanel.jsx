/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { Users, Eye, Filter, Trophy } from 'lucide-react';
import BuyerListingPrice from './BuyerListingPrice';

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
          Only a few tickets left for this event — don&apos;t wait until the last minute
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-3 py-2.5">
        <p className="text-sm font-semibold text-slate-800">
          {rows.length} listings
          {listingQuantity > 1 ? (
            <span className="mr-1 font-normal text-slate-500">
              · at least {listingQuantity} tickets
            </span>
          ) : null}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenFilters}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-emerald-600 shadow-sm hover:bg-slate-50"
            aria-label="Filters"
          >
            <Filter className="h-5 w-5" strokeWidth={2} />
          </button>
          <label className="sr-only" htmlFor="bloomfield-qty-select">
            Number of tickets
          </label>
          <select
            id="bloomfield-qty-select"
            value={listingQuantity}
            onChange={(e) => onListingQuantityChange(Number(e.target.value))}
            className="rounded-lg border border-slate-200 bg-white py-1.5 pl-8 pr-2 text-sm font-medium text-slate-800 shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          >
            {[1, 2, 3, 4, 5, 6, 8].map((n) => (
              <option key={n} value={n}>
                {n} {n === 1 ? 'ticket' : 'tickets'}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="max-h-[min(68vh,640px)] divide-y divide-slate-100 overflow-y-auto overscroll-contain">
        {rows.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-slate-600">
            No listings match the number of tickets you selected. Try lowering the quantity or
            clearing filters.
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
                data-bloomfield-block={bloomfield.blockId}
                className={`px-4 py-3.5 transition-colors ${
                  isHi
                    ? 'bg-sky-50 ring-1 ring-inset ring-sky-200'
                    : 'bg-white hover:bg-slate-50/90'
                }`}
                onMouseEnter={() => onHoverRow(stableId)}
                onMouseLeave={() => onHoverRow(null)}
              >
                <div dir="ltr" lang="en" className="text-left">
                  <button
                    type="button"
                    className="flex w-full min-w-0 flex-col gap-3"
                    onClick={() => onToggleRow(groupId)}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <h3 className="text-[1.0625rem] font-bold leading-tight tracking-tight text-slate-900">
                          Section {bloomfield.sectionId}
                        </h3>
                        <p className="mt-1 text-sm font-medium text-slate-600">
                          Row {bloomfield.row}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-2 sm:flex-row sm:items-center">
                        <span className="inline-flex items-center rounded-full bg-emerald-500 px-2.5 py-1 text-xs font-bold text-white shadow-sm">
                          {bloomfield.rating.score} {bloomfield.rating.label}
                        </span>
                        <div className="min-w-0 [&_.buyer-listing-price-main]:text-xl [&_.buyer-listing-price-main]:font-extrabold">
                          <BuyerListingPrice ticket={firstTicket} compact />
                        </div>
                      </div>
                    </div>

                    {bloomfield.features.length > 0 ? (
                      <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs font-medium text-slate-600">
                        {bloomfield.features.map((f) => (
                          <span key={f.key} className="inline-flex items-center gap-1.5">
                            {f.key === 'together' ? (
                              <Users className="h-4 w-4 shrink-0 text-emerald-600" strokeWidth={2} />
                            ) : (
                              <Eye className="h-4 w-4 shrink-0 text-slate-500" strokeWidth={2} />
                            )}
                            {f.label}
                          </span>
                        ))}
                      </div>
                    ) : null}

                    <div className="flex flex-wrap items-center gap-2">
                      {bloomfield.isTopChoice ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-lime-100 px-2.5 py-1 text-xs font-semibold text-lime-900">
                          <Trophy className="h-3.5 w-3.5" strokeWidth={2} />
                          Top choice
                        </span>
                      ) : null}
                      {bloomfield.lastTickets ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2.5 py-1 text-xs font-semibold text-rose-800">
                          Last tickets
                        </span>
                      ) : null}
                    </div>

                    {bloomfield.urgencyNote ? (
                      <p className="text-xs font-semibold text-rose-600">{bloomfield.urgencyNote}</p>
                    ) : null}
                  </button>
                </div>

                {isExpanded ? (
                  <div className="mt-3 border-t border-slate-100 pt-3" dir="rtl">
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
