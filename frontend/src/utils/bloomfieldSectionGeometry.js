/**
 * Bloomfield schematic — Viagogo-style asymmetric sections on a rounded-rect bowl.
 * Inner tier: wi → inner-back rect (short of old wm). Outer tier: outer-front rect → wo (past inner-back).
 * Angular insets create true gaps between adjacent blocks; radial offset separates the tiers.
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
const STAND_DEPTH_UPPER = 48;

/** Pull inner tier outer edge inward (px in viewBox) — leaves channel before outer tier. */
const RADIAL_INNER_BACK_TRIM = 5;
/** Outer tier inner edge sits this far beyond nominal lower-bowl depth (px) — clear radial gap vs inner-back. */
const RADIAL_OUTER_FRONT_EXTRA = 11;

/**
 * Normalized perimeter padding per wedge side (t ∈ [0,1)). ~0.00055 → ~0.11% of loop each side.
 * Caps relative to wedge span so tiny corners do not invert.
 */
const ANGULAR_PAD_T = 0.00052;

const wi = PITCH_W + 2 * GAP;
const hi = PITCH_H + 2 * GAP;
const ri = Math.min(36, Math.min(wi, hi) * 0.11 + 24);

const wm = wi + 2 * STAND_DEPTH_LOWER;
const hm = hi + 2 * STAND_DEPTH_LOWER;
const rm = Math.min(ri + STAND_DEPTH_LOWER, wm / 2 - 8, hm / 2 - 8);

const innerBackDepth = STAND_DEPTH_LOWER - RADIAL_INNER_BACK_TRIM;
const wInnerBack = wi + 2 * innerBackDepth;
const hInnerBack = hi + 2 * innerBackDepth;
const rInnerBack = Math.min(ri + innerBackDepth, wInnerBack / 2 - 8, hInnerBack / 2 - 8);

const outerFrontDepth = STAND_DEPTH_LOWER + RADIAL_OUTER_FRONT_EXTRA;
const wOuterFront = wi + 2 * outerFrontDepth;
const hOuterFront = hi + 2 * outerFrontDepth;
const rOuterFront = Math.min(ri + outerFrontDepth, wOuterFront / 2 - 8, hOuterFront / 2 - 8);

const wo = wm + 2 * STAND_DEPTH_UPPER;
const ho = hm + 2 * STAND_DEPTH_UPPER;
const ro = Math.min(rm + STAND_DEPTH_UPPER, wo / 2 - 6, ho / 2 - 6);

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

/** Shrink [t0,t1] from both ends so adjacent wedges leave visible angular channel. */
function applyAngularGap(t0, t1) {
  const span = t1 - t0;
  const pad = Math.min(ANGULAR_PAD_T, span * 0.12);
  const ta = t0 + pad;
  const tb = t1 - pad;
  if (tb <= ta + 1e-8) {
    const mid = (t0 + t1) / 2;
    return { t0: mid - 1e-6, t1: mid + 1e-6 };
  }
  return { t0: ta, t1: tb };
}

/**
 * Order matches pointOnPerimeter: t=0 at west end of north (top) edge, then CW:
 * north inner → NE → east → SE → south → SW → west → NW.
 * Weights: west/east inner (touchlines) wider than north/south inner.
 */
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

/** West inner 332–337: shared span for outer 420–431 */
const westInnerSpan = rangeForIds(['332', '333', '334', '335', '336', '337']);
/** South inner 319–328 → south outer 221–229 */
const southInnerSpan = rangeForIds(['319', '320', '321', '322', '323', '324', '325', '326', '327', '328']);
/** North inner 301–309 → center strip for 404–406 */
const northInnerSpan = rangeForIds(['301', '302', '303', '304', '305', '306', '307', '308', '309']);

function splitSpan(t0, t1, n, i) {
  const dt = (t1 - t0) / n;
  const raw0 = t0 + dt * i;
  const raw1 = t0 + dt * (i + 1);
  return applyAngularGap(raw0, raw1);
}

const OUTER_WEDGES = [];

/** West outer 420–431 (12), north → south */
for (let i = 0; i < 12; i += 1) {
  const id = String(420 + i);
  const { t0, t1 } = splitSpan(westInnerSpan.t0, westInnerSpan.t1, 12, i);
  const { d, cx, cy } = ringSlice(t0, t1, wOuterFront, hOuterFront, rOuterFront, wo, ho, ro);
  OUTER_WEDGES.push({ id, faceLabel: id, d, cx, cy, tier: 'upper' });
}

/** North outer center only: 404, 405, 406 */
const northMid = (northInnerSpan.t0 + northInnerSpan.t1) / 2;
const northHalfW = (northInnerSpan.t1 - northInnerSpan.t0) * 0.34;
const northOuterT0 = northMid - northHalfW / 2;
const northOuterT1 = northMid + northHalfW / 2;
for (let i = 0; i < 3; i += 1) {
  const id = String(404 + i);
  const { t0, t1 } = splitSpan(northOuterT0, northOuterT1, 3, i);
  const { d, cx, cy } = ringSlice(t0, t1, wOuterFront, hOuterFront, rOuterFront, wo, ho, ro);
  OUTER_WEDGES.push({ id, faceLabel: id, d, cx, cy, tier: 'upper' });
}

/** South outer 221–229 (9), east → west along bottom */
for (let i = 0; i < 9; i += 1) {
  const id = String(221 + i);
  const { t0, t1 } = splitSpan(southInnerSpan.t0, southInnerSpan.t1, 9, i);
  const { d, cx, cy } = ringSlice(t0, t1, wOuterFront, hOuterFront, rOuterFront, wo, ho, ro);
  OUTER_WEDGES.push({ id, faceLabel: id, d, cx, cy, tier: 'upper' });
}

/** Inner first (draw order), then outer; labels render on top in map component */
export const SECTION_WEDGES = [...INNER_WEDGES, ...OUTER_WEDGES];

const ALL_BLOCK_IDS = new Set(SECTION_WEDGES.map((s) => s.id));

/** @deprecated */
export const LOWER_WEDGE_IDS = INNER_WEDGES.map((w) => w.id);
/** @deprecated */
export const UPPER_WEDGE_IDS = OUTER_WEDGES.map((w) => w.id);
/** @deprecated */
export const WEDGE_IDS = LOWER_WEDGE_IDS;

/**
 * Map API section number to schematic block id (exact Viagogo ids only).
 */
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

export const BOWL_OUTER_D = roundedRectPathD(CX, CY, wo + 24, ho + 24, ro + 14);
