/**
 * Bloomfield schematic: elliptical wedge sections around pitch (Viagogo-style layout).
 * IDs 301–310 (N), 311–318 (E), 319–328 (S), 329–336 (W) — clockwise from top.
 */

export const VIEW_W = 1000;
export const VIEW_H = 636;

export const CX = 500;
export const CY = 318;

/** Outer rim of seating ring */
const RX_OUT = 392;
const RY_OUT = 244;
/** Inner rim (meets pitch) */
const RX_IN = 176;
const RY_IN = 102;

/** Pitch ellipse (drawn above wedges) */
export const RX_PITCH = 168;
export const RY_PITCH = 90;

const WEDGE_COUNT = 36;

function fmt(n) {
  return Number(n.toFixed(2));
}

function pt(cx, cy, rx, ry, t) {
  return [cx + rx * Math.cos(t), cy + ry * Math.sin(t)];
}

export function buildWedgePath(t1, t2, rxOut, ryOut, rxIn, ryIn) {
  const [x1o, y1o] = pt(CX, CY, rxOut, ryOut, t1);
  const [x2o, y2o] = pt(CX, CY, rxOut, ryOut, t2);
  const [x1i, y1i] = pt(CX, CY, rxIn, ryIn, t1);
  const [x2i, y2i] = pt(CX, CY, rxIn, ryIn, t2);
  return `M ${fmt(x1o)} ${fmt(y1o)} A ${rxOut} ${ryOut} 0 0 1 ${fmt(x2o)} ${fmt(y2o)} L ${fmt(x2i)} ${fmt(y2i)} A ${rxIn} ${ryIn} 0 0 0 ${fmt(x1i)} ${fmt(y1i)} Z`;
}

/** Ordered clockwise from north-centre: 301…310, 311…318, 319…328, 329…336 */
export const WEDGE_IDS = (() => {
  const ids = [];
  for (let i = 0; i < 10; i += 1) ids.push(String(301 + i));
  for (let i = 0; i < 8; i += 1) ids.push(String(311 + i));
  for (let i = 0; i < 10; i += 1) ids.push(String(319 + i));
  for (let i = 0; i < 8; i += 1) ids.push(String(329 + i));
  return ids;
})();

/**
 * Map any ticket section number to a wedge id (deterministic bucket on last two digits).
 */
export function blockIdFromSectionNumber(numStr) {
  if (!numStr || numStr === '—') return WEDGE_IDS[0];
  const n = parseInt(String(numStr), 10);
  if (Number.isNaN(n)) return WEDGE_IDS[0];
  const idx = ((n % 100) + 35) % WEDGE_COUNT;
  return WEDGE_IDS[idx];
}

export const SECTION_WEDGES = WEDGE_IDS.map((id, i) => {
  const tMid = -Math.PI / 2 + (i + 0.5) * ((2 * Math.PI) / WEDGE_COUNT);
  const t1 = tMid - Math.PI / WEDGE_COUNT;
  const t2 = tMid + Math.PI / WEDGE_COUNT;
  const d = buildWedgePath(t1, t2, RX_OUT, RY_OUT, RX_IN, RY_IN);
  const rxMid = (RX_IN + RX_OUT) / 2;
  const ryMid = (RY_IN + RY_OUT) / 2;
  const [px, py] = pt(CX, CY, rxMid, ryMid, tMid);
  return { id, d, cx: px, cy: py, tMid };
});

/** Bowl rim ellipse (under seating wedges) */
export const BOWL_RX = 408;
export const BOWL_RY = 248;
