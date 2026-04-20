/**
 * Bloomfield — Viagogo 3-tier bowl on a squircle (rounded rect: straight N/S/E/W, curved corners only).
 * Tier 1 (~200s): thin inner ring. Tier 2 (~300s): main bowl full loop. Tier 3 (~400s): N+S only.
 * Straights use equal subdivision; corners are standalone annular sectors (no path merging).
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

export const CX = 500;
export const CY = 320;

/** Base pitch; may be reduced slightly if outer bowl would exceed vertical fit budget. */
let pitchW = Math.round(300 * 0.83);
let pitchH = Math.round(168 * 0.83);
export const PITCH_RX = 5;
export const PITCH_RY = 5;

const MOAT_DEFAULT = 20;
/** Thin 200s, deep 300s bowl, deep 400s N/S. */
const D_T1 = 12;
const G_T12 = 2;
const D_T2 = 80;
const G_T23 = 8;
const D_T3 = 65;

const CELL_IN = 0.45;
const T2_CORNER_OUTER_FRAC = 1;

/** Total vertical stack beyond pitch+moat band (symmetric east/west). */
const INNER_DIM =
  2 * (D_T1 + G_T12) + 2 * D_T2 + 2 * G_T23 + 2 * D_T3;
/** Leave ~10px margin inside VIEW_H 640; shrink moat/pitch only if depths push past this. */
const OUTER_H_CEIL = 630;

let MOAT = MOAT_DEFAULT;
const maxBandH = OUTER_H_CEIL - INNER_DIM;
if (pitchH + 2 * MOAT > maxBandH) {
  MOAT = Math.max(6, Math.floor((maxBandH - pitchH) / 2));
}
if (pitchH + 2 * MOAT > maxBandH) {
  pitchH = Math.max(100, maxBandH - 2 * MOAT);
  pitchW = Math.round(pitchH * (300 / 168));
}

export const PITCH_W = pitchW;
export const PITCH_H = pitchH;

const wi = PITCH_W + 2 * MOAT;
const hi = PITCH_H + 2 * MOAT;
/** Slightly tighter fillet — straights read longer, corners less “puffy”. */
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

/** `segments` equal slices → `segments + 1` boundary coordinates along [start, start+span]. */
function equalBreaks(start, span, segments) {
  if (!Number.isFinite(segments) || segments <= 0) return [start, start + span];
  return Array.from({ length: segments + 1 }, (_, k) => start + (k / segments) * span);
}

/** Intersect [a,b] with [lo,hi] on x (order-agnostic); null if empty. */
function clipSpan1D(a, b, lo, hi) {
  const t0 = Math.min(a, b);
  const t1 = Math.max(a, b);
  const xa = Math.max(lo, t0);
  const xb = Math.min(hi, t1);
  if (xb <= xa + 1e-9) return null;
  return { xa, xb };
}

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
    const ang = a0 + t * (a1 - a0);
    pts.push({ x: cx0 + rOut * Math.cos(ang), y: cy0 + rOut * Math.sin(ang) });
  }
  for (let i = steps; i >= 0; i -= 1) {
    const t = i / steps;
    const ang = a0 + t * (a1 - a0);
    pts.push({ x: cx0 + rIn * Math.cos(ang), y: cy0 + rIn * Math.sin(ang) });
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

/** Tier-2 master breaks: equal spacing (aligned T1 north clips + visual rhythm). */
const xNorthT2 = equalBreaks(xL2i + r2i, topFlat2i, 9);
const xSouthT2 = equalBreaks(xL2i + r2i, botFlat2i, 10);
const xSouthT2Rev = xSouthT2.slice().reverse();
const yWestT2 = equalBreaks(yT2i + r2i, sideFlat2i, 6);
const yWestT2Rev = yWestT2.slice().reverse();

/* --- TIER 1 straights only (no 200s in corners — white negative space) --- */

const xN1Lo = xL1 + r1;
const xN1Hi = xR1 - r1;
for (let i = 0; i < 9; i += 1) {
  const clip = clipSpan1D(xNorthT2[i], xNorthT2[i + 1], xN1Lo, xN1Hi);
  if (clip) push(TIER_1, String(201 + i), String(201 + i), 't1', rectCell(clip.xa, yT1, clip.xb, yT));
}

const xS1Lo = xL1 + r1;
const xS1Hi = xR1 - r1;
for (let i = 0; i < 8; i += 1) {
  const clip = clipSpan1D(xSouthT2Rev[10 - i], xSouthT2Rev[9 - i], xS1Lo, xS1Hi);
  if (clip) push(TIER_1, String(221 + i), String(221 + i), 't1', rectCell(clip.xa, yB, clip.xb, yB1));
}
{
  const clip = clipSpan1D(xSouthT2Rev[0], xSouthT2Rev[2], xS1Lo, xS1Hi);
  if (clip) push(TIER_1, '229', '229', 't1', rectCell(clip.xa, yB, clip.xb, yB1));
}

const yW1Lo = yT1 + r1;
const yW1Hi = yB1 - r1;
for (let p = 0; p < 3; p += 1) {
  const yClip = clipSpan1D(yWestT2[p * 2], yWestT2[p * 2 + 2], yW1Lo, yW1Hi);
  if (yClip) {
    push(TIER_1, String(236 - p), String(236 - p), 't1', rectCell(xL1, yClip.xa, xL, yClip.xb));
  }
}

for (let p = 0; p < 3; p += 1) {
  const yClip = clipSpan1D(yWestT2[p * 2], yWestT2[p * 2 + 2], yW1Lo, yW1Hi);
  if (yClip) {
    push(TIER_1, String(214 + p), String(214 + p), 't1', rectCell(xR, yClip.xa, xR1, yClip.xb));
  }
}

/* --- TIER 2 full bowl — straights = rectCell only; corners = full 90° quarters (equal arc share) --- */

for (let i = 0; i < 9; i += 1) {
  push(
    TIER_2,
    String(301 + i),
    String(301 + i),
    't2',
    rectCell(xNorthT2[i], yT2o, xNorthT2[i + 1], yT2i)
  );
}

for (let i = 0; i < 10; i += 1) {
  const x0 = xSouthT2Rev[i + 1];
  const x1 = xSouthT2Rev[i];
  const sid = String(319 + (9 - i));
  push(TIER_2, sid, sid, 't2', rectCell(x0, yB2i, x1, yB2o));
}

for (let i = 0; i < 6; i += 1) {
  const y0 = yWestT2Rev[i + 1];
  const y1 = yWestT2Rev[i];
  const sid = String(332 + i);
  push(TIER_2, sid, sid, 't2', rectCell(xL2o, y0, xL2i, y1));
}

for (let i = 0; i < 6; i += 1) {
  push(
    TIER_2,
    String(312 + i),
    String(312 + i),
    't2',
    rectCell(xR2i, yWestT2[i], xR2o, yWestT2[i + 1])
  );
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

/* --- TIER 3 north + south only — equal strips on flats --- */

const xN3Br = equalBreaks(xL3i + r3i, topFlat3i, 3);
for (let j = 0; j < 3; j += 1) {
  push(TIER_3, String(404 + j), String(404 + j), 't3', rectCell(xN3Br[j], yT3o, xN3Br[j + 1], yT3i));
}

const xS3Br = equalBreaks(xL3i + r3i, botFlat3i, 13);
for (let j = 0; j < 13; j += 1) {
  push(
    TIER_3,
    String(419 + j),
    String(419 + j),
    't3',
    rectCell(xS3Br[j], yB3i, xS3Br[j + 1], yB3o)
  );
}

const DRAW_ORDER = [
  ...[201, 202, 203, 204, 205, 206, 207, 208, 209].map(String),
  ...[221, 222, 223, 224, 225, 226, 227, 228, 229].map(String),
  ...[236, 235, 234].map(String),
  ...[214, 215, 216].map(String),
  ...[301, 302, 303, 304, 305, 306, 307, 308, 309].map(String),
  ...[319, 320, 321, 322, 323, 324, 325, 326, 327, 328].map(String),
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
  ...[419, 420, 421, 422, 423, 424, 425, 426, 427, 428, 429, 430, 431].map(String),
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
