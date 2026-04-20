/**
 * Bloomfield — Viagogo 3-tier bowl on a squircle (rounded rect: straight N/S/E/W, curved corners only).
 * Tier 1 (~200s): thin inner ring. Tier 2 (~300s): main bowl full loop. Tier 3 (~400s): N+S only.
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
/** Viagogo-ish radial weights (~112px stand + gaps): thin 200s, massive 300s, stout 400s N/S. */
const D_T1 = 12;
const G_T12 = 2;
const D_T2 = 55;
const G_T23 = 8;
const D_T3 = 35;

const CELL_IN = 0.45;
/** Tier 2 corner wedges: full annular depth to r2o (standalone sectors; grid gap from CELL_IN only). */
const T2_CORNER_OUTER_FRAC = 1;

const wi = PITCH_W + 2 * MOAT;
const hi = PITCH_H + 2 * MOAT;
/** Slightly tighter fillet than before — straights read longer, corners less “puffy”. */
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

/** Tier 2 inner (after channel from T1) */
const w2i = wi + 2 * (D_T1 + G_T12);
const h2i = hi + 2 * (D_T1 + G_T12);
const r2i = ri + D_T1 + G_T12;
const xL2i = CX - w2i / 2;
const xR2i = CX + w2i / 2;
const yT2i = CY - h2i / 2;
const yB2i = CY + h2i / 2;

/** Tier 2 outer */
const w2o = w2i + 2 * D_T2;
const h2o = h2i + 2 * D_T2;
const r2o = r2i + D_T2;
const xL2o = CX - w2o / 2;
const xR2o = CX + w2o / 2;
const yT2o = CY - h2o / 2;
const yB2o = CY + h2o / 2;

/** Tier 3 inner edge (full ring — channel after T2) */
const w3i = w2o + 2 * G_T23;
const h3i = h2o + 2 * G_T23;
const r3i = r2o + G_T23;
const xL3i = CX - w3i / 2;
const xR3i = CX + w3i / 2;
const yT3i = CY - h3i / 2;
const yB3i = CY + h3i / 2;

/** Tier 3 outer (squircle shell) */
const w3o = w3i + 2 * D_T3;
const h3o = h3i + 2 * D_T3;
const r3o = r3i + D_T3;

/** Tier 3 outer face (north/south 400s bands) */
const yT3o = CY - h3o / 2;
const yB3o = CY + h3o / 2;

const topFlat1 = w1 - 2 * r1;
const botFlat1 = topFlat1;
const sideFlat1 = h1 - 2 * r1;

const topFlat2i = w2i - 2 * r2i;
const botFlat2i = topFlat2i;
const sideFlat2i = h2i - 2 * r2i;

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

/** Axis-aligned band slice; cx/cy = center of inset rect (matches 8px labels, any tier depth). */
function rectCell(x0, y0, x1, y1) {
  const xa = Math.min(x0, x1) + CELL_IN;
  const xb = Math.max(x0, x1) - CELL_IN;
  const ya = Math.min(y0, y1) + CELL_IN;
  const yb = Math.max(y0, y1) - CELL_IN;
  if (xb <= xa || yb <= ya) return null;
  const d = `M ${fmt(xa)} ${fmt(ya)} L ${fmt(xb)} ${fmt(ya)} L ${fmt(xb)} ${fmt(yb)} L ${fmt(xa)} ${fmt(yb)} Z`;
  return { d, cx: (xa + xb) / 2, cy: (ya + yb) / 2 };
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

function annularSector(cx0, cy0, rIn, rOut, a0, a1, steps = 14) {
  if (!Number.isFinite(rIn) || !Number.isFinite(rOut) || rOut <= rIn + 1e-3) return null;
  const pts = [];
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    const a = a0 + t * (a1 - a0);
    pts.push({ x: cx0 + rOut * Math.cos(a), y: cy0 + rOut * Math.sin(a) });
  }
  for (let i = steps; i >= 0; i -= 1) {
    const t = i / steps;
    const a = a0 + t * (a1 - a0);
    pts.push({ x: cx0 + rIn * Math.cos(a), y: cy0 + rIn * Math.sin(a) });
  }
  let d = '';
  for (let i = 0; i < pts.length; i += 1) {
    const p = pts[i];
    d += i === 0 ? `M ${fmt(p.x)} ${fmt(p.y)}` : ` L ${fmt(p.x)} ${fmt(p.y)}`;
  }
  d += ' Z';
  const { cx, cy } = polygonCentroid(pts);
  return { d, cx, cy };
}

function push(list, id, faceLabel, tier, w) {
  if (!w || typeof w.d !== 'string' || !w.d) return;
  if (!Number.isFinite(w.cx) || !Number.isFinite(w.cy)) return;
  list.push({ id, faceLabel, d: w.d, cx: w.cx, cy: w.cy, tier });
}

const TIER_1 = [];
const TIER_2 = [];
const TIER_3 = [];

/* --- TIER 1 straights only (no 200s in corners — white negative space) --- */

for (let i = 0; i < 9; i += 1) {
  const xa = xL1 + r1 + (i / 9) * topFlat1;
  const xb = xL1 + r1 + ((i + 1) / 9) * topFlat1;
  push(TIER_1, String(201 + i), String(201 + i), 't1', rectCell(xa, yT1, xb, yT));
}

for (let i = 0; i < 9; i += 1) {
  const xa = xR1 - r1 - (i / 9) * botFlat1;
  const xb = xR1 - r1 - ((i + 1) / 9) * botFlat1;
  push(TIER_1, String(229 - i), String(229 - i), 't1', rectCell(xb, yB, xa, yB1));
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

/* --- TIER 2 full bowl --- */

for (let i = 0; i < 9; i += 1) {
  const xa = xL2i + r2i + (i / 9) * topFlat2i;
  const xb = xL2i + r2i + ((i + 1) / 9) * topFlat2i;
  push(TIER_2, String(301 + i), String(301 + i), 't2', rectCell(xa, yT2o, xb, yT2i));
}

for (let i = 0; i < 10; i += 1) {
  const xa = xR2i - r2i - (i / 10) * botFlat2i;
  const xb = xR2i - r2i - ((i + 1) / 10) * botFlat2i;
  push(TIER_2, String(328 - i), String(328 - i), 't2', rectCell(xb, yB2i, xa, yB2o));
}

for (let i = 0; i < 6; i += 1) {
  const ya = yT2i + r2i + (i / 6) * sideFlat2i;
  const yb = yT2i + r2i + ((i + 1) / 6) * sideFlat2i;
  /** West reads top→bottom: 337 … 332 (i=0 is top). */
  push(TIER_2, String(337 - i), String(337 - i), 't2', rectCell(xL2o, ya, xL2i, yb));
}

for (let i = 0; i < 6; i += 1) {
  const ya = yT2i + r2i + (i / 6) * sideFlat2i;
  const yb = yT2i + r2i + ((i + 1) / 6) * sideFlat2i;
  push(TIER_2, String(312 + i), String(312 + i), 't2', rectCell(xR2i, ya, xR2o, yb));
}

const cn2 = {
  nw: { x: xL2i + r2i, y: yT2i + r2i },
  ne: { x: xR2i - r2i, y: yT2i + r2i },
  se: { x: xR2i - r2i, y: yB2i - r2i },
  sw: { x: xL2i + r2i, y: yB2i - r2i },
};

const rinC = r2i + CELL_IN;
const routC = r2i + (r2o - r2i) * T2_CORNER_OUTER_FRAC - CELL_IN;

push(TIER_2, '338', '338', 't2', annularSector(cn2.nw.x, cn2.nw.y, rinC, routC, -Math.PI / 2, -Math.PI));
push(
  TIER_2,
  '310',
  '310',
  't2',
  annularSector(cn2.ne.x, cn2.ne.y, rinC, routC, -Math.PI / 2, -Math.PI / 4, 8)
);
push(
  TIER_2,
  '311',
  '311',
  't2',
  annularSector(cn2.ne.x, cn2.ne.y, rinC, routC, -Math.PI / 4, 0, 8)
);
push(TIER_2, '318', '318', 't2', annularSector(cn2.se.x, cn2.se.y, rinC, routC, 0, Math.PI / 2));

const swA = Math.PI / 2;
const swB = Math.PI;
const swThird = (swB - swA) / 3;
push(
  TIER_2,
  '329',
  '329',
  't2',
  annularSector(cn2.sw.x, cn2.sw.y, rinC, routC, swA, swA + swThird, 6)
);
push(
  TIER_2,
  '330',
  '330',
  't2',
  annularSector(cn2.sw.x, cn2.sw.y, rinC, routC, swA + swThird, swA + 2 * swThird, 6)
);
push(
  TIER_2,
  '331',
  '331',
  't2',
  annularSector(cn2.sw.x, cn2.sw.y, rinC, routC, swA + 2 * swThird, swB, 6)
);

/* --- TIER 3 north + south only (uniform shell; cells on flats only) --- */

for (let i = 0; i < 3; i += 1) {
  const xa = xL3i + r3i + (i / 3) * topFlat3i;
  const xb = xL3i + r3i + ((i + 1) / 3) * topFlat3i;
  push(TIER_3, String(404 + i), String(404 + i), 't3', rectCell(xa, yT3o, xb, yT3i));
}

for (let i = 0; i < 13; i += 1) {
  const xa = xR3i - r3i - (i / 13) * botFlat3i;
  const xb = xR3i - r3i - ((i + 1) / 13) * botFlat3i;
  push(TIER_3, String(431 - i), String(431 - i), 't3', rectCell(xb, yB3i, xa, yB3o));
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
