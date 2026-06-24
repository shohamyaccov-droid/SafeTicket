/* eslint-disable react/prop-types -- project does not use PropTypes consistently */
import { useState, useMemo, useCallback } from 'react';
import { useVenueMapPanZoom } from '../hooks/useVenueMapPanZoom';
import { getTicketPrice, formatMoney, resolveTicketCurrency } from '../utils/priceFormat';
import {
  VIEW_W,
  VIEW_H,
  CX,
  CY,
  SECTION_WEDGES,
  GAP_ROUNDRECT_D,
  BOWL_OUTER_D,
  PITCH_X,
  PITCH_Y,
  PITCH_W,
  PITCH_H,
  PITCH_RX,
  PITCH_RY,
} from '../utils/bloomfieldSectionGeometry';
import './BloomfieldStadiumMap.css';
import BloomfieldMapPriceTag, { menoraPriceTagMetrics } from './BloomfieldMapPriceTag';

const FILL_DEFAULT = '#dbe4f3';
const FILL_HOVER = '#a5b4fc';
const STROKE_SECTION = '#ffffff';
const FILL_ACTIVE = '#60a5fa';
const PITCH_GRASS = '#2f855a';
const LINE_WHITE = '#ffffff';
/** Muted labels (Viagogo reference); active listings on green use dark text for contrast */
const TEXT_SECTION_MUTED = '#64748b';

const STROKE_INACTIVE_W = 1.5;
const STROKE_HIGHLIGHT_W = 2.75;

function isRenderableWedge(sec) {
  return (
    sec &&
    typeof sec.id === 'string' &&
    typeof sec.d === 'string' &&
    sec.d.length > 0 &&
    !sec.d.includes('NaN') &&
    Number.isFinite(sec.cx) &&
    Number.isFinite(sec.cy)
  );
}

/** One listing per block for map affordances: lowest displayed price wins. */
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

/** Lowest price across all visible rows (for “best price” pin badge). */
function globalMinListingPrice(rows) {
  let minP = Infinity;
  for (const row of rows) {
    const raw = parseFloat(getTicketPrice(row.firstTicket));
    if (Number.isFinite(raw) && raw < minP) minP = raw;
  }
  return minP;
}

/** One pin per map block: price is the minimum among listings in that section only. */
function layoutPins(rows) {
  const floorPrice = globalMinListingPrice(rows);
  const byBlock = {};
  for (const row of rows) {
    const bid = row.bloomfield?.blockId;
    if (bid == null || bid === '') continue;
    const k = String(bid);
    if (!byBlock[k]) byBlock[k] = [];
    byBlock[k].push(row);
  }
  const pins = [];
  for (const bid of Object.keys(byBlock)) {
    const list = byBlock[bid];
    const rep = pickCheapestRow(list);
    if (!rep) continue;
    const sid = String(bid);
    const w = SECTION_WEDGES.find((x) => String(x.id) === sid);
    const cx0 = w?.cx ?? CX;
    const cy0 = w?.cy ?? CY;
    const t = rep.firstTicket;
    const raw = parseFloat(getTicketPrice(t));
    const cur = resolveTicketCurrency(t);
    const priceLabel = formatMoney(Number.isFinite(raw) ? raw : 0, cur);
    const n = rep.group.available_count ?? 0;
    const isBestPrice =
      Number.isFinite(raw) &&
      Number.isFinite(floorPrice) &&
      Math.abs(raw - floorPrice) < 0.005;
    pins.push({
      stableId: rep.stableId,
      blockId: sid,
      x: cx0,
      y: cy0 - 6,
      priceLine: priceLabel,
      urgency: n > 0 && n < 5 ? `${n} left` : null,
      isBestPrice,
    });
  }
  return pins;
}

export default function BloomfieldStadiumMap({
  rows = [],
  highlightStableId = null,
  onSelectGroup,
  onHoverGroup,
}) {
  const [hoverBlockId, setHoverBlockId] = useState(null);
  const panZoom = useVenueMapPanZoom({ minScale: 0.65, maxScale: 2.8, zoomStep: 0.14 });

  const blocksWithListings = useMemo(() => {
    const s = new Set();
    for (const r of rows) {
      const bid = r.bloomfield?.blockId;
      if (bid != null && bid !== '') s.add(String(bid));
    }
    return s;
  }, [rows]);

  const safeSectionWedges = useMemo(
    () => (Array.isArray(SECTION_WEDGES) ? SECTION_WEDGES.filter(isRenderableWedge) : []),
    []
  );

  const highlightBlockId = useMemo(() => {
    if (highlightStableId == null || highlightStableId === '') return null;
    const hit = rows.find((r) => String(r.stableId) === String(highlightStableId));
    const raw = hit?.bloomfield?.blockId;
    return raw != null && raw !== '' ? String(raw) : null;
  }, [rows, highlightStableId]);

  const pinsByBlock = useMemo(() => {
    const m = {};
    for (const p of layoutPins(rows)) {
      m[p.blockId] = p;
    }
    return m;
  }, [rows]);

  const firstRowInBlock = useCallback((blockId) => {
    const b = String(blockId);
    const list = rows.filter((r) => String(r.bloomfield?.blockId ?? '') === b);
    return pickCheapestRow(list) ?? undefined;
  }, [rows]);

  const handleBlockEnter = (blockId) => {
    const has = blocksWithListings.has(String(blockId));
    if (!has) return;
    setHoverBlockId(String(blockId));
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

  const penW = PITCH_W * 0.42;
  const penD = PITCH_H * 0.2;
  const centerCircleR = Math.min(PITCH_W, PITCH_H) * 0.12;

  return (
    <div className="bloomfield-map-shell">
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
        className="absolute inset-0 cursor-grab active:cursor-grabbing"
        style={{ touchAction: 'pan-x pan-y' }}
        onPointerDown={panZoom.onPointerDown}
        onPointerMove={panZoom.onPointerMove}
        onPointerUp={panZoom.onPointerUp}
        onPointerCancel={panZoom.onPointerUp}
        role="application"
        aria-label="Bloomfield seating map — drag to pan, use plus and minus to zoom"
      >
        <div
          className="flex h-full w-full items-center justify-center will-change-transform"
          style={panZoom.transformStyle}
        >
          <svg
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            className="h-full w-full max-h-[540px] select-none overflow-visible"
            role="img"
            aria-label="Bloomfield stadium seating map"
          >
            <defs>
              <linearGradient id="bf-stage-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#1e3a8a" />
                <stop offset="100%" stopColor="#312e81" />
              </linearGradient>
            </defs>

            <rect width={VIEW_W} height={VIEW_H} fill="#f8fafc" />

            <path d={BOWL_OUTER_D} fill="#eef2ff" stroke="#cbd5e1" strokeWidth="1.1" />

            <path d={GAP_ROUNDRECT_D} fill="#ffffff" stroke="none" />

            {safeSectionWedges.map((sec) => {
              if (!isRenderableWedge(sec)) return null;
              const sid = String(sec.id);
              const has = blocksWithListings.has(sid);
              const isHi = highlightBlockId === sid;
              const isHover = hoverBlockId === sid;
              const fill = has ? (isHover ? FILL_HOVER : FILL_ACTIVE) : FILL_DEFAULT;
              return (
                <path
                  key={sid}
                  data-section-id={sid}
                  d={sec.d}
                  fill={fill}
                  fillOpacity={1}
                  shapeRendering="geometricPrecision"
                  stroke={isHi || isHover ? '#1d4ed8' : STROKE_SECTION}
                  strokeWidth={isHi || isHover ? STROKE_HIGHLIGHT_W : STROKE_INACTIVE_W}
                  strokeLinejoin={isHi ? 'round' : 'miter'}
                  className={`bloomfield-stadium-section transition-[stroke,fill-opacity,transform] duration-150 ease-out${isHover ? ' is-hover' : ''}${isHi ? ' is-active' : ''}`}
                  style={{ cursor: has ? 'pointer' : 'default' }}
                  onMouseEnter={() => handleBlockEnter(sid)}
                  onMouseLeave={handleBlockLeave}
                  onClick={() => handleBlockClick(sid)}
                />
              );
            })}

            {safeSectionWedges.map((sec) => {
              if (!isRenderableWedge(sec)) return null;
              const sid = String(sec.id);
              const has = blocksWithListings.has(sid);
              const pin = pinsByBlock[sid];
              const priceLine = pin?.priceLine ?? '';

              if (has && pin && priceLine) {
                return (
                  <BloomfieldMapPriceTag
                    key={`lbl-${sid}`}
                    cx={sec.cx}
                    cy={sec.cy}
                    priceLine={priceLine}
                    metrics={menoraPriceTagMetrics(72, 28, priceLine)}
                  />
                );
              }

              return (
                <text
                  key={`lbl-${sid}`}
                  x={sec.cx}
                  y={sec.cy}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill={TEXT_SECTION_MUTED}
                  fontSize="8.5"
                  fontWeight="600"
                  fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                  style={{
                    pointerEvents: 'none',
                    userSelect: 'none',
                    writingMode: 'horizontal-tb',
                    letterSpacing: '0.02em',
                    textRendering: 'geometricPrecision',
                  }}
                >
                  {sec.faceLabel}
                </text>
              );
            })}

            <rect
              x={PITCH_X + 2}
              y={PITCH_Y + 2}
              width={PITCH_W - 4}
              height={PITCH_H - 4}
              rx={PITCH_RX - 1}
              ry={PITCH_RY - 1}
              fill={PITCH_GRASS}
              stroke={LINE_WHITE}
              strokeWidth="1.25"
            />

            <line
              x1={CX}
              y1={PITCH_Y}
              x2={CX}
              y2={PITCH_Y + PITCH_H}
              stroke={LINE_WHITE}
              strokeWidth="1.25"
            />

            <circle
              cx={CX}
              cy={CY}
              r={centerCircleR}
              fill="none"
              stroke={LINE_WHITE}
              strokeWidth="1.25"
            />

            <rect
              x={CX - 72}
              y={PITCH_Y - 30}
              width={144}
              height={24}
              rx={12}
              ry={12}
              fill="url(#bf-stage-gradient)"
              stroke="#1e40af"
              strokeWidth="1"
            />
            <text
              x={CX}
              y={PITCH_Y - 18}
              textAnchor="middle"
              dominantBaseline="central"
              fill="#ffffff"
              fontSize="10.5"
              fontWeight="800"
              style={{ letterSpacing: '0.12em', pointerEvents: 'none', userSelect: 'none' }}
            >
              STAGE
            </text>

            <rect
              x={CX - penW / 2}
              y={PITCH_Y}
              width={penW}
              height={penD}
              fill="none"
              stroke={LINE_WHITE}
              strokeWidth="1.25"
            />
            <rect
              x={CX - penW / 2}
              y={PITCH_Y + PITCH_H - penD}
              width={penW}
              height={penD}
              fill="none"
              stroke={LINE_WHITE}
              strokeWidth="1.25"
            />

          </svg>
        </div>
      </div>
    </div>
      <div className="bloomfield-map-legend" aria-hidden="true">
        <span className="bloomfield-map-legend__item">
          <i className="swatch swatch--available" /> זמין
        </span>
        <span className="bloomfield-map-legend__item">
          <i className="swatch swatch--selected" /> נבחר
        </span>
        <span className="bloomfield-map-legend__item">
          <i className="swatch swatch--unavailable" /> לא זמין
        </span>
      </div>
    </div>
  );
}
