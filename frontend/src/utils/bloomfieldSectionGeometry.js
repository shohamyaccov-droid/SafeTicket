/**
 * Bloomfield schematic — inner bowl stays rounded-rect; outer stadium footprint is a smooth ellipse.
 * Outer tier: sides are rays from (CX,CY) through inner rim points to the oval. Micro t-inset separates fills; stroke paints the gap.
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

export const CX = 500;
export const CY = 320;

export const PITCH_W = Math.round(300 * 0.83);
export const PITCH_H = Math.round(168 * 0.83);
export const PITCH_RX = 5;
export const PITCH_RY = 5;

const GAP = 22;
const STAND_DEPTH_LOWER = 48;
/** Thicker upper tier (radial depth) vs inner — Viagogo-like proportion */
const STAND_DEPTH_UPPER = 66;

/** Pull inner tier outer edge inward (px in viewBox) — opens the inter-tier channel. */
const RADIAL_INNER_BACK_TRIM = 5;
/** Constant radial depth (px) of the lower/upper tier gap: outer-front depth = inner-back depth + this. */
const TIER_CHANNEL_DEPTH = 16;

/** Extra semi-axis beyond nominal wo/2, ho/2 so bowl fill extends past seat ring (px). */
const BOWL_OVAL_MARGIN = 14;

/** Uniform perimeter inset per wedge side (~0.2° of full loop as t) so adjacent fills never share an edge. */
const T_SEP_PER_SIDE = 0.2 / 360;

const wi = PITCH_W + 2 * GAP;
const hi = PITCH_H + 2 * GAP;
const ri = Math.min(36, Math.min(wi, hi) * 0.11 + 24);

const wm = wi + 2 * STAND_DEPTH_LOWER;
const hm = hi + 2 * STAND_DEPTH_LOWER;

const innerBackDepth = STAND_DEPTH_LOWER - RADIAL_INNER_BACK_TRIM;
const wInnerBack = wi + 2 * innerBackDepth;
const hInnerBack = hi + 2 * innerBackDepth;
const rInnerBack = Math.min(ri + innerBackDepth, wInnerBack / 2 - 8, hInnerBack / 2 - 8);

const outerFrontDepth = innerBackDepth + TIER_CHANNEL_DEPTH;
const wOuterFront = wi + 2 * outerFrontDepth;
const hOuterFront = hi + 2 * outerFrontDepth;
const rOuterFront = Math.min(ri + outerFrontDepth, wOuterFront / 2 - 8, hOuterFront / 2 - 8);

const wo = wm + 2 * STAND_DEPTH_UPPER;
const ho = hm + 2 * STAND_DEPTH_UPPER;

/** Stadium outer silhouette — smooth oval (semi-axes in viewBox px). */
const OVAL_RX = wo / 2 + BOWL_OVAL_MARGIN;
const OVAL_RY = ho / 2 + BOWL_OVAL_MARGIN;

function fmt(n) {
  return Number(n.toFixed(2));
}

/**
 * Point on rounded-rect perimeter (cw from top-left of top edge), t ∈ [0,1).
 */
function pointOnPerimeter(t, w, h, r, cx, cy) {
  const hw = w / 2;
  const hh = h / 2;
  const xL = cx - hw;
  const xR = cx + hw;
  const yT = cy - hh;
  const yB = cy + hh;
  const rr = Math.min(r, hw, hh);
  const tw = w - 2 * rr;
  const th = h - 2 * rr;
  const q = (Math.PI * rr) / 2;
  const L = 2 * tw + 2 * th + 4 * q;
  let u = (((t % 1) + 1) % 1) * L;

  if (u <= tw) {
    return { x: xL + rr + u, y: yT };
  }
  u -= tw;
  if (u <= q) {
    const ang = u / rr;
    return { x: xR - rr + rr * Math.sin(ang), y: yT + rr - rr * Math.cos(ang) };
  }
  u -= q;
  if (u <= th) {
    return { x: xR, y: yT + rr + u };
  }
  u -= th;
  if (u <= q) {
    const ang = u / rr;
    return { x: xR - rr + rr * Math.cos(ang), y: yB - rr + rr * Math.sin(ang) };
  }
  u -= q;
  if (u <= tw) {
    return { x: xR - rr - u, y: yB };
  }
  u -= tw;
  if (u <= q) {
    const ang = u / rr;
    return { x: xL + rr - rr * Math.sin(ang), y: yB - rr + rr * Math.cos(ang) };
  }
  u -= q;
  if (u <= th) {
    return { x: xL, y: yB - rr - u };
  }
  u -= th;
  const ang = u / rr;
  return {
    x: xL + rr + rr * Math.cos(Math.PI + ang),
    y: yT + rr + rr * Math.sin(Math.PI + ang),
  };
}

/**
 * Intersection of ray C → P (through inner rim) with axis-aligned ellipse.
 * Uses unit direction so wedge sides are straight radials from the stadium center.
 */
function rayToEllipse(px, py, rx, ry) {
  let dx = px - CX;
  let dy = py - CY;
  const len = Math.hypot(dx, dy);
  if (len < 1e-12) {
    dx = 1;
    dy = 0;
  } else {
    dx /= len;
    dy /= len;
  }
  const t = 1 / Math.sqrt((dx * dx) / (rx * rx) + (dy * dy) / (ry * ry));
  return { x: CX + dx * t, y: CY + dy * t };
}

function applyMicroSep(t0, t1) {
  const span = t1 - t0;
  const pad = Math.min(T_SEP_PER_SIDE, span * 0.06);
  const ta = t0 + pad;
  const tb = t1 - pad;
  if (tb <= ta + 1e-10) {
    const m = (t0 + t1) / 2;
    return { t0: m - 1e-8, t1: m + 1e-8 };
  }
  return { t0: ta, t1: tb };
}

function ellipseParamAngle(px, py, rx, ry) {
  return Math.atan2((py - CY) / ry, (px - CX) / rx);
}

/** Prefer the arc whose midpoint sits farther from center than inner chord midpoint (outside / stands side). */
function pickOuterArcDelta(phiStart, phiEnd, imx, imy) {
  let d1 = phiEnd - phiStart;
  while (d1 > Math.PI) d1 -= 2 * Math.PI;
  while (d1 <= -Math.PI) d1 += 2 * Math.PI;
  const d2 = d1 > 0 ? d1 - 2 * Math.PI : d1 + 2 * Math.PI;
  function bulge(d) {
    const m = phiStart + d / 2;
    const ox = CX + OVAL_RX * Math.cos(m);
    const oy = CY + OVAL_RY * Math.sin(m);
    return Math.hypot(ox - CX, oy - CY) - Math.hypot(imx - CX, imy - CY);
  }
  return bulge(d1) >= bulge(d2) ? d1 : d2;
}

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

/** Full axis-aligned ellipse path (CW outline). */
export function ellipsePathD(cx, cy, rx, ry) {
  return [
    `M ${fmt(cx + rx)} ${fmt(cy)}`,
    `A ${fmt(rx)} ${fmt(ry)} 0 1 1 ${fmt(cx - rx)} ${fmt(cy)}`,
    `A ${fmt(rx)} ${fmt(ry)} 0 1 1 ${fmt(cx + rx)} ${fmt(cy)}`,
    'Z',
  ].join(' ');
}

function quadPath(o1, o2, i2, i1) {
  return `M ${fmt(o1.x)} ${fmt(o1.y)} L ${fmt(o2.x)} ${fmt(o2.y)} L ${fmt(i2.x)} ${fmt(i2.y)} L ${fmt(i1.x)} ${fmt(i1.y)} Z`;
}

/** Inner tier: rounded-rect annulus (both edges rounded-rect). */
function ringSlice(t0, t1, innerW, innerH, innerR, outerW, outerH, outerR) {
  const o1 = pointOnPerimeter(t0, outerW, outerH, outerR, CX, CY);
  const o2 = pointOnPerimeter(t1, outerW, outerH, outerR, CX, CY);
  const i1 = pointOnPerimeter(t0, innerW, innerH, innerR, CX, CY);
  const i2 = pointOnPerimeter(t1, innerW, innerH, innerR, CX, CY);
  const d = quadPath(o1, o2, i2, i1);
  const cx = (o1.x + o2.x + i1.x + i2.x) / 4;
  const cy = (o1.y + o2.y + i1.y + i2.y) / 4;
  return { d, cx, cy };
}

/**
 * Outer tier: inner edge = rounded rect; sides = straight radials C→perimeter(t);
 * outer edge = single elliptical arc (crisp, shared endpoints with neighbors).
 */
function ringSliceEllipseOuter(t0, t1, innerW, innerH, innerR) {
  const i1 = pointOnPerimeter(t0, innerW, innerH, innerR, CX, CY);
  const i2 = pointOnPerimeter(t1, innerW, innerH, innerR, CX, CY);
  const o1 = rayToEllipse(i1.x, i1.y, OVAL_RX, OVAL_RY);
  const o2 = rayToEllipse(i2.x, i2.y, OVAL_RX, OVAL_RY);
  const imx = (i1.x + i2.x) / 2;
  const imy = (i1.y + i2.y) / 2;
  const phiStart = ellipseParamAngle(o2.x, o2.y, OVAL_RX, OVAL_RY);
  const phiEnd = ellipseParamAngle(o1.x, o1.y, OVAL_RX, OVAL_RY);
  const dPhi = pickOuterArcDelta(phiStart, phiEnd, imx, imy);
  const largeArc = Math.abs(dPhi) > Math.PI ? 1 : 0;
  const sweep = dPhi > 0 ? 1 : 0;
  const arc = `A ${fmt(OVAL_RX)} ${fmt(OVAL_RY)} 0 ${largeArc} ${sweep} ${fmt(o1.x)} ${fmt(o1.y)}`;
  const d = [
    `M ${fmt(i1.x)} ${fmt(i1.y)}`,
    `L ${fmt(i2.x)} ${fmt(i2.y)}`,
    `L ${fmt(o2.x)} ${fmt(o2.y)}`,
    arc,
    'Z',
  ].join(' ');
  const phiM = phiStart + dPhi / 2;
  const omx = CX + OVAL_RX * Math.cos(phiM);
  const omy = CY + OVAL_RY * Math.sin(phiM);
  const cx = (imx + omx) / 2;
  const cy = (imy + omy) / 2;
  return { d, cx, cy };
}

const INNER_SPECS = [
  ...[301, 302, 303, 304, 305, 306, 307, 308, 309].map((n) => ({ id: String(n), faceLabel: String(n), w: 1.12 })),
  { id: '310', faceLabel: '310', w: 0.74 },
  { id: '311', faceLabel: '311', w: 0.74 },
  ...[312, 313, 314, 315, 316, 317].map((n) => ({ id: String(n), faceLabel: String(n), w: 2.15 })),
  { id: '318', faceLabel: '318', w: 0.88 },
  ...[328, 327, 326, 325, 324, 323, 322, 321, 320, 319].map((n) => ({ id: String(n), faceLabel: String(n), w: 1.12 })),
  { id: '329', faceLabel: '329', w: 0.74 },
  { id: '330', faceLabel: '330', w: 0.74 },
  { id: '331', faceLabel: '331', w: 0.74 },
  ...[332, 333, 334, 335, 336, 337].map((n) => ({ id: String(n), faceLabel: String(n), w: 2.15 })),
  { id: '338', faceLabel: '338', w: 0.88 },
];

function normalizeRanges(specs) {
  const sum = specs.reduce((a, s) => a + s.w, 0);
  let acc = 0;
  return specs.map((s) => {
    const t0 = acc / sum;
    acc += s.w;
    const t1 = acc / sum;
    return { ...s, t0, t1 };
  });
}

const INNER_RANGES = normalizeRanges(INNER_SPECS);

const INNER_WEDGES = INNER_RANGES.map((r) => {
  const { t0, t1 } = applyMicroSep(r.t0, r.t1);
  const { d, cx, cy } = ringSlice(t0, t1, wi, hi, ri, wInnerBack, hInnerBack, rInnerBack);
  return { id: r.id, faceLabel: r.faceLabel, d, cx, cy, tier: 'lower' };
});

function rangeForIds(ids) {
  const set = new Set(ids.map(String));
  const hits = INNER_RANGES.filter((x) => set.has(x.id));
  if (!hits.length) return { t0: 0, t1: 0 };
  return { t0: hits[0].t0, t1: hits[hits.length - 1].t1 };
}

const westInnerSpan = rangeForIds(['332', '333', '334', '335', '336', '337']);
const southInnerSpan = rangeForIds(['319', '320', '321', '322', '323', '324', '325', '326', '327', '328']);
const northInnerSpan = rangeForIds(['301', '302', '303', '304', '305', '306', '307', '308', '309']);

function splitSpan(t0, t1, n, i) {
  const dt = (t1 - t0) / n;
  return applyMicroSep(t0 + dt * i, t0 + dt * (i + 1));
}

const OUTER_WEDGES = [];

for (let i = 0; i < 12; i += 1) {
  const id = String(420 + i);
  const { t0, t1 } = splitSpan(westInnerSpan.t0, westInnerSpan.t1, 12, i);
  const { d, cx, cy } = ringSliceEllipseOuter(t0, t1, wOuterFront, hOuterFront, rOuterFront);
  OUTER_WEDGES.push({ id, faceLabel: id, d, cx, cy, tier: 'upper' });
}

const northMid = (northInnerSpan.t0 + northInnerSpan.t1) / 2;
const northHalfW = (northInnerSpan.t1 - northInnerSpan.t0) * 0.34;
const northOuterT0 = northMid - northHalfW / 2;
const northOuterT1 = northMid + northHalfW / 2;
for (let i = 0; i < 3; i += 1) {
  const id = String(404 + i);
  const { t0, t1 } = splitSpan(northOuterT0, northOuterT1, 3, i);
  const { d, cx, cy } = ringSliceEllipseOuter(t0, t1, wOuterFront, hOuterFront, rOuterFront);
  OUTER_WEDGES.push({ id, faceLabel: id, d, cx, cy, tier: 'upper' });
}

for (let i = 0; i < 9; i += 1) {
  const id = String(221 + i);
  const { t0, t1 } = splitSpan(southInnerSpan.t0, southInnerSpan.t1, 9, i);
  const { d, cx, cy } = ringSliceEllipseOuter(t0, t1, wOuterFront, hOuterFront, rOuterFront);
  OUTER_WEDGES.push({ id, faceLabel: id, d, cx, cy, tier: 'upper' });
}

export const SECTION_WEDGES = [...INNER_WEDGES, ...OUTER_WEDGES];

const ALL_BLOCK_IDS = new Set(SECTION_WEDGES.map((s) => s.id));

/** @deprecated */
export const LOWER_WEDGE_IDS = INNER_WEDGES.map((w) => w.id);
/** @deprecated */
export const UPPER_WEDGE_IDS = OUTER_WEDGES.map((w) => w.id);
/** @deprecated */
export const WEDGE_IDS = LOWER_WEDGE_IDS;

export function blockIdFromSectionNumber(numStr) {
  if (!numStr || numStr === '—') return '301';
  const n = parseInt(String(numStr), 10);
  if (Number.isNaN(n)) return '301';
  const s = String(n);
  if (ALL_BLOCK_IDS.has(s)) return s;
  return '301';
}

export const GAP_ROUNDRECT_D = roundedRectPathD(CX, CY, wi, hi, ri);

export const PITCH_X = CX - PITCH_W / 2;
export const PITCH_Y = CY - PITCH_H / 2;

export const BOWL_OUTER_D = ellipsePathD(CX, CY, OVAL_RX, OVAL_RY);
