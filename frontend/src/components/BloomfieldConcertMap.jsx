/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { useMemo, useCallback, useState } from 'react';
import { useVenueMapPanZoom } from '../hooks/useVenueMapPanZoom';
import { getTicketPrice, formatListingMoney, resolveTicketCurrency } from '../utils/priceFormat';
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
import BloomfieldMapPriceTag from './BloomfieldMapPriceTag';
import {
  MAP_FILL_AVAILABLE,
  MAP_FILL_TAKEN,
  MAP_TAKEN_BUBBLE_LABEL,
  classifyMapBlockRows,
  mapRowIsBuyable,
} from '../utils/mapSectionStatus';

const FILL_EMPTY = '#dbe4f3';
const FILL_EMPTY_HOVER = '#a5b4fc';
const STROKE_SECTION = '#ffffff';
const STROKE_EMPTY = '#c7d2e8';
const STROKE_INACTIVE_W = 2;
const STROKE_HIGHLIGHT_W = 5;

function blockCenter(b) {
  return { cx: b.x + b.w / 2, cy: b.y + b.h / 2 };
}

function pickCheapestRow(list, { buyableOnly = false } = {}) {
  const pool = buyableOnly ? list.filter(mapRowIsBuyable) : list;
  if (!pool.length) return null;
  let best = pool[0];
  let bestP = Infinity;
  for (const row of pool) {
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
    if (!mapRowIsBuyable(row)) continue;
    const raw = parseFloat(getTicketPrice(row.firstTicket));
    if (Number.isFinite(raw) && raw < minP) minP = raw;
  }
  return minP;
}

function globalMaxListingPrice(rows) {
  let maxP = -Infinity;
  for (const row of rows) {
    if (!mapRowIsBuyable(row)) continue;
    const raw = parseFloat(getTicketPrice(row.firstTicket));
    if (Number.isFinite(raw) && raw > maxP) maxP = raw;
  }
  return maxP;
}

/** Higher price → deeper green (HSL). Taken sections use flat gray. */
function fillForPriceTier(minP, maxP, price) {
  if (!Number.isFinite(price)) {
    return { fill: MAP_FILL_AVAILABLE, tier: 0 };
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

  const blockStatusById = useMemo(() => {
    const status = {};
    for (const [k, list] of Object.entries(blockRowsById)) {
      status[k] = classifyMapBlockRows(list);
    }
    return status;
  }, [blockRowsById]);

  const blocksWithListings = useMemo(
    () => new Set(Object.keys(blockStatusById).filter((k) => blockStatusById[k] !== 'empty')),
    [blockStatusById]
  );

  const blocksAvailable = useMemo(
    () => new Set(Object.keys(blockStatusById).filter((k) => blockStatusById[k] === 'available')),
    [blockStatusById]
  );

  const highlightBlockId = useMemo(() => {
    if (highlightStableId == null || highlightStableId === '') return null;
    const hit = rows.find((r) => String(r.stableId) === String(highlightStableId));
    const raw = hit?.bloomfield?.blockId;
    return raw != null && raw !== '' ? String(raw) : null;
  }, [rows, highlightStableId]);

  const minP = useMemo(() => globalMinListingPrice(rows), [rows]);
  const maxP = useMemo(() => globalMaxListingPrice(rows), [rows]);

  const firstRowInBlock = useCallback(
    (blockId) => {
      const list = blockRowsById[String(blockId)] ?? [];
      return pickCheapestRow(list, { buyableOnly: true }) ?? pickCheapestRow(list) ?? undefined;
    },
    [blockRowsById]
  );

  const handleBlockEnter = (blockId) => {
    if (!blocksAvailable.has(String(blockId))) return;
    setHoverBlockId(String(blockId));
    const first = firstRowInBlock(blockId);
    onHoverGroup?.(first?.stableId ?? null);
  };

  const handleBlockLeave = () => {
    setHoverBlockId(null);
    onHoverGroup?.(null);
  };

  const handleBlockClick = (blockId) => {
    if (!blocksAvailable.has(String(blockId))) return;
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
        className="absolute inset-0 cursor-grab active:cursor-grabbing"
        style={{ touchAction: 'pan-y pinch-zoom' }}
        onPointerDown={panZoom.onPointerDown}
        onPointerMove={panZoom.onPointerMove}
        onPointerUp={panZoom.onPointerUp}
        onPointerCancel={panZoom.onPointerUp}
        role="application"
        aria-label="מפת הושבה — הופעה בבלומפילד — גרירה להזזה, פלוס ומינוס לזום"
      >
        <div className="flex h-full w-full items-center justify-center will-change-transform" style={panZoom.transformStyle}>
          <svg
            viewBox={viewBoxStr}
            width="100%"
            height="auto"
            className="block h-auto w-full max-h-full max-w-full select-none"
            preserveAspectRatio="xMidYMid meet"
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
              const status = blockStatusById[sid] || 'empty';
              const has = status !== 'empty';
              const isTaken = status === 'taken';
              const isAvailable = status === 'available';
              const isHi = highlightBlockId === sid && isAvailable;
              const isHover = hoverBlockId === sid && isAvailable;
              const rep = isAvailable ? firstRowInBlock(sid) : undefined;
              const raw = rep ? parseFloat(getTicketPrice(rep.firstTicket)) : NaN;
              const { fill } = isTaken
                ? { fill: MAP_FILL_TAKEN, tier: 0 }
                : isAvailable
                  ? fillForPriceTier(minP, maxP, raw)
                  : { fill: isHover ? FILL_EMPTY_HOVER : FILL_EMPTY, tier: 0 };
              const cur = rep ? resolveTicketCurrency(rep.firstTicket) : 'ILS';
              const priceLine = isTaken
                ? MAP_TAKEN_BUBBLE_LABEL
                : has && Number.isFinite(raw)
                  ? formatListingMoney(raw, cur)
                  : '';
              const pts = concertBlockPolygonPoints(b);
              const { cx, cy } = blockCenter(b);

              return (
                <g key={sid}>
                  <polygon
                    data-section-id={sid}
                    points={pts}
                    fill={fill}
                    stroke={isHi ? '#16a34a' : has ? STROKE_SECTION : STROKE_EMPTY}
                    strokeWidth={isHi ? STROKE_HIGHLIGHT_W : STROKE_INACTIVE_W}
                    filter={isAvailable ? 'url(#bfc-seat-soft)' : undefined}
                    className={`bloomfield-concert-map__seat${isAvailable ? ' bloomfield-concert-map__seat--listed' : ''}${
                      isTaken ? ' bloomfield-concert-map__seat--taken' : ''
                    }${isHi ? ' bloomfield-concert-map__seat--active' : ''}${
                      isHover ? ' bloomfield-concert-map__seat--hover' : ''
                    }`}
                    style={{
                      transition: 'stroke 0.15s ease, stroke-width 0.15s ease',
                      cursor: isTaken ? 'not-allowed' : isAvailable ? 'pointer' : 'default',
                    }}
                    onMouseEnter={isAvailable ? () => handleBlockEnter(sid) : undefined}
                    onMouseLeave={isAvailable ? handleBlockLeave : undefined}
                    onClick={isAvailable ? () => handleBlockClick(sid) : undefined}
                    role={isAvailable ? 'button' : undefined}
                    tabIndex={isAvailable ? 0 : undefined}
                    onKeyDown={
                      isAvailable
                        ? (e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              handleBlockClick(sid);
                            }
                          }
                        : undefined
                    }
                    aria-label={
                      isTaken
                        ? `${b.label}, נתפס`
                        : isAvailable
                          ? `${b.label}, ${priceLine}`
                          : b.label
                    }
                  />
                  <text
                    className="bloomfield-concert-map__seat-label"
                    x={cx}
                    y={cy}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill={has ? '#0f172a' : '#475569'}
                    fontSize={sid.length > 3 ? 28 : 32}
                    fontWeight="800"
                    fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                    style={{ pointerEvents: 'none' }}
                  >
                    {b.label}
                  </text>
                  {has && priceLine ? (
                    <BloomfieldMapPriceTag
                      cx={cx}
                      cy={cy}
                      priceLine={priceLine}
                      width={b.w}
                      height={b.h}
                      offsetX={Math.min(40, b.w * 0.34)}
                      offsetY={-Math.min(36, b.h * 0.42)}
                      variant={isTaken ? 'taken' : 'available'}
                    />
                  ) : null}
                </g>
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
