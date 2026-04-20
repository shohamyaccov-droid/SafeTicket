/**
 * Bloomfield schematic — Viagogo-style “rounded rectangle” football bowl:
 * rectangular pitch + gap + thick rounded-rect stand ring (straight N/S/E/W, curved corners).
 * Sections are quads between outer and inner rounded rectangles (no elliptical donut).
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

export const CX = 500;
export const CY = 320;

/** Pitch — sharp rectangle (max rx 5) */
export const PITCH_W = 300;
export const PITCH_H = 168;
export const PITCH_RX = 5;
export const PITCH_RY = 5;

/** Clear strip between pitch edge and stand inner edge */
const GAP = 22;

/** Stand depth (outer bowl − inner hole) */
const STAND_DEPTH = 92;

const wi = PITCH_W + 2 * GAP;
const hi = PITCH_H + 2 * GAP;
const ri = 38;

const wo = wi + 2 * STAND_DEPTH;
const ho = hi + 2 * STAND_DEPTH;
const ro = ri + STAND_DEPTH;

const WEDGE_COUNT = 36;

function fmt(n) {
  return Number(n.toFixed(2));
}

/**
 * Point on outer rounded-rect perimeter, clockwise from top-left of top straight edge.
 * @param {number} t - 0..1 along perimeter
 */
function pointOnOuterPerimeter(t) {
  const hw = wo / 2;
  const hh = ho / 2;
  const xL = CX - hw;
  const xR = CX + hw;
  const yT = CY - hh;
  const yB = CY + hh;
  const r = Math.min(ro, hw, hh);
  const tw = wo - 2 * r;
  const th = ho - 2 * r;
  const q = (Math.PI * r) / 2;
  const L = 2 * tw + 2 * th + 4 * q;
  let u = (((t % 1) + 1) % 1) * L;

  if (u <= tw) {
    return { x: xL + r + u, y: yT };
  }
  u -= tw;
  if (u <= q) {
    const ang = u / r;
    return { x: xR - r + r * Math.sin(ang), y: yT + r - r * Math.cos(ang) };
  }
  u -= q;
  if (u <= th) {
    return { x: xR, y: yT + r + u };
  }
  u -= th;
  if (u <= q) {
    const ang = u / r;
    return { x: xR - r + r * Math.cos(ang), y: yB - r + r * Math.sin(ang) };
  }
  u -= q;
  if (u <= tw) {
    return { x: xR - r - u, y: yB };
  }
  u -= tw;
  if (u <= q) {
    const ang = u / r;
    return { x: xL + r - r * Math.sin(ang), y: yB - r + r * Math.cos(ang) };
  }
  u -= q;
  if (u <= th) {
    return { x: xL, y: yB - r - u };
  }
  u -= th;
  const ang = u / r;
  return {
    x: xL + r + r * Math.cos(Math.PI + ang),
    y: yT + r + r * Math.sin(Math.PI + ang),
  };
}

/** Inner stand boundary point (same direction from center as outer point) */
function innerFromOuter(ox, oy) {
  return {
    x: CX + (ox - CX) * (wi / wo),
    y: CY + (oy - CY) * (hi / ho),
  };
}

/** SVG d for a filled rounded rect (stroke optional) */
export function roundedRectPathD(cx, cy, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  const hw = w / 2;
  const hh = h / 2;
  const xL = cx - hw;
  const xR = cx + hw;
  const yT = cy - hh;
  const yB = cy + hh;
  return [
    `M ${fmt(xL + rr)} ${fmt(yT)}`,
    `H ${fmt(xR - rr)}`,
    `A ${fmt(rr)} ${fmt(rr)} 0 0 1 ${fmt(xR)} ${fmt(yT + rr)}`,
    `V ${fmt(yB - rr)}`,
    `A ${fmt(rr)} ${fmt(rr)} 0 0 1 ${fmt(xR - rr)} ${fmt(yB)}`,
    `H ${fmt(xL + rr)}`,
    `A ${fmt(rr)} ${fmt(rr)} 0 0 1 ${fmt(xL)} ${fmt(yB - rr)}`,
    `V ${fmt(yT + rr)}`,
    `A ${fmt(rr)} ${fmt(rr)} 0 0 1 ${fmt(xL + rr)} ${fmt(yT)}`,
    'Z',
  ].join(' ');
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

export function blockIdFromSectionNumber(numStr) {
  if (!numStr || numStr === '—') return WEDGE_IDS[0];
  const n = parseInt(String(numStr), 10);
  if (Number.isNaN(n)) return WEDGE_IDS[0];
  const idx = ((n % 100) + 35) % WEDGE_COUNT;
  return WEDGE_IDS[idx];
}

function quadPath(o1, o2, i2, i1) {
  return `M ${fmt(o1.x)} ${fmt(o1.y)} L ${fmt(o2.x)} ${fmt(o2.y)} L ${fmt(i2.x)} ${fmt(i2.y)} L ${fmt(i1.x)} ${fmt(i1.y)} Z`;
}

export const SECTION_WEDGES = WEDGE_IDS.map((id, i) => {
  const t1 = i / WEDGE_COUNT;
  const t2 = (i + 1) / WEDGE_COUNT;
  const o1 = pointOnOuterPerimeter(t1);
  const o2 = pointOnOuterPerimeter(t2);
  const i1 = innerFromOuter(o1.x, o1.y);
  const i2 = innerFromOuter(o2.x, o2.y);
  const d = quadPath(o1, o2, i2, i1);
  const cx = (o1.x + o2.x + i1.x + i2.x) / 4;
  const cy = (o1.y + o2.y + i1.y + i2.y) / 4;
  return { id, d, cx, cy };
});

/** Concours / gap fill inside stand hole (under pitch in z-order) */
export const GAP_ROUNDRECT_D = roundedRectPathD(CX, CY, wi, hi, ri);

/** Pitch placement */
export const PITCH_X = CX - PITCH_W / 2;
export const PITCH_Y = CY - PITCH_H / 2;

/** Subtle outer bowl (rounded rect) behind stands */
export const BOWL_OUTER_D = roundedRectPathD(CX, CY, wo + 24, ho + 24, ro + 14);
