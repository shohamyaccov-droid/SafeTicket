/**
 * Bloomfield schematic — rounded-rect bowl with lower + upper tier wedges.
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

export const CX = 500;
export const CY = 320;

/** Pitch ~17% smaller → more concourse between pitch and stands */
export const PITCH_W = Math.round(300 * 0.83);
export const PITCH_H = Math.round(168 * 0.83);
export const PITCH_RX = 5;
export const PITCH_RY = 5;

const GAP = 22;
/** Lower bowl depth + upper tier depth (total ring thickness ≈ prior single ring) */
const STAND_DEPTH_LOWER = 48;
const STAND_DEPTH_UPPER = 48;

const wi = PITCH_W + 2 * GAP;
const hi = PITCH_H + 2 * GAP;
const ri = Math.min(36, Math.min(wi, hi) * 0.11 + 24);

const wm = wi + 2 * STAND_DEPTH_LOWER;
const hm = hi + 2 * STAND_DEPTH_LOWER;
const rm = Math.min(ri + STAND_DEPTH_LOWER, wm / 2 - 8, hm / 2 - 8);

const wo = wm + 2 * STAND_DEPTH_UPPER;
const ho = hm + 2 * STAND_DEPTH_UPPER;
const ro = Math.min(rm + STAND_DEPTH_UPPER, wo / 2 - 6, ho / 2 - 6);

const WEDGE_COUNT = 36;

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

/** Lower tier ids (inner bowl): 301…336 */
export const LOWER_WEDGE_IDS = (() => {
  const ids = [];
  for (let i = 0; i < 10; i += 1) ids.push(String(301 + i));
  for (let i = 0; i < 8; i += 1) ids.push(String(311 + i));
  for (let i = 0; i < 10; i += 1) ids.push(String(319 + i));
  for (let i = 0; i < 8; i += 1) ids.push(String(329 + i));
  return ids;
})();

/** Upper tier ids (outer ring): 401…436 */
export const UPPER_WEDGE_IDS = (() => {
  const ids = [];
  for (let i = 0; i < 10; i += 1) ids.push(String(401 + i));
  for (let i = 0; i < 8; i += 1) ids.push(String(411 + i));
  for (let i = 0; i < 10; i += 1) ids.push(String(419 + i));
  for (let i = 0; i < 8; i += 1) ids.push(String(429 + i));
  return ids;
})();

/** @deprecated use LOWER_WEDGE_IDS */
export const WEDGE_IDS = LOWER_WEDGE_IDS;

function wedgeIndexFromSectionNumber(n) {
  return ((n % 100) + 35) % WEDGE_COUNT;
}

/**
 * Map ticket section number to a wedge id. Section numbers 400–499 → upper tier; else lower.
 */
export function blockIdFromSectionNumber(numStr) {
  if (!numStr || numStr === '—') return LOWER_WEDGE_IDS[0];
  const n = parseInt(String(numStr), 10);
  if (Number.isNaN(n)) return LOWER_WEDGE_IDS[0];
  const idx = wedgeIndexFromSectionNumber(n);
  if (n >= 400 && n < 500) {
    return UPPER_WEDGE_IDS[idx];
  }
  return LOWER_WEDGE_IDS[idx];
}

const LOWER_FACE_LABELS = [
  '118', '124', '129', '134', '138', '142', '148', '152', '156', '162',
  '215', '222', '229', '238', '245', '251', '258', '265',
  '301', '308', '315', '322', '329', '334', '338', '345', '352', '358',
  '401', '408', '415', '421', '426', '429', '433', '438',
];

const UPPER_FACE_LABELS = [
  '402', '406', '412', '418', '424', '428', '432', '436', '440', '444',
  '448', '452', '456', '460', '464', '468', '472', '476',
  '480', '484', '488', '492', '496', '500', '504', '508', '512', '516',
  '520', '524', '528', '532', '536', '540', '544', '548',
];

function quadPath(o1, o2, i2, i1) {
  return `M ${fmt(o1.x)} ${fmt(o1.y)} L ${fmt(o2.x)} ${fmt(o2.y)} L ${fmt(i2.x)} ${fmt(i2.y)} L ${fmt(i1.x)} ${fmt(i1.y)} Z`;
}

function buildTierWedge(ids, faceLabels, outerW, outerH, outerR, innerW, innerH, innerR) {
  return ids.map((id, i) => {
    const t1 = i / WEDGE_COUNT;
    const t2 = (i + 1) / WEDGE_COUNT;
    const o1 = pointOnPerimeter(t1, outerW, outerH, outerR, CX, CY);
    const o2 = pointOnPerimeter(t2, outerW, outerH, outerR, CX, CY);
    const i1 = pointOnPerimeter(t1, innerW, innerH, innerR, CX, CY);
    const i2 = pointOnPerimeter(t2, innerW, innerH, innerR, CX, CY);
    const d = quadPath(o1, o2, i2, i1);
    const tcx = (o1.x + o2.x + i1.x + i2.x) / 4;
    const tcy = (o1.y + o2.y + i1.y + i2.y) / 4;
    const faceLabel = faceLabels[i] ?? id;
    return { id, faceLabel, d, cx: tcx, cy: tcy, tier: outerW === wo ? 'upper' : 'lower' };
  });
}

const LOWER_WEDGES = buildTierWedge(
  LOWER_WEDGE_IDS,
  LOWER_FACE_LABELS,
  wm,
  hm,
  rm,
  wi,
  hi,
  ri
);

const UPPER_WEDGES = buildTierWedge(
  UPPER_WEDGE_IDS,
  UPPER_FACE_LABELS,
  wo,
  ho,
  ro,
  wm,
  hm,
  rm
);

/** All wedges: lower (inner bowl) first, then upper (outer ring) */
export const SECTION_WEDGES = [...LOWER_WEDGES, ...UPPER_WEDGES];

export const GAP_ROUNDRECT_D = roundedRectPathD(CX, CY, wi, hi, ri);

export const PITCH_X = CX - PITCH_W / 2;
export const PITCH_Y = CY - PITCH_H / 2;

export const BOWL_OUTER_D = roundedRectPathD(CX, CY, wo + 24, ho + 24, ro + 14);
