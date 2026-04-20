/**
 * Bloomfield — hardcoded Viagogo-style section map.
 * Inner ring: explicit CW order on inner bowl. Outer ring: West 420–431, North 404–406, South 221–229 only (East is single-tier).
 * Stadium shell: horizontal capsule (rounded rect with r = h/2) so touchline sides are longer than goal ends.
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

export const CX = 500;
export const CY = 320;

export const PITCH_W = Math.round(300 * 0.83);
export const PITCH_H = Math.round(168 * 0.83);
export const PITCH_RX = 5;
export const PITCH_RY = 5;

/** Moat pitch ↔ inner rim */
const GAP = 32;
const STAND_DEPTH_LOWER = 50;
const STAND_DEPTH_UPPER = 50;

const RADIAL_INNER_BACK_TRIM = 6;
const RADIAL_OUTER_FRONT_EXTRA = 12;

/**
 * Normalized gap between adjacent blocks (t space). Slightly larger for a consistent white grid.
 */
const ANGULAR_PAD_T = 0.00115;

const wi = PITCH_W + 2 * GAP;
const hi = PITCH_H + 2 * GAP;
/** Inner hole: moderate corners (pitch surround). */
const ri = Math.min(28, Math.min(wi, hi) * 0.09 + 18);

const wm = wi + 2 * STAND_DEPTH_LOWER;
const hm = hi + 2 * STAND_DEPTH_LOWER;

const innerBackDepth = STAND_DEPTH_LOWER - RADIAL_INNER_BACK_TRIM;
const wInnerBack = wi + 2 * innerBackDepth;
const hInnerBack = hi + 2 * innerBackDepth;
const rInnerBack = Math.min(ri + innerBackDepth, wInnerBack / 2 - 8, hInnerBack / 2 - 8);

const outerFrontDepth = STAND_DEPTH_LOWER + RADIAL_OUTER_FRONT_EXTRA;
const wOuterFront = wi + 2 * outerFrontDepth;
const hOuterFront = hi + 2 * outerFrontDepth;
const rOuterFront = Math.min(ri + outerFrontDepth, wOuterFront / 2 - 8, hOuterFront / 2 - 8);

/** Outer bowl: wider than tall (sidelines > goal ends). */
const wo = wm + 2 * STAND_DEPTH_UPPER;
const ho = hm + 2 * STAND_DEPTH_UPPER;
/** Capsule ends: semicircles on left/right (not a tall ellipse). */
const ro = ho / 2;

function fmt(n) {
  return Number(n.toFixed(4));
}

/**
 * Point on rounded-rect perimeter, t ∈ [0,1), CW from west end of top edge.
 * With r = h/2 and w ≥ h this traces a horizontal stadium/capsule.
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

function quadPath(o1, o2, i2, i1) {
  return `M ${fmt(o1.x)} ${fmt(o1.y)} L ${fmt(o2.x)} ${fmt(o2.y)} L ${fmt(i2.x)} ${fmt(i2.y)} L ${fmt(i1.x)} ${fmt(i1.y)} Z`;
}

/** Shoelace centroid of quad (o1→o2→i2→i1). */
function quadCentroid(o1, o2, i2, i1) {
  const pts = [o1, o2, i2, i1];
  let a = 0;
  let cxSum = 0;
  let cySum = 0;
  for (let i = 0; i < 4; i += 1) {
    const j = (i + 1) % 4;
    const cross = pts[i].x * pts[j].y - pts[j].x * pts[i].y;
    a += cross;
    cxSum += (pts[i].x + pts[j].x) * cross;
    cySum += (pts[i].y + pts[j].y) * cross;
  }
  a *= 0.5;
  if (Math.abs(a) < 1e-8) {
    return {
      cx: (o1.x + o2.x + i1.x + i2.x) / 4,
      cy: (o1.y + o2.y + i1.y + i2.y) / 4,
    };
  }
  return { cx: cxSum / (6 * a), cy: cySum / (6 * a) };
}

function ringSlice(t0, t1, innerW, innerH, innerR, outerW, outerH, outerR) {
  const o1 = pointOnPerimeter(t0, outerW, outerH, outerR, CX, CY);
  const o2 = pointOnPerimeter(t1, outerW, outerH, outerR, CX, CY);
  const i1 = pointOnPerimeter(t0, innerW, innerH, innerR, CX, CY);
  const i2 = pointOnPerimeter(t1, innerW, innerH, innerR, CX, CY);
  const d = quadPath(o1, o2, i2, i1);
  const { cx, cy } = quadCentroid(o1, o2, i2, i1);
  return { d, cx, cy };
}

function applyAngularGap(t0, t1) {
  const span = t1 - t0;
  const pad = Math.min(ANGULAR_PAD_T, span * 0.14);
  const ta = t0 + pad;
  const tb = t1 - pad;
  if (tb <= ta + 1e-9) {
    const mid = (t0 + t1) / 2;
    return { t0: mid - 1e-6, t1: mid + 1e-6 };
  }
  return { t0: ta, t1: tb };
}

/**
 * CW from t=0 on top edge (west→east): NW corner → North → NE → East → SE → South → SW → West.
 * West inner: 332…337 bottom→top on left; South inner along bottom east→west: 328…319.
 */
const INNER_SPECS_ORDERED = [
  { id: '338', faceLabel: '338', w: 0.92 },
  ...[301, 302, 303, 304, 305, 306, 307, 308, 309].map((n) => ({ id: String(n), faceLabel: String(n), w: 1.05 })),
  { id: '310', faceLabel: '310', w: 0.72 },
  { id: '311', faceLabel: '311', w: 0.72 },
  ...[312, 313, 314, 315, 316, 317].map((n) => ({ id: String(n), faceLabel: String(n), w: 1.18 })),
  { id: '318', faceLabel: '318', w: 0.92 },
  ...[328, 327, 326, 325, 324, 323, 322, 321, 320, 319].map((n) => ({ id: String(n), faceLabel: String(n), w: 1.05 })),
  { id: '329', faceLabel: '329', w: 0.62 },
  { id: '330', faceLabel: '330', w: 0.62 },
  { id: '331', faceLabel: '331', w: 0.62 },
  ...[337, 336, 335, 334, 333, 332].map((n) => ({ id: String(n), faceLabel: String(n), w: 1.22 })),
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

const INNER_RANGES = normalizeRanges(INNER_SPECS_ORDERED);

const INNER_WEDGES = INNER_RANGES.map((r) => {
  const { t0, t1 } = applyAngularGap(r.t0, r.t1);
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
  const raw0 = t0 + dt * i;
  const raw1 = t0 + dt * (i + 1);
  return applyAngularGap(raw0, raw1);
}

const OUTER_WEDGES = [];

for (let i = 0; i < 12; i += 1) {
  const id = String(420 + i);
  const { t0, t1 } = splitSpan(westInnerSpan.t0, westInnerSpan.t1, 12, i);
  const { d, cx, cy } = ringSlice(t0, t1, wOuterFront, hOuterFront, rOuterFront, wo, ho, ro);
  OUTER_WEDGES.push({ id, faceLabel: id, d, cx, cy, tier: 'upper' });
}

const northMid = (northInnerSpan.t0 + northInnerSpan.t1) / 2;
const northOuterHalf = (northInnerSpan.t1 - northInnerSpan.t0) * 0.36;
const northOuterT0 = northMid - northOuterHalf / 2;
const northOuterT1 = northMid + northOuterHalf / 2;
for (let i = 0; i < 3; i += 1) {
  const id = String(404 + i);
  const { t0, t1 } = splitSpan(northOuterT0, northOuterT1, 3, i);
  const { d, cx, cy } = ringSlice(t0, t1, wOuterFront, hOuterFront, rOuterFront, wo, ho, ro);
  OUTER_WEDGES.push({ id, faceLabel: id, d, cx, cy, tier: 'upper' });
}

for (let i = 0; i < 9; i += 1) {
  const id = String(221 + i);
  const { t0, t1 } = splitSpan(southInnerSpan.t0, southInnerSpan.t1, 9, i);
  const { d, cx, cy } = ringSlice(t0, t1, wOuterFront, hOuterFront, rOuterFront, wo, ho, ro);
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

/** Stadium shell: capsule (r = ho/2). Slight padding so stroke sits inside view. */
const BOWL_PAD = 10;
export const BOWL_OUTER_D = roundedRectPathD(CX, CY, wo + BOWL_PAD * 2, ho + BOWL_PAD * 2, ro + BOWL_PAD);
