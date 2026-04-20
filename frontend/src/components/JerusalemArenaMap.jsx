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
  COURT_X,
  COURT_Y,
  COURT_W,
  COURT_H,
  COURT_RX,
  ARENA_FLOOR_RX,
  ARENA_FLOOR_RY,
} from '../utils/jerusalemArenaGeometry';

const FILL_DEFAULT = '#f3f4f6';
const STROKE_SECTION = '#ffffff';
const FILL_ACTIVE = '#a3e635';
const COURT_WOOD = '#d4a574';
const COURT_STROKE = '#b88652';
const LINE_COURT = '#92400e';
const PIN_INVERTED = '#222222';
const TEXT_SECTION_MUTED = '#9ca3af';
const TEXT_ON_GREEN = '#14532d';
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

function layoutPins(rows) {
  const floorPrice = globalMinListingPrice(rows);
  const byBlock = {};
  for (const row of rows) {
    const bid = row.jerusalem?.blockId;
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

export default function JerusalemArenaMap({
  rows = [],
  highlightStableId = null,
  onSelectGroup,
  onHoverGroup,
}) {
  const [pinHoverId, setPinHoverId] = useState(null);
  const panZoom = useVenueMapPanZoom({ minScale: 0.65, maxScale: 2.8, zoomStep: 0.14 });

  const blocksWithListings = useMemo(() => {
    const s = new Set();
    for (const r of rows) {
      const bid = r.jerusalem?.blockId;
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
    const raw = hit?.jerusalem?.blockId;
    return raw != null && raw !== '' ? String(raw) : null;
  }, [rows, highlightStableId]);

  const pins = useMemo(() => layoutPins(rows), [rows]);

  const firstRowInBlock = useCallback((blockId) => {
    const b = String(blockId);
    const list = rows.filter((r) => String(r.jerusalem?.blockId ?? '') === b);
    return pickCheapestRow(list) ?? undefined;
  }, [rows]);

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

  const centerCircleR = Math.min(COURT_W, COURT_H) * 0.12;
  const penW = COURT_W * 0.42;
  const penD = COURT_H * 0.2;

  const pinInverted = (stableId) =>
    (highlightStableId != null && String(stableId) === String(highlightStableId)) ||
    (pinHoverId != null && String(stableId) === String(pinHoverId));

  return (
    <div className="bloomfield-map-root relative w-full aspect-[800/600] max-h-[min(540px,74vh)] min-h-[260px] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
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

      <div className="absolute top-2 left-1/2 z-[5] -translate-x-1/2">
        <button
          type="button"
          onClick={panZoom.resetView}
          className="rounded-full bg-slate-900 px-4 py-1.5 text-xs font-semibold text-white shadow-md hover:bg-slate-800"
        >
          Search this area
        </button>
      </div>

      <div
        className="absolute inset-0 cursor-grab touch-none active:cursor-grabbing"
        onPointerDown={panZoom.onPointerDown}
        onPointerMove={panZoom.onPointerMove}
        onPointerUp={panZoom.onPointerUp}
        onPointerCancel={panZoom.onPointerUp}
        role="application"
        aria-label="מפת פיס ארנה ירושלים — גרירה להזזה, זום עם פלוס ומינוס"
      >
        <div
          className="flex h-full w-full items-center justify-center will-change-transform"
          style={panZoom.transformStyle}
        >
          <svg
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            className="h-full w-full max-h-[540px] select-none overflow-visible"
            role="img"
            aria-label="Pais Arena Jerusalem seating map"
          >
            <defs>
              <filter id="ja-pin-shadow" x="-40%" y="-40%" width="180%" height="180%">
                <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#000000" floodOpacity="0.12" />
              </filter>
            </defs>

            <rect width={VIEW_W} height={VIEW_H} fill="#ffffff" />

            <ellipse
              cx={CX}
              cy={CY}
              rx={ARENA_FLOOR_RX}
              ry={ARENA_FLOOR_RY}
              fill="#f3f4f6"
              stroke="#e5e7eb"
              strokeWidth="2"
            />

            <rect
              x={COURT_X}
              y={COURT_Y}
              width={COURT_W}
              height={COURT_H}
              rx={COURT_RX}
              fill={COURT_WOOD}
              stroke={COURT_STROKE}
              strokeWidth="2"
            />

            <ellipse cx={CX} cy={CY} rx={centerCircleR} ry={centerCircleR} fill="none" stroke={LINE_COURT} strokeWidth="2" />
            <line x1={CX} y1={COURT_Y} x2={CX} y2={COURT_Y + COURT_H} stroke={LINE_COURT} strokeWidth="2" strokeDasharray="4,4" />
            <line x1={COURT_X} y1={COURT_Y + 60} x2={COURT_X + 80} y2={COURT_Y + 60} stroke={LINE_COURT} strokeWidth="1.5" />
            <line x1={COURT_X} y1={COURT_Y + 100} x2={COURT_X + 80} y2={COURT_Y + 100} stroke={LINE_COURT} strokeWidth="1.5" />
            <line
              x1={COURT_X + COURT_W - 80}
              y1={COURT_Y + 60}
              x2={COURT_X + COURT_W}
              y2={COURT_Y + 60}
              stroke={LINE_COURT}
              strokeWidth="1.5"
            />
            <line
              x1={COURT_X + COURT_W - 80}
              y1={COURT_Y + 100}
              x2={COURT_X + COURT_W}
              y2={COURT_Y + 100}
              stroke={LINE_COURT}
              strokeWidth="1.5"
            />
            <rect
              x={CX - penW / 2}
              y={COURT_Y}
              width={penW}
              height={penD}
              fill="none"
              stroke={LINE_COURT}
              strokeWidth="1.25"
            />
            <rect
              x={CX - penW / 2}
              y={COURT_Y + COURT_H - penD}
              width={penW}
              height={penD}
              fill="none"
              stroke={LINE_COURT}
              strokeWidth="1.25"
            />

            {safeSectionWedges.map((sec) => {
              if (!isRenderableWedge(sec)) return null;
              const sid = String(sec.id);
              const has = blocksWithListings.has(sid);
              const isHi = highlightBlockId === sid;
              const fill = has ? FILL_ACTIVE : FILL_DEFAULT;
              return (
                <path
                  key={sid}
                  data-section-id={sid}
                  d={sec.d}
                  fill={fill}
                  fillOpacity={1}
                  shapeRendering="geometricPrecision"
                  stroke={isHi ? '#0ea5e9' : STROKE_SECTION}
                  strokeWidth={isHi ? STROKE_HIGHLIGHT_W : STROKE_INACTIVE_W}
                  strokeLinejoin={isHi ? 'round' : 'miter'}
                  className="transition-[stroke,fill-opacity] duration-150 ease-out"
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
                  fontSize="8"
                  fontWeight={has ? '800' : '500'}
                  fontFamily="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
                  style={{ pointerEvents: 'none', userSelect: 'none', writingMode: 'horizontal-tb' }}
                >
                  {sec.faceLabel}
                </text>
              );
            })}

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
                  <g filter="url(#ja-pin-shadow)">
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
                    style={{ pointerEvents: 'none', direction: 'ltr', unicodeBidi: 'isolate' }}
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
    </div>
  );
}
