/**
 * Bloomfield — Viagogo 3-tier bowl on a squircle (rounded rect: straight N/S/E/W, curved corners only).
 * Tier 1 (~200s): thin inner ring (straights only; corners = negative space).
 * Tier 2 (~300s): full loop — uniform equal arc-length cells along inner/outer squircle track.
 * Tier 3 (~400s): N+S only (equal splits on flats).
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

export const CX = 500;
export const CY = 320;

export const PITCH_W = Math.round(300 * 0.83);
export const PITCH_H = Math.round(168 * 0.83);
export const PITCH_RX = 5;
export const PITCH_RY = 5;

const MOAT = 20;
const D_T1 = 12;
const G_T12 = 2;
const D_T2 = 55;
const G_T23 = 2;
const D_T3 = 58;

const CELL_IN = 0.45;

const wi = PITCH_W + 2 * MOAT;
const hi = PITCH_H + 2 * MOAT;
const ri = Math.min(34, Math.min(wi, hi) * 0.11 + 18);

const xL = CX - wi / 2;
const xR = CX + wi / 2;
const yT = CY - hi / 2;
const yB = CY + hi / 2;

/** Tier 1 outer */
const w1 = wi + 2 * D_T1;
const h1 = hi + 2 * D_T1;
const r1 = ri + D_T1;
const xL1 = CX - w1 / 2;
const xR1 = CX + w1 / 2;
const yT1 = CY - h1 / 2;
const yB1 = CY + h1 / 2;

/** Tier 2 inner / outer (concentric squircles for uniform ring cells) */
const w2i = wi + 2 * (D_T1 + G_T12);
const h2i = hi + 2 * (D_T1 + G_T12);
const r2i = ri + D_T1 + G_T12;
const w2o = w2i + 2 * D_T2;
const h2o = h2i + 2 * D_T2;
const r2o = r2i + D_T2;

/** Tier 3 inner edge */
const w3i = w2o + 2 * G_T23;
const h3i = h2o + 2 * G_T23;
const r3i = r2o + G_T23;
const xL3i = CX - w3i / 2;
const xR3i = CX + w3i / 2;
const yT3i = CY - h3i / 2;
const yB3i = CY + h3i / 2;

/** Tier 3 outer */
const w3o = w3i + 2 * D_T3;
const h3o = h3i + 2 * D_T3;
const r3o = r3i + D_T3;

const yT3o = CY - h3o / 2;
const yB3o = CY + h3o / 2;

const topFlat1 = w1 - 2 * r1;
const botFlat1 = topFlat1;
const sideFlat1 = h1 - 2 * r1;

const topFlat3i = w3i - 2 * r3i;
const botFlat3i = topFlat3i;

function fmt(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return 0;
  return Number(v.toFixed(4));
}

export function roundedRectPathD(cx, cy, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  const hw = w / 2;
  const hh = h / 2;
  const xl = cx - hw;
  const xr = cx + hw;
  const yt = cy - hh;
  const yb = cy + hh;
  return [
    `M ${fmt(xl + rr)} ${fmt(yt)}`,
    `H ${fmt(xr - rr)}`,
    `A ${fmt(rr)} ${fmt(rr)} 0 0 1 ${fmt(xr)} ${fmt(yt + rr)}`,
    `V ${fmt(yb - rr)}`,
    `A ${fmt(rr)} ${fmt(rr)} 0 0 1 ${fmt(xr - rr)} ${fmt(yb)}`,
    `H ${fmt(xl + rr)}`,
    `A ${fmt(rr)} ${fmt(rr)} 0 0 1 ${fmt(xl)} ${fmt(yb - rr)}`,
    `V ${fmt(yt + rr)}`,
    `A ${fmt(rr)} ${fmt(rr)} 0 0 1 ${fmt(xl + rr)} ${fmt(yt)}`,
    'Z',
  ].join(' ');
}

/**
 * Point on rounded-rect perimeter at arc-length fraction frac ∈ [0,1).
 * Start: west end of top edge (after NW corner), direction: clockwise.
 */
function pointOnRoundedRectPerimeter(cx, cy, w, h, r, frac) {
  const rr = Math.min(r, w / 2, h / 2);
  const hw = w / 2;
  const hh = h / 2;
  const xl = cx - hw;
  const xr = cx + hw;
  const yt = cy - hh;
  const yb = cy + hh;
  const Ltop = w - 2 * rr;
  const Lright = h - 2 * rr;
  const Lbot = w - 2 * rr;
  const Lleft = h - 2 * rr;
  const Lc = (Math.PI / 2) * rr;
  const L = Ltop + Lright + Lbot + Lleft + 4 * Lc;
  let s = (frac % 1 + 1) % 1 * L;
  if (s >= L) s = 0;

  let d = s;

  if (d < Ltop) {
    const t = d / Ltop;
    return { x: xl + rr + t * (xr - xl - 2 * rr), y: yt };
  }
  d -= Ltop;

  if (d < Lc) {
    const t = d / Lc;
    const a = -Math.PI / 2 + t * (Math.PI / 2);
    return { x: xr - rr + rr * Math.cos(a), y: yt + rr + rr * Math.sin(a) };
  }
  d -= Lc;

  if (d < Lright) {
    const t = d / Lright;
    return { x: xr, y: yt + rr + t * (yb - yt - 2 * rr) };
  }
  d -= Lright;

  if (d < Lc) {
    const t = d / Lc;
    const a = 0 + t * (Math.PI / 2);
    return { x: xr - rr + rr * Math.cos(a), y: yb - rr + rr * Math.sin(a) };
  }
  d -= Lc;

  if (d < Lbot) {
    const t = d / Lbot;
    return { x: xr - rr - t * (xr - xl - 2 * rr), y: yb };
  }
  d -= Lbot;

  if (d < Lc) {
    const t = d / Lc;
    const a = Math.PI / 2 + t * (Math.PI / 2);
    return { x: xl + rr + rr * Math.cos(a), y: yb - rr + rr * Math.sin(a) };
  }
  d -= Lc;

  if (d < Lleft) {
    const t = d / Lleft;
    return { x: xl, y: yb - rr - t * (yb - yt - 2 * rr) };
  }
  d -= Lleft;

  {
    const t = d / Lc;
    const a = Math.PI + t * (Math.PI / 2);
    return { x: xl + rr + rr * Math.cos(a), y: yt + rr + rr * Math.sin(a) };
  }
}

function polygonCentroid(pts) {
  let a = 0;
  let cx = 0;
  let cy = 0;
  const n = pts.length;
  for (let i = 0; i < n; i += 1) {
    const j = (i + 1) % n;
    const cross = pts[i].x * pts[j].y - pts[j].x * pts[i].y;
    a += cross;
    cx += (pts[i].x + pts[j].x) * cross;
    cy += (pts[i].y + pts[j].y) * cross;
  }
  a *= 0.5;
  if (Math.abs(a) < 1e-10) {
    const sx = pts.reduce((s, p) => s + p.x, 0);
    const sy = pts.reduce((s, p) => s + p.y, 0);
    return { cx: sx / n, cy: sy / n };
  }
  return { cx: cx / (6 * a), cy: cy / (6 * a) };
}

/** Inset quad vertices along inward radial from centroid (white grid gap). */
function insetQuadTowardCentroid(p0, p1, p2, p3) {
  const c = polygonCentroid([p0, p1, p2, p3]);
  const shrink = (p) => {
    const dx = p.x - c.cx;
    const dy = p.y - c.cy;
    const len = Math.hypot(dx, dy) || 1;
    return { x: p.x - (dx / len) * CELL_IN, y: p.y - (dy / len) * CELL_IN };
  };
  return [shrink(p0), shrink(p1), shrink(p2), shrink(p3)];
}

/** Ring slice between inner and outer squircle; same arc-length fraction on both tracks. */
function ringQuadCell(cx, cy, wOut, hOut, rOut, wIn, hIn, rIn, f0, f1) {
  const p0o = pointOnRoundedRectPerimeter(cx, cy, wOut, hOut, rOut, f0);
  const p1o = pointOnRoundedRectPerimeter(cx, cy, wOut, hOut, rOut, f1);
  const p1i = pointOnRoundedRectPerimeter(cx, cy, wIn, hIn, rIn, f1);
  const p0i = pointOnRoundedRectPerimeter(cx, cy, wIn, hIn, rIn, f0);
  const [q0, q1, q2, q3] = insetQuadTowardCentroid(p0o, p1o, p1i, p0i);
  const d = `M ${fmt(q0.x)} ${fmt(q0.y)} L ${fmt(q1.x)} ${fmt(q1.y)} L ${fmt(q2.x)} ${fmt(q2.y)} L ${fmt(q3.x)} ${fmt(q3.y)} Z`;
  const { cx: ccx, cy: ccy } = polygonCentroid([q0, q1, q2, q3]);
  return { d, cx: ccx, cy: ccy };
}

/** Axis-aligned band slice */
function rectCell(x0, y0, x1, y1) {
  const xa = Math.min(x0, x1) + CELL_IN;
  const xb = Math.max(x0, x1) - CELL_IN;
  const ya = Math.min(y0, y1) + CELL_IN;
  const yb = Math.max(y0, y1) - CELL_IN;
  if (xb <= xa || yb <= ya) return null;
  const d = `M ${fmt(xa)} ${fmt(ya)} L ${fmt(xb)} ${fmt(ya)} L ${fmt(xb)} ${fmt(yb)} L ${fmt(xa)} ${fmt(yb)} Z`;
  return { d, cx: (xa + xb) / 2, cy: (ya + yb) / 2 };
}

function push(list, id, faceLabel, tier, w) {
  if (!w || typeof w.d !== 'string' || !w.d) return;
  if (!Number.isFinite(w.cx) || !Number.isFinite(w.cy)) return;
  list.push({ id, faceLabel, d: w.d, cx: w.cx, cy: w.cy, tier });
}

const TIER_1 = [];
const TIER_2 = [];
const TIER_3 = [];

/* --- TIER 1 straights only --- */

for (let i = 0; i < 9; i += 1) {
  const xa = xL1 + r1 + (i / 9) * topFlat1;
  const xb = xL1 + r1 + ((i + 1) / 9) * topFlat1;
  push(TIER_1, String(201 + i), String(201 + i), 't1', rectCell(xa, yT1, xb, yT));
}

/** South T1: screen L→R reads 229 … 221 (continues from east, right-to-left along stand). */
for (let i = 0; i < 9; i += 1) {
  const xa = xL1 + r1 + (i / 9) * botFlat1;
  const xb = xL1 + r1 + ((i + 1) / 9) * botFlat1;
  push(TIER_1, String(229 - i), String(229 - i), 't1', rectCell(xa, yB, xb, yB1));
}

for (let i = 0; i < 3; i += 1) {
  const ya = yT1 + r1 + (i / 3) * sideFlat1;
  const yb = yT1 + r1 + ((i + 1) / 3) * sideFlat1;
  push(TIER_1, String(236 - i), String(236 - i), 't1', rectCell(xL1, ya, xL, yb));
}

for (let i = 0; i < 3; i += 1) {
  const ya = yT1 + r1 + (i / 3) * sideFlat1;
  const yb = yT1 + r1 + ((i + 1) / 3) * sideFlat1;
  push(TIER_1, String(214 + i), String(214 + i), 't1', rectCell(xR, ya, xR1, yb));
}

/* --- TIER 2: 38 equal arc-length cells around full squircle ring --- */

const T2_COUNT = 38;
const T2_IDS = [
  ...[301, 302, 303, 304, 305, 306, 307, 308, 309].map(String),
  '310',
  '311',
  ...[312, 313, 314, 315, 316, 317].map(String),
  '318',
  ...[328, 327, 326, 325, 324, 323, 322, 321, 320, 319].map(String),
  '329',
  '330',
  '331',
  ...[332, 333, 334, 335, 336, 337].map(String),
  '338',
];

for (let i = 0; i < T2_COUNT; i += 1) {
  const f0 = i / T2_COUNT;
  const f1 = (i + 1) / T2_COUNT;
  push(
    TIER_2,
    T2_IDS[i],
    T2_IDS[i],
    't2',
    ringQuadCell(CX, CY, w2o, h2o, r2o, w2i, h2i, r2i, f0, f1)
  );
}

/* --- TIER 3 north + south (equal splits on flats) --- */

for (let i = 0; i < 3; i += 1) {
  const xa = xL3i + r3i + (i / 3) * topFlat3i;
  const xb = xL3i + r3i + ((i + 1) / 3) * topFlat3i;
  push(TIER_3, String(404 + i), String(404 + i), 't3', rectCell(xa, yT3o, xb, yT3i));
}

/** South T3: screen L→R reads 431 … 419 */
for (let i = 0; i < 13; i += 1) {
  const xa = xL3i + r3i + (i / 13) * botFlat3i;
  const xb = xL3i + r3i + ((i + 1) / 13) * botFlat3i;
  push(TIER_3, String(431 - i), String(431 - i), 't3', rectCell(xa, yB3i, xb, yB3o));
}

const DRAW_ORDER = [
  ...[201, 202, 203, 204, 205, 206, 207, 208, 209].map(String),
  ...[229, 228, 227, 226, 225, 224, 223, 222, 221].map(String),
  ...[236, 235, 234].map(String),
  ...[214, 215, 216].map(String),
  ...[301, 302, 303, 304, 305, 306, 307, 308, 309].map(String),
  ...[328, 327, 326, 325, 324, 323, 322, 321, 320, 319].map(String),
  ...[337, 336, 335, 334, 333, 332].map(String),
  ...[312, 313, 314, 315, 316, 317].map(String),
  '338',
  '310',
  '311',
  '318',
  '329',
  '330',
  '331',
  ...[404, 405, 406].map(String),
  ...[431, 430, 429, 428, 427, 426, 425, 424, 423, 422, 421, 420, 419].map(String),
];

const byId = Object.fromEntries([...TIER_1, ...TIER_2, ...TIER_3].map((s) => [s.id, s]));
function isValidWedge(s) {
  return (
    s &&
    typeof s.id === 'string' &&
    typeof s.d === 'string' &&
    s.d.length > 0 &&
    !s.d.includes('NaN') &&
    Number.isFinite(s.cx) &&
    Number.isFinite(s.cy)
  );
}
export const SECTION_WEDGES = DRAW_ORDER.map((id) => byId[id]).filter(isValidWedge);

const ALL_BLOCK_IDS = new Set(SECTION_WEDGES.map((s) => s.id));

export const LOWER_WEDGE_IDS = SECTION_WEDGES.filter((s) => s.tier === 't1' || s.tier === 't2').map((s) => s.id);
export const UPPER_WEDGE_IDS = SECTION_WEDGES.filter((s) => s.tier === 't3').map((s) => s.id);
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

export const BOWL_OUTER_D = roundedRectPathD(CX, CY, w3o, h3o, r3o);
