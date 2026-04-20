/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { useMemo } from 'react';
import { Filter, Trophy, Ticket, Gem, CheckSquare } from 'lucide-react';
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
  cheapestTicketPrice = null,
}) {
  const resolvedCheapest = useMemo(() => {
    if (cheapestTicketPrice != null && !Number.isNaN(Number(cheapestTicketPrice))) {
      return Number(cheapestTicketPrice);
    }
    const nums = rows
      .map((r) => parseFloat(r.group?.price))
      .filter((n) => !Number.isNaN(n));
    if (nums.length === 0) return null;
    return Math.min(...nums);
  }, [rows, cheapestTicketPrice]);
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

      <div
        className="max-h-[min(68vh,640px)] space-y-3 overflow-y-auto overflow-x-hidden overscroll-contain px-3 py-3 [scrollbar-width:thin] [scrollbar-color:rgb(203_213_225)_transparent] [color-scheme:light] [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-slate-300/90"
      >
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
            const hasPdf = (group.tickets || []).some((t) => t.has_pdf_file || t.pdf_file_url);
            const groupPrice = parseFloat(group.price);
            const isBestValue =
              resolvedCheapest != null && !Number.isNaN(groupPrice) && groupPrice === resolvedCheapest;

            const rawSection =
              firstTicket?.section != null ? String(firstTicket.section).trim() : '';
            const detailTitle =
              rawSection.length > 0
                ? bloomfield.row && bloomfield.row !== '—'
                  ? `${rawSection} — row ${bloomfield.row}`
                  : rawSection
                : `${bloomfield.zone}-tier-${bloomfield.sectionId}`;

            return (
              <article
                key={stableId}
                data-ticket-group-id={groupId}
                data-e2e-ticket-id={firstTicket?.id}
                data-bloomfield-block={bloomfield.blockId}
                className={`overflow-hidden rounded-xl border border-slate-200/90 bg-white shadow-sm transition-shadow hover:shadow-md ${
                  isHi ? 'ring-2 ring-emerald-400 ring-offset-2' : ''
                }`}
                onMouseEnter={() => onHoverRow(stableId)}
                onMouseLeave={() => onHoverRow(null)}
              >
                {bloomfield.isTopChoice ? (
                  <div className="flex items-center gap-2 border-b border-green-100 bg-green-50 px-4 py-2.5 font-sans text-sm font-semibold text-green-800">
                    <Trophy className="h-4 w-4 shrink-0 text-green-700" strokeWidth={2} aria-hidden />
                    Top choice
                  </div>
                ) : null}
                <div dir="ltr" lang="en" className="text-left">
                  <button
                    type="button"
                    className="flex w-full min-w-0 flex-row items-center justify-between gap-4 border-0 bg-transparent px-4 py-4 text-left font-sans shadow-none outline-none ring-0 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-500/40"
                    onClick={() => onToggleRow(groupId)}
                  >
                    <div
                      className="min-w-0 shrink-0 [&_.buyer-listing-price]:items-start [&_.buyer-listing-price]:text-left [&_.buyer-listing-price-main]:text-3xl [&_.buyer-listing-price-main]:font-bold [&_.buyer-listing-price-main]:leading-none [&_.buyer-listing-price-main]:tracking-tight [&_.buyer-listing-price-fee]:mt-1 [&_.buyer-listing-price-fee]:text-xs [&_.buyer-listing-price-fee]:text-slate-500"
                    >
                      <BuyerListingPrice ticket={firstTicket} />
                    </div>
                    <div className="flex min-w-0 flex-1 flex-col items-end text-right">
                      <h3 className="text-sm font-semibold leading-snug text-slate-800">{detailTitle}</h3>
                      <div className="mt-2 flex flex-wrap justify-end gap-2">
                        {group.available_count > 0 ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                            <Ticket className="h-3.5 w-3.5 shrink-0 text-pink-500" strokeWidth={2} aria-hidden />
                            כרטיסים זמינים
                          </span>
                        ) : null}
                        {isBestValue ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-cyan-100/90 px-2.5 py-1 text-xs font-semibold text-teal-900">
                            <Gem className="h-3.5 w-3.5 shrink-0 text-teal-600" strokeWidth={2} aria-hidden />
                            מחיר משתלם
                          </span>
                        ) : null}
                        {hasPdf ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-sky-100 px-2.5 py-1 text-xs font-semibold text-sky-900">
                            <CheckSquare className="h-3.5 w-3.5 shrink-0 text-green-600" strokeWidth={2} aria-hidden />
                            הורדה מיידית
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </button>
                </div>

                {isExpanded ? (
                  <div className="border-t border-slate-100 px-4 pb-4 pt-3" dir="rtl">
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
