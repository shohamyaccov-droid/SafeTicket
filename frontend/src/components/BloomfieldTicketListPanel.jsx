/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { Filter } from 'lucide-react';
import {
  getTicketBaseNumeric,
  resolveTicketCurrency,
  currencySymbol,
  formatAmountForCurrency,
  buyerChargeFromBase,
} from '../utils/priceFormat';
import { listingAvailabilityLabel, listingQuantityOptions, normalizeListingSplitType } from '../utils/listingQuantity';
import TakenBuyButton from './TakenBuyButton';
import { isListingGroupTaken } from '../utils/ticketAvailability';
import useBuyerServiceFeePercent from '../hooks/useBuyerServiceFeePercent';
import { formatBuyerFeePercent } from '../services/pricingSettings';

const ZONE_HE = {
  north: 'טריבונה צפון',
  south: 'טריבונה דרום',
  east: 'טריבונה מזרח',
  west: 'טריבונה מערב',
  pitch: 'מגרש / אזור ליד הבמה',
  'concert-west': 'יציע מערב',
  'concert-east': 'יציע מזרח',
  'concert-south': 'יציע דרום (עגול)',
};

/* ─── inline style constants ─────────────────────────────────────────────── */
/* Using inline styles for all layout-critical rules so no external CSS      */
/* (BuyerListingPrice.css, global resets, browser button defaults) can break  */
/* the horizontal flex layout.                                                */

const ROW_STYLE = {
  display: 'flex',
  flexDirection: 'row',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '12px 16px',
  gap: '12px',
  minHeight: '64px',
};

const CTA_COL_STYLE = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'stretch',
  flexShrink: 0,
};

const ROW_BUY_BTN_STYLE = {
  minHeight: 40,
  minWidth: 108,
  padding: '8px 12px',
  border: 'none',
  borderRadius: 8,
  background: '#059669',
  color: '#fff',
  fontSize: 13,
  fontWeight: 800,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
};

const PRICE_COL_STYLE = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'flex-start',
  flexShrink: 0,
};

const SECTION_COL_STYLE = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'flex-end',
  textAlign: 'right',
  minWidth: 0,
  flex: 1,
};

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
  buyQuantity = 1,
  onBuyQuantityChange,
  buyingStableId = null,
  user,
  isSellerFn,
  onRequestLogin,
  totalListingsBeforeQuantityFilter = 0,
}) {
  const buyerFeePercent = useBuyerServiceFeePercent();
  const feePercentLabel = formatBuyerFeePercent(buyerFeePercent);

  return (
    <div className="flex min-w-0 flex-col rounded-xl border border-slate-200 bg-white shadow-sm" dir="rtl">

      {/* Scarcity banner */}
      {totalListingsBeforeQuantityFilter > 0 && totalListingsBeforeQuantityFilter <= 8 ? (
        <div className="border-b border-rose-100 bg-rose-50 px-3 py-2 text-center text-xs font-semibold text-rose-700">
          נותרו מעט כרטיסים לאירוע זה — אל תחכו לרגע האחרון
        </div>
      ) : null}

      {/* Header: count + controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-3 py-2.5">
        <p className="text-sm font-semibold text-slate-800">
          {rows.length} מודעות
          {listingQuantity > 1 ? (
            <span className="mr-1 font-normal text-slate-500">
              · לפחות {listingQuantity} כרטיסים
            </span>
          ) : null}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenFilters}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-emerald-600 shadow-sm hover:bg-slate-50"
            aria-label="סינון"
          >
            <Filter className="h-5 w-5" strokeWidth={2} />
          </button>
          <label className="sr-only" htmlFor="bloomfield-qty-select">
            מספר כרטיסים
          </label>
          <select
            id="bloomfield-qty-select"
            value={listingQuantity}
            onChange={(e) => onListingQuantityChange(Number(e.target.value))}
            className="rounded-lg border border-slate-200 bg-white py-1.5 px-3 text-sm font-medium text-slate-800 shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          >
            {[1, 2, 3, 4, 5, 6, 8].map((n) => (
              <option key={n} value={n}>
                {n} {n === 1 ? 'כרטיס' : 'כרטיסים'}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Ticket list */}
      <div
        className="max-h-[min(68vh,640px)] space-y-2 overflow-y-auto overflow-x-hidden overscroll-contain px-3 py-3 [scrollbar-width:thin] [scrollbar-color:rgb(203_213_225)_transparent] [color-scheme:light] [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-slate-300/90"
      >
        {rows.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-slate-600" dir="rtl">
            אין מודעות שתואמות לכמות הנבחרת. נסו להפחית את הכמות או לנקות את הסינון.
          </div>
        ) : (
          rows.map(({ stableId, group, bloomfield, firstTicket }) => {
            const groupId = group.listing_group_id ?? group.id;
            const isExpanded =
              activeTicketId != null && String(activeTicketId) === String(groupId);
            const isHi =
              highlightStableId != null && String(highlightStableId) === String(stableId);
            const isBuying =
              buyingStableId != null && String(buyingStableId) === String(stableId);
            const sellerOwns = isSellerFn(user, firstTicket, group);
            const isTakenListing = isListingGroupTaken(group);
            const isUnavailableListing = sellerOwns || isTakenListing;
            const splitType = normalizeListingSplitType(
              firstTicket?.split_type || group.split_type || ''
            );
            const qtyOptions = listingQuantityOptions(splitType, group.available_count || 1);

            /* ── price computation (bypass BuyerListingPrice.css entirely) ── */
            const cur = resolveTicketCurrency(firstTicket);
            const sym = currencySymbol(cur);
            const baseNum = getTicketBaseNumeric(firstTicket);
            const priceStr = formatAmountForCurrency(baseNum, cur);
            const feeNum =
              baseNum > 0
                ? buyerChargeFromBase(baseNum, buyerFeePercent).serviceFee
                : 0;
            const qty = group.available_count || 1;
            const qtyLabel = listingAvailabilityLabel(splitType, qty);

            /* ── section title ────────────────────────────────────────────── */
            const rawSection =
              firstTicket?.section != null ? String(firstTicket.section).trim() : '';
            const detailTitle =
              rawSection.length > 0
                ? bloomfield.row && bloomfield.row !== '—'
                  ? `${rawSection} — שורה ${bloomfield.row}`
                  : rawSection
                : bloomfield.sectionId && bloomfield.sectionId !== '—'
                  ? `מקטע ${bloomfield.sectionId}`
                  : ZONE_HE[bloomfield.zone] || 'אזור כללי';

            return (
              <article
                key={stableId}
                data-ticket-group-id={groupId}
                data-e2e-ticket-id={firstTicket?.id}
                data-bloomfield-block={bloomfield.blockId}
                role="button"
                tabIndex={0}
                onClick={() => onToggleRow(groupId, group)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onToggleRow(groupId, group);
                  }
                }}
                onMouseEnter={() => onHoverRow(stableId)}
                onMouseLeave={() => onHoverRow(null)}
                className={`overflow-hidden rounded-xl border bg-white shadow-sm transition-shadow hover:shadow-md ${
                  isHi
                    ? 'border-emerald-400 ring-2 ring-emerald-400 ring-offset-1'
                    : isExpanded
                      ? 'border-slate-300'
                      : 'border-slate-200'
                }`}
                style={{ cursor: 'pointer' }}
              >
                {/* ── HORIZONTAL CARD ROW (inline styles guarantee layout) ── */}
                <div style={ROW_STYLE}>

                  {/* LEFT: Price + service fee */}
                  <div style={PRICE_COL_STYLE}>
                    <span
                      style={{
                        fontSize: '0.8125rem',
                        fontWeight: 600,
                        color: '#374151',
                        marginBottom: 2,
                        direction: 'rtl',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {qtyLabel}
                    </span>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'baseline',
                        gap: '0.35rem',
                        whiteSpace: 'nowrap',
                        lineHeight: 1.15,
                      }}
                    >
                      <span
                        style={{
                          fontSize: '1.5rem',
                          fontWeight: 700,
                          color: '#111827',
                          direction: 'ltr',
                          unicodeBidi: 'embed',
                          letterSpacing: '-0.02em',
                        }}
                      >
                        {sym}{priceStr}
                      </span>
                      <span
                        style={{
                          fontSize: '0.8125rem',
                          fontWeight: 500,
                          color: '#6b7280',
                          direction: 'rtl',
                        }}
                      >
                        לכרטיס
                      </span>
                    </span>
                    {feeNum > 0 && (
                      <span
                        style={{
                          fontSize: '0.7rem',
                          color: '#6b7280',
                          marginTop: 4,
                          whiteSpace: 'nowrap',
                          direction: 'rtl',
                        }}
                      >
                        + {feePercentLabel}% דמי שירות ותפעול
                      </span>
                    )}
                  </div>

                  {/* RIGHT: Section title + badges */}
                  <div dir="rtl" style={SECTION_COL_STYLE}>
                    <span
                      style={{
                        fontSize: '0.875rem',
                        fontWeight: 600,
                        color: '#1f2937',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: '160px',
                      }}
                    >
                      {detailTitle}
                    </span>
                  </div>

                  <div
                    style={CTA_COL_STYLE}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.stopPropagation()}
                  >
                    {sellerOwns ? (
                      <TakenBuyButton label="הכרטיס שלך" variant="own" />
                    ) : isTakenListing ? (
                      <TakenBuyButton label="נתפס" variant="taken" />
                    ) : (
                      <button
                        type="button"
                        style={ROW_BUY_BTN_STYLE}
                        disabled={group.available_count <= 0 || isBuying}
                        onClick={(e) => {
                          e.stopPropagation();
                          onBuy(group);
                        }}
                      >
                        {isBuying ? 'מעביר לתשלום…' : 'קנה עכשיו'}
                      </button>
                    )}
                  </div>

                </div>
                {/* ── END HORIZONTAL ROW ─────────────────────────────────── */}

                {isTakenListing ? (
                  <p className="px-4 pb-2 text-xs text-slate-500" dir="rtl">
                    כרטיס זה כבר אינו זמין לרכישה
                  </p>
                ) : null}

                {/* Quantity + offer after expand; buy CTA is always on the collapsed row */}
                {isExpanded && !isUnavailableListing ? (
                  <div className="border-t border-slate-100 px-4 pb-4 pt-3" dir="rtl">
                    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
                        <label className="flex flex-col gap-1 text-xs font-semibold text-slate-700">
                          כמות
                          <select
                            className="min-h-[44px] rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-800"
                            value={qtyOptions.includes(buyQuantity) ? buyQuantity : qtyOptions[0]}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => {
                              e.stopPropagation();
                              onBuyQuantityChange?.(Number(e.target.value));
                            }}
                            disabled={group.available_count <= 0 || isBuying}
                          >
                            {qtyOptions.map((n) => (
                              <option key={n} value={n}>
                                {n} {n === 1 ? 'כרטיס' : 'כרטיסים'}
                              </option>
                            ))}
                          </select>
                        </label>
                        {user ? (
                          group?.tickets?.[0]?.allow_negotiation !== false ? (
                            <button
                              type="button"
                              className="min-h-[44px] rounded-lg border-2 border-emerald-600 bg-white px-5 py-2.5 text-sm font-bold text-emerald-700 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:opacity-60"
                              disabled={group.available_count <= 0}
                              onClick={(e) => {
                                e.stopPropagation();
                                onOffer(group);
                              }}
                            >
                              הצע מחיר
                            </button>
                          ) : null
                        ) : group?.tickets?.[0]?.allow_negotiation !== false ? (
                          <button
                            type="button"
                            className="min-h-[44px] rounded-lg border-2 border-emerald-600 bg-white px-5 py-2.5 text-sm font-bold text-emerald-700 hover:bg-emerald-50"
                            onClick={(e) => {
                              e.stopPropagation();
                              onRequestLogin?.();
                            }}
                          >
                            התחבר כדי להציע מחיר על המודעה
                          </button>
                        ) : null}
                      </div>
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
