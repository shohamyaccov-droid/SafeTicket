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

const FILL_DEFAULT = '#dbe4f3';
const FILL_HOVER = '#a5b4fc';
const STROKE_SECTION = '#ffffff';
const FILL_ACTIVE = '#60a5fa';
const PITCH_GRASS = '#2f855a';
const LINE_WHITE = '#ffffff';
const PIN_INVERTED = '#222222';
/** Muted labels (Viagogo reference); active listings on green use dark text for contrast */
const TEXT_SECTION_MUTED = '#64748b';
const TEXT_ON_GREEN = '#0f172a';
const ROSE_600 = '#e11d48';
const BEST_BADGE_FILL = '#14532d';

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
  const [pinHoverId, setPinHoverId] = useState(null);
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

  const pins = useMemo(() => layoutPins(rows), [rows]);

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

  const pinInverted = (stableId) =>
    (highlightStableId != null && String(stableId) === String(highlightStableId)) ||
    (pinHoverId != null && String(stableId) === String(pinHoverId));

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
              {/* ~Tailwind shadow-md for price pins */}
              <filter id="bf-pin-shadow" x="-40%" y="-40%" width="180%" height="180%">
                <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#000000" floodOpacity="0.12" />
              </filter>
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
              return (
                <text
                  key={`lbl-${sid}`}
                  x={sec.cx}
                  y={sec.cy}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill={has ? TEXT_ON_GREEN : TEXT_SECTION_MUTED}
                  fontSize="8.5"
                  fontWeight={has ? '800' : '600'}
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

            {pins.map((p) => {
              const hasUrgency = Boolean(p.urgency);
              const bodyH = hasUrgency ? 34 : 26;
              const bodyW = p.isBestPrice ? 118 : 100;
              const pillR = bodyH / 2;
              const bodyTop = -bodyH - 4;
              const inverted = pinInverted(p.stableId);
              const bg = inverted ? PIN_INVERTED : '#ffffff';
              const stroke = inverted ? '#404040' : '#f3f4f6';
              const lineFill = inverted ? '#ffffff' : '#000000';
              const urgentFill = inverted ? '#fda4af' : ROSE_600;

              const priceY = hasUrgency ? bodyTop + 12 : bodyTop + bodyH / 2;
              const urgentY = bodyTop + 24;

              return (
                <g
                  key={p.blockId}
                  transform={`translate(${p.x}, ${p.y})`}
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => {
                    setPinHoverId(p.stableId);
                    onHoverGroup?.(p.stableId);
                  }}
                  onMouseLeave={() => {
                    setPinHoverId(null);
                    onHoverGroup?.(null);
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectGroup?.(p.stableId);
                  }}
                >
                  <g filter="url(#bf-pin-shadow)">
                    <rect
                      x={-bodyW / 2}
                      y={bodyTop}
                      width={bodyW}
                      height={bodyH}
                      rx={pillR}
                      ry={pillR}
                      fill={bg}
                      stroke={stroke}
                      strokeWidth={1}
                    />
                  </g>
                  {p.isBestPrice ? (
                    <g pointerEvents="none">
                      <rect
                        x={-bodyW / 2 + 7}
                        y={bodyTop + (bodyH - 18) / 2}
                        width={18}
                        height={18}
                        rx={4}
                        ry={4}
                        fill={BEST_BADGE_FILL}
                      />
                      <text
                        x={-bodyW / 2 + 16}
                        y={bodyTop + bodyH / 2}
                        textAnchor="middle"
                        dominantBaseline="central"
                        fill="#ffffff"
                        fontSize="10"
                        fontWeight="800"
                        style={{ direction: 'ltr' }}
                      >
                        $
                      </text>
                    </g>
                  ) : null}
                  <text
                    x={p.isBestPrice ? 7 : 0}
                    y={priceY}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill={lineFill}
                    fontSize="11.5"
                    fontWeight="800"
                    fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                    style={{
                      pointerEvents: 'none',
                      direction: 'ltr',
                      unicodeBidi: 'isolate',
                    }}
                  >
                    {p.priceLine}
                  </text>
                  {hasUrgency ? (
                    <text
                      x={p.isBestPrice ? 7 : 0}
                      y={urgentY}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fill={urgentFill}
                      fontSize="9.5"
                      fontWeight="600"
                      fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                      style={{ pointerEvents: 'none', lineHeight: 1 }}
                    >
                      {p.urgency}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </svg>
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
