/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { useMemo, useCallback, useState } from 'react';
import { useVenueMapPanZoom } from '../hooks/useVenueMapPanZoom';
import { getTicketPrice, formatMoney, resolveTicketCurrency } from '../utils/priceFormat';
import {
  CONCERT_BLOCKS,
  CONCERT_BLOCK_COUNT,
  CONCERT_SPACERS,
  STAGE_RECT,
  STAGE_LABEL_CX,
  STAGE_LABEL_CY,
  concertBlockPolygonPoints,
} from '../utils/bloomfieldConcertGeometry';
import './BloomfieldStadiumMap.css';
import './BloomfieldConcertMap.css';

const FILL_EMPTY = '#dbe4f3';
const FILL_EMPTY_HOVER = '#a5b4fc';
const STROKE_SECTION = '#ffffff';
const STROKE_EMPTY = '#c7d2e8';
const STROKE_INACTIVE_W = 2;
const STROKE_HIGHLIGHT_W = 5;

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

const VIEWBOX_PADDING = 40;

function computeTightViewBox() {
  let minX = STAGE_RECT.x;
  let minY = STAGE_RECT.y;
  let maxX = STAGE_RECT.x + STAGE_RECT.w;
  let maxY = STAGE_RECT.y + STAGE_RECT.h;

  for (const b of CONCERT_BLOCKS) {
    minX = Math.min(minX, b.x);
    minY = Math.min(minY, b.y);
    maxX = Math.max(maxX, b.x + b.w);
    maxY = Math.max(maxY, b.y + b.h);
  }
  for (const s of CONCERT_SPACERS) {
    minX = Math.min(minX, s.x);
    minY = Math.min(minY, s.y);
    maxX = Math.max(maxX, s.x + s.w);
    maxY = Math.max(maxY, s.y + s.h);
  }

  const vbX = minX - VIEWBOX_PADDING;
  const vbY = minY - VIEWBOX_PADDING;
  const vbW = maxX - minX + VIEWBOX_PADDING * 2;
  const vbH = maxY - minY + VIEWBOX_PADDING * 2;
  return {
    vbX,
    vbY,
    vbW,
    vbH,
    viewBoxStr: `${vbX} ${vbY} ${vbW} ${vbH}`,
  };
}

export default function BloomfieldConcertMap({
  rows = [],
  highlightStableId = null,
  onSelectGroup,
  onHoverGroup,
}) {
  const [hoverBlockId, setHoverBlockId] = useState(null);
  const panZoom = useVenueMapPanZoom({ minScale: 0.65, maxScale: 2.8, zoomStep: 0.14 });

  const { viewBoxStr, vbX, vbY, vbW, vbH } = useMemo(() => computeTightViewBox(), []);

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
    setHoverBlockId(String(blockId));
    const has = blocksWithListings.has(String(blockId));
    if (!has) return;
    const first = firstRowInBlock(blockId);
    onHoverGroup?.(first?.stableId ?? null);
  };

  const handleBlockLeave = () => {
    setHoverBlockId(null);
    onHoverGroup?.(null);
  };

  const handleBlockClick = (blockId) => {
    if (!blocksWithListings.has(String(blockId))) return;
    const first = firstRowInBlock(blockId);
    if (first) onSelectGroup?.(first.stableId);
  };

  return (
    <div className="bloomfield-map-shell">
    <div className="bloomfield-map-root relative h-full w-full min-h-[300px] max-h-[min(85vh,920px)] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
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
        <div className="h-full w-full will-change-transform" style={panZoom.transformStyle}>
          <svg
            viewBox={viewBoxStr}
            width="100%"
            height="100%"
            className="block h-full w-full select-none overflow-visible"
            role="img"
            aria-label="מפת הושבה — אצטדיון בלומפילד — הופעה"
          >
            <defs>
              <filter id="bfc-seat-soft" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#0f172a" floodOpacity="0.08" />
              </filter>
              <linearGradient id="bfc-stage-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#4f46e5" />
                <stop offset="100%" stopColor="#1e293b" />
              </linearGradient>
            </defs>

            <rect x={vbX} y={vbY} width={vbW} height={vbH} fill="#ffffff" />

            <rect
              x={STAGE_RECT.x}
              y={STAGE_RECT.y}
              width={STAGE_RECT.w}
              height={STAGE_RECT.h}
              rx={12}
              ry={12}
              fill="url(#bfc-stage-gradient)"
              stroke="#312e81"
              strokeWidth="3"
              filter="url(#bfc-seat-soft)"
            />
            <text
              x={STAGE_LABEL_CX}
              y={STAGE_LABEL_CY}
              textAnchor="middle"
              dominantBaseline="central"
              fill="#ffffff"
              fontSize="28"
              fontWeight="800"
              fontFamily="system-ui, sans-serif"
              style={{ pointerEvents: 'none', userSelect: 'none' }}
            >
              STAGE
            </text>
            <text
              x={STAGE_LABEL_CX}
              y={STAGE_LABEL_CY + 30}
              textAnchor="middle"
              dominantBaseline="central"
              fill="rgba(255,255,255,0.88)"
              fontSize="20"
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
              const isHover = hoverBlockId === sid;
              const rep = has ? firstRowInBlock(sid) : undefined;
              const raw = rep ? parseFloat(getTicketPrice(rep.firstTicket)) : NaN;
              const { fill } = has
                ? fillForPriceTier(minP, maxP, raw)
                : { fill: isHover ? FILL_EMPTY_HOVER : FILL_EMPTY, tier: 0 };
              const cur = rep ? resolveTicketCurrency(rep.firstTicket) : 'ILS';
              const priceLine =
                has && Number.isFinite(raw) ? formatMoney(raw, cur) : '';
              const pts = concertBlockPolygonPoints(b);
              const { cx, cy } = blockCenter(b);

              return (
                <g key={sid}>
                  <polygon
                    data-section-id={sid}
                    points={pts}
                    fill={fill}
                    stroke={isHi ? '#0ea5e9' : has ? STROKE_SECTION : STROKE_EMPTY}
                    strokeWidth={isHi ? STROKE_HIGHLIGHT_W : STROKE_INACTIVE_W}
                    filter={has ? 'url(#bfc-seat-soft)' : undefined}
                    className={`bloomfield-concert-map__seat${has ? ' bloomfield-concert-map__seat--listed' : ''}${
                      isHi ? ' bloomfield-concert-map__seat--active' : ''
                    }${isHover ? ' bloomfield-concert-map__seat--hover' : ''}`}
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
                  <text
                    className="bloomfield-concert-map__seat-label"
                    x={cx}
                    y={cy}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill={has ? '#1e293b' : '#475569'}
                    fontSize={has ? (sid.length > 3 ? 26 : 30) : sid.length > 3 ? 28 : 32}
                    fontWeight="700"
                    fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                  >
                    {b.label}
                  </text>
                </g>
              );
            })}

            {CONCERT_BLOCKS.map((b) => {
              const sid = String(b.id);
              if (!blocksWithListings.has(sid)) return null;
              const rep = firstRowInBlock(sid);
              if (!rep) return null;
              const raw = parseFloat(getTicketPrice(rep.firstTicket));
              const cur = resolveTicketCurrency(rep.firstTicket);
              const priceLine = Number.isFinite(raw) ? formatMoney(raw, cur) : '';
              const status = availabilityLine(rep, floorPrice);
              const { cx } = blockCenter(b);
              const tooltipW = 112;
              const tooltipH = status ? 54 : 38;
              const tooltipX = cx - tooltipW / 2;
              const tooltipY = Math.max(2, b.y - tooltipH - 8);

              return (
                <foreignObject
                  key={`tooltip-${sid}`}
                  x={tooltipX}
                  y={tooltipY}
                  width={tooltipW}
                  height={tooltipH}
                  className="bloomfield-map-price-tooltip-fo"
                >
                  <div
                    xmlns="http://www.w3.org/1999/xhtml"
                    className="bloomfield-map-price-tooltip"
                    aria-hidden="true"
                  >
                    <div className="bloomfield-map-price-tooltip__price">{priceLine}</div>
                    {status ? (
                      <div className="bloomfield-map-price-tooltip__label">{status}</div>
                    ) : null}
                    <div className="bloomfield-map-price-tooltip__section">{b.label}</div>
                  </div>
                </foreignObject>
              );
            })}
          </svg>
        </div>
      </div>
    </div>

      <div className="bloomfield-map-legend bloomfield-concert-map-legend" aria-hidden="true">
        <span className="bloomfield-map-legend__item">
          <span className="swatch swatch--available" /> זמין במלאי
        </span>
        <span className="bloomfield-map-legend__item">
          <span className="swatch swatch--selected" /> נבחר
        </span>
        <span className="bloomfield-map-legend__item">
          <span className="swatch swatch--unavailable" /> ללא מודעות
        </span>
        <span className="bloomfield-map-legend__meta">{CONCERT_BLOCK_COUNT} גושים · פריסת הופעה</span>
      </div>
    </div>
  );
}
