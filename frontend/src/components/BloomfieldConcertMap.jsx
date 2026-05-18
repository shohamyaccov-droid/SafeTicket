/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { useMemo, useCallback } from 'react';
import { useVenueMapPanZoom } from '../hooks/useVenueMapPanZoom';
import { getTicketPrice, formatMoney, resolveTicketCurrency } from '../utils/priceFormat';
import {
  VIEW_W,
  VIEW_H,
  CONCERT_BLOCKS,
  CONCERT_SPACERS,
  STAGE_RECT,
  STAGE_LABEL_CX,
  STAGE_LABEL_CY,
  concertBlockPolygonPoints,
} from '../utils/bloomfieldConcertGeometry';
import './BloomfieldConcertMap.css';

const STAGE_FILL = '#374151';
const STAGE_STROKE = '#1f2937';
const STROKE_SECTION = 'rgba(255,255,255,0.55)';
const STROKE_INACTIVE_W = 1.15;
const STROKE_HIGHLIGHT_W = 3;

function blockCenter(b) {
  return { cx: b.x + b.w / 2, cy: b.y + b.h / 2 };
}

function pickCheapestRow(list) {
  if (!list.length) return null;
  let best = list[0];
  let bestP = Infinity;
  for (const row of list) {
    const raw = parseFloat(getTicketPrice(row.firstTicket));
    const p = Number.isFinite(raw) ? raw : Infinity;
    if (p < bestP) {
      bestP = p;
      best = row;
    }
  }
  return best;
}

function globalMinListingPrice(rows) {
  let minP = Infinity;
  for (const row of rows) {
    const raw = parseFloat(getTicketPrice(row.firstTicket));
    if (Number.isFinite(raw) && raw < minP) minP = raw;
  }
  return minP;
}

function globalMaxListingPrice(rows) {
  let maxP = -Infinity;
  for (const row of rows) {
    const raw = parseFloat(getTicketPrice(row.firstTicket));
    if (Number.isFinite(raw) && raw > maxP) maxP = raw;
  }
  return maxP;
}

/** Higher price → deeper green (HSL). */
function fillForPriceTier(minP, maxP, price) {
  if (!Number.isFinite(price)) {
    return { fill: '#d1d5db', tier: 0 };
  }
  const lo = Number.isFinite(minP) ? minP : price;
  const hi = Number.isFinite(maxP) ? maxP : price;
  const span = hi > lo ? hi - lo : 0;
  const t = span > 0 ? Math.min(1, Math.max(0, (price - lo) / span)) : 0;
  const L = 90 - t * 44;
  const S = 36 + t * 34;
  const H = 142 + t * 12;
  return { fill: `hsl(${H}, ${S}%, ${L}%)`, tier: t };
}

function labelColorsForTier(tier) {
  if (tier >= 0.58) {
    return { main: '#f8fafc', sub: 'rgba(248,250,252,0.88)', sec: 'rgba(248,250,252,0.78)' };
  }
  return { main: '#0f172a', sub: '#334155', sec: '#1e293b' };
}

function availabilityLine(rep, floorPrice) {
  const avail = rep.group?.available_count ?? 0;
  const raw = parseFloat(getTicketPrice(rep.firstTicket));
  const bf = rep.bloomfield;
  if (bf?.isTopChoice) {
    return 'Amazing';
  }
  if (avail > 0 && avail < 5) {
    return `${avail} left`;
  }
  if (
    Number.isFinite(raw) &&
    Number.isFinite(floorPrice) &&
    Math.abs(raw - floorPrice) < 0.02
  ) {
    return 'Best value';
  }
  if (avail >= 12) {
    return `${avail} avail`;
  }
  return null;
}

export default function BloomfieldConcertMap({
  rows = [],
  highlightStableId = null,
  onSelectGroup,
  onHoverGroup,
}) {
  const panZoom = useVenueMapPanZoom({ minScale: 0.65, maxScale: 2.8, zoomStep: 0.14 });

  const blocksWithListings = useMemo(() => {
    const s = new Set();
    for (const r of rows) {
      const bid = r.bloomfield?.blockId;
      if (bid != null && bid !== '') s.add(String(bid));
    }
    return s;
  }, [rows]);

  const highlightBlockId = useMemo(() => {
    if (highlightStableId == null || highlightStableId === '') return null;
    const hit = rows.find((r) => String(r.stableId) === String(highlightStableId));
    const raw = hit?.bloomfield?.blockId;
    return raw != null && raw !== '' ? String(raw) : null;
  }, [rows, highlightStableId]);

  const minP = useMemo(() => globalMinListingPrice(rows), [rows]);
  const maxP = useMemo(() => globalMaxListingPrice(rows), [rows]);

  const blockRowsById = useMemo(() => {
    const m = {};
    for (const r of rows) {
      const bid = r.bloomfield?.blockId;
      if (bid == null || bid === '') continue;
      const k = String(bid);
      if (!m[k]) m[k] = [];
      m[k].push(r);
    }
    return m;
  }, [rows]);

  const floorPrice = Number.isFinite(minP) ? minP : null;

  const firstRowInBlock = useCallback(
    (blockId) => {
      const list = blockRowsById[String(blockId)] ?? [];
      return pickCheapestRow(list) ?? undefined;
    },
    [blockRowsById]
  );

  const handleBlockEnter = (blockId) => {
    const has = blocksWithListings.has(String(blockId));
    if (!has) return;
    const first = firstRowInBlock(blockId);
    onHoverGroup?.(first?.stableId ?? null);
  };

  const handleBlockLeave = () => {
    onHoverGroup?.(null);
  };

  const handleBlockClick = (blockId) => {
    if (!blocksWithListings.has(String(blockId))) return;
    const first = firstRowInBlock(blockId);
    if (first) onSelectGroup?.(first.stableId);
  };

  return (
    <div className="bloomfield-map-root relative w-full aspect-[1000/640] max-h-[min(540px,74vh)] min-h-[260px] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="absolute top-2 left-2 z-[5] flex flex-col overflow-hidden rounded-md shadow-md">
        <button
          type="button"
          className="flex h-9 w-9 items-center justify-center border-0 bg-white text-lg font-semibold text-slate-900 hover:bg-slate-50"
          onClick={panZoom.zoomIn}
          aria-label="התקרבות"
        >
          +
        </button>
        <button
          type="button"
          className="flex h-9 w-9 items-center justify-center border-t border-slate-200 bg-white text-lg font-semibold text-slate-900 hover:bg-slate-50"
          onClick={panZoom.zoomOut}
          aria-label="התרחקות"
        >
          −
        </button>
      </div>

      <div
        className="absolute inset-0 cursor-grab touch-none active:cursor-grabbing"
        onPointerDown={panZoom.onPointerDown}
        onPointerMove={panZoom.onPointerMove}
        onPointerUp={panZoom.onPointerUp}
        onPointerCancel={panZoom.onPointerUp}
        role="application"
        aria-label="מפת הושבה — הופעה בבלומפילד — גרירה להזזה, פלוס ומינוס לזום"
      >
        <div
          className="flex h-full w-full items-center justify-center will-change-transform"
          style={panZoom.transformStyle}
        >
          <svg
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            className="h-full w-full max-h-[540px] select-none overflow-visible"
            role="img"
            aria-label="מפת הושבה — אצטדיון בלומפילד — הופעה"
          >
            <defs>
              <filter id="bfc-seat-soft" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="1" stdDeviation="1.5" floodColor="#0f172a" floodOpacity="0.08" />
              </filter>
            </defs>

            <rect width={VIEW_W} height={VIEW_H} fill="#ffffff" />

            <rect
              x={STAGE_RECT.x}
              y={STAGE_RECT.y}
              width={STAGE_RECT.w}
              height={STAGE_RECT.h}
              rx={6}
              ry={6}
              fill={STAGE_FILL}
              stroke={STAGE_STROKE}
              strokeWidth="1.5"
            />
            <text
              x={STAGE_LABEL_CX}
              y={STAGE_LABEL_CY}
              textAnchor="middle"
              dominantBaseline="central"
              fill="#ffffff"
              fontSize="14"
              fontWeight="800"
              fontFamily="system-ui, sans-serif"
              style={{ pointerEvents: 'none', userSelect: 'none' }}
            >
              STAGE
            </text>
            <text
              x={STAGE_LABEL_CX}
              y={STAGE_LABEL_CY + 15}
              textAnchor="middle"
              dominantBaseline="central"
              fill="rgba(255,255,255,0.88)"
              fontSize="10"
              fontWeight="600"
              fontFamily="system-ui, sans-serif"
              style={{ pointerEvents: 'none', userSelect: 'none' }}
            >
              במה
            </text>

            {CONCERT_SPACERS.map((s, idx) => {
              const pts = [
                [s.x + 2, s.y + 2],
                [s.x + s.w - 2, s.y + 2],
                [s.x + s.w - 1, s.y + s.h - 2],
                [s.x + 1, s.y + s.h - 2],
              ]
                .map((p) => `${p[0]},${p[1]}`)
                .join(' ');
              return (
                <polygon key={`spacer-${idx}`} className="bloomfield-concert-map__spacer" points={pts} />
              );
            })}

            {CONCERT_BLOCKS.map((b) => {
              const sid = String(b.id);
              const has = blocksWithListings.has(sid);
              const isHi = highlightBlockId === sid;
              const rep = has ? firstRowInBlock(sid) : undefined;
              const raw = rep ? parseFloat(getTicketPrice(rep.firstTicket)) : NaN;
              const { fill, tier } = has
                ? fillForPriceTier(minP, maxP, raw)
                : { fill: '#d1d5db', tier: 0 };
              const cur = rep ? resolveTicketCurrency(rep.firstTicket) : 'ILS';
              const priceLine =
                has && Number.isFinite(raw) ? formatMoney(raw, cur) : '';
              const status = rep ? availabilityLine(rep, floorPrice) : null;
              const { main, sub, sec } = has ? labelColorsForTier(tier) : { main: '#64748b', sub: '#94a3b8', sec: '#64748b' };
              const pts = concertBlockPolygonPoints(b);
              const { cx, cy } = blockCenter(b);
              const lineCount = 1 + (status ? 1 : 0) + 1;
              const startY = cy - (lineCount === 2 ? 11 : lineCount === 3 ? 22 : 8);

              return (
                <g key={sid}>
                  <polygon
                    data-section-id={sid}
                    points={pts}
                    fill={fill}
                    stroke={isHi ? '#0ea5e9' : STROKE_SECTION}
                    strokeWidth={isHi ? STROKE_HIGHLIGHT_W : STROKE_INACTIVE_W}
                    filter={has ? 'url(#bfc-seat-soft)' : undefined}
                    className={`bloomfield-concert-map__seat${has ? ' bloomfield-concert-map__seat--listed' : ''}${
                      isHi ? ' bloomfield-concert-map__seat--active' : ''
                    }`}
                    style={{ transition: 'stroke 0.15s ease, stroke-width 0.15s ease' }}
                    onMouseEnter={() => handleBlockEnter(sid)}
                    onMouseLeave={handleBlockLeave}
                    onClick={() => handleBlockClick(sid)}
                    role={has ? 'button' : undefined}
                    tabIndex={has ? 0 : undefined}
                    onKeyDown={(e) => {
                      if (!has) return;
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleBlockClick(sid);
                      }
                    }}
                    aria-label={has ? `${b.label}, ${priceLine}` : b.label}
                  />
                  {has ? (
                    <text
                      className="bloomfield-concert-map__seat-label"
                      textAnchor="middle"
                      fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                      style={{ direction: 'ltr', unicodeBidi: 'isolate' }}
                    >
                      <tspan x={cx} y={startY} fill={main} fontSize="17" fontWeight="800">
                        {priceLine}
                      </tspan>
                      {status ? (
                        <tspan x={cx} dy="15" fill={sub} fontSize="12" fontWeight="700">
                          {status}
                        </tspan>
                      ) : null}
                      <tspan x={cx} dy={status ? '14' : '15'} fill={sec} fontSize="15" fontWeight="800">
                        {b.label}
                      </tspan>
                    </text>
                  ) : (
                    <text
                      className="bloomfield-concert-map__seat-label"
                      x={cx}
                      y={cy}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fill="#94a3b8"
                      fontSize={sid.length > 3 ? 14 : 16}
                      fontWeight="700"
                      fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                    >
                      {b.label}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    </div>
  );
}
