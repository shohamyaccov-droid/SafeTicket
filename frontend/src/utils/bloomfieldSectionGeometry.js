/**
 * Bloomfield — 4-stand “squircle” model: N/S/E/W rectangular bands + 4 corner arc wedges.
 * Inner/outer tiers flush; east is inner-only. Clockwise from north-west: 301 (north-left) … 337 (west bottom).
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

export const CX = 500;
export const CY = 320;

export const PITCH_W = Math.round(300 * 0.83);
export const PITCH_H = Math.round(168 * 0.83);
export const PITCH_RX = 5;
export const PITCH_RY = 5;

const GAP = 32;
/** Inner tier radial depth (hole → inner-back). */
const dInner = 52;
/** Outer tier depth (inner-back → outer-back). */
const dOuter = 48;

const wi = PITCH_W + 2 * GAP;
const hi = PITCH_H + 2 * GAP;
/** Hole / moat corner radius — moderate squircle (not a circle). */
const ri = Math.min(40, Math.min(wi, hi) * 0.14 + 18);

const xL = CX - wi / 2;
const xR = CX + wi / 2;
const yT = CY - hi / 2;
const yB = CY + hi / 2;

const topFlatW = wi - 2 * ri;
const bottomFlatW = topFlatW;
const westFlatH = hi - 2 * ri;

/** Inset between cells so white strokes read as aisles (half of ~1px gap in user space). */
const CELL_IN = 0.45;

function fmt(n) {
  return Number(n.toFixed(4));
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

/** Annular sector: sweep angle a0 → a1 (radians), CCW in standard math with y right/x; works with SVG sin/cos. */
function annularSector(cx0, cy0, rIn, rOut, a0, a1, steps = 16) {
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

function pushWedge(list, id, faceLabel, tier, wedge) {
  if (wedge && wedge.d) list.push({ id, faceLabel, d: wedge.d, cx: wedge.cx, cy: wedge.cy, tier });
}

const SECTION_WEDGES_BUILD = [];

/* --- Inner tier: straight stands --- */

const yInnerN0 = yT - dInner;
const yInnerN1 = yT;
for (let i = 0; i < 9; i += 1) {
  const xa = xL + ri + (i / 9) * topFlatW;
  const xb = xL + ri + ((i + 1) / 9) * topFlatW;
  const w = rectCell(xa, yInnerN0, xb, yInnerN1);
  pushWedge(SECTION_WEDGES_BUILD, String(301 + i), String(301 + i), 'lower', w);
}

const yInnerS0 = yB;
const yInnerS1 = yB + dInner;
for (let i = 0; i < 10; i += 1) {
  const xa = xR - ri - (i / 10) * bottomFlatW;
  const xb = xR - ri - ((i + 1) / 10) * bottomFlatW;
  const w = rectCell(xb, yInnerS0, xa, yInnerS1);
  pushWedge(SECTION_WEDGES_BUILD, String(328 - i), String(328 - i), 'lower', w);
}

const xInnerW0 = xL - dInner;
const xInnerW1 = xL;
for (let i = 0; i < 6; i += 1) {
  const ya = yT + ri + (i / 6) * westFlatH;
  const yb = yT + ri + ((i + 1) / 6) * westFlatH;
  const w = rectCell(xInnerW0, ya, xInnerW1, yb);
  pushWedge(SECTION_WEDGES_BUILD, String(332 + i), String(332 + i), 'lower', w);
}

const xInnerE0 = xR;
const xInnerE1 = xR + dInner;
for (let i = 0; i < 6; i += 1) {
  const ya = yT + ri + (i / 6) * westFlatH;
  const yb = yT + ri + ((i + 1) / 6) * westFlatH;
  const w = rectCell(xInnerE0, ya, xInnerE1, yb);
  pushWedge(SECTION_WEDGES_BUILD, String(312 + i), String(312 + i), 'lower', w);
}

/* --- Inner tier: corners (annular sectors around hole fillet centers) --- */

const cnw = { x: xL + ri, y: yT + ri };
const cne = { x: xR - ri, y: yT + ri };
const cse = { x: xR - ri, y: yB - ri };
const csw = { x: xL + ri, y: yB - ri };

pushWedge(
  SECTION_WEDGES_BUILD,
  '338',
  '338',
  'lower',
  annularSector(cnw.x, cnw.y, ri + CELL_IN, ri + dInner - CELL_IN, -Math.PI / 2, -Math.PI)
);

const ne310a = annularSector(cne.x, cne.y, ri + CELL_IN, ri + dInner - CELL_IN, -Math.PI / 2, -Math.PI / 4, 8);
const ne311a = annularSector(cne.x, cne.y, ri + CELL_IN, ri + dInner - CELL_IN, -Math.PI / 4, 0, 8);
pushWedge(SECTION_WEDGES_BUILD, '310', '310', 'lower', ne310a);
pushWedge(SECTION_WEDGES_BUILD, '311', '311', 'lower', ne311a);

pushWedge(
  SECTION_WEDGES_BUILD,
  '318',
  '318',
  'lower',
  annularSector(cse.x, cse.y, ri + CELL_IN, ri + dInner - CELL_IN, 0, Math.PI / 2)
);

const swA = Math.PI / 2;
const swB = Math.PI;
const swThird = (swB - swA) / 3;
const sw1 = annularSector(csw.x, csw.y, ri + CELL_IN, ri + dInner - CELL_IN, swA, swA + swThird, 6);
const sw2 = annularSector(csw.x, csw.y, ri + CELL_IN, ri + dInner - CELL_IN, swA + swThird, swA + 2 * swThird, 6);
const sw3 = annularSector(csw.x, csw.y, ri + CELL_IN, ri + dInner - CELL_IN, swA + 2 * swThird, swB, 6);
pushWedge(SECTION_WEDGES_BUILD, '329', '329', 'lower', sw1);
pushWedge(SECTION_WEDGES_BUILD, '330', '330', 'lower', sw2);
pushWedge(SECTION_WEDGES_BUILD, '331', '331', 'lower', sw3);

/* --- Outer tier: flush behind inner --- */

const yOutN0 = yT - dInner - dOuter;
const yOutN1 = yT - dInner;
const northOuterFrac = 0.38;
const nx0 = xL + ri + topFlatW * (0.5 - northOuterFrac / 2);
const nx1 = xL + ri + topFlatW * (0.5 + northOuterFrac / 2);
for (let i = 0; i < 3; i += 1) {
  const xa = nx0 + (i / 3) * (nx1 - nx0);
  const xb = nx0 + ((i + 1) / 3) * (nx1 - nx0);
  const w = rectCell(xa, yOutN0, xb, yOutN1);
  pushWedge(SECTION_WEDGES_BUILD, String(404 + i), String(404 + i), 'upper', w);
}

const yOutS0 = yB + dInner;
const yOutS1 = yB + dInner + dOuter;
for (let i = 0; i < 9; i += 1) {
  const xa = xR - ri - (i / 9) * bottomFlatW;
  const xb = xR - ri - ((i + 1) / 9) * bottomFlatW;
  const w = rectCell(xb, yOutS0, xa, yOutS1);
  pushWedge(SECTION_WEDGES_BUILD, String(221 + i), String(221 + i), 'upper', w);
}

const xOutW0 = xL - dInner - dOuter;
const xOutW1 = xL - dInner;
for (let i = 0; i < 12; i += 1) {
  const ya = yT + ri + (i / 12) * westFlatH;
  const yb = yT + ri + ((i + 1) / 12) * westFlatH;
  const w = rectCell(xOutW0, ya, xOutW1, yb);
  pushWedge(SECTION_WEDGES_BUILD, String(420 + i), String(420 + i), 'upper', w);
}

/** Stable draw + hit order: lower straights by edge, corners, upper — reorder for cleaner overlap. */
const ORDER_IDS = [
  ...[301, 302, 303, 304, 305, 306, 307, 308, 309].map(String),
  ...[328, 327, 326, 325, 324, 323, 322, 321, 320, 319].map(String),
  ...[332, 333, 334, 335, 336, 337].map(String),
  ...[312, 313, 314, 315, 316, 317].map(String),
  '338',
  '310',
  '311',
  '318',
  '329',
  '330',
  '331',
  ...[404, 405, 406].map(String),
  ...[221, 222, 223, 224, 225, 226, 227, 228, 229].map(String),
  ...[420, 421, 422, 423, 424, 425, 426, 427, 428, 429, 430, 431].map(String),
];

const byId = Object.fromEntries(SECTION_WEDGES_BUILD.map((s) => [s.id, s]));
export const SECTION_WEDGES = ORDER_IDS.map((id) => byId[id]).filter(Boolean);

const ALL_BLOCK_IDS = new Set(SECTION_WEDGES.map((s) => s.id));

export const LOWER_WEDGE_IDS = SECTION_WEDGES.filter((s) => s.tier === 'lower').map((s) => s.id);
export const UPPER_WEDGE_IDS = SECTION_WEDGES.filter((s) => s.tier === 'upper').map((s) => s.id);
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

const depthTotal = dInner + dOuter;
const Wo = wi + 2 * depthTotal;
const Ho = hi + 2 * depthTotal;
const Ro = Math.min(ri + depthTotal, Wo / 2 - 2, Ho / 2 - 2);
export const BOWL_OUTER_D = roundedRectPathD(CX, CY, Wo, Ho, Ro);
