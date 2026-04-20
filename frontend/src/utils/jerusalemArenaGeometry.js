/**
 * Pais Arena Jerusalem — 2-tier symmetric bowl (lower + upper), uniform angular sectors.
 * Same idea as Menora: equal span/count around the ring; annular sectors + CELL_IN grid gaps.
 */

// --- Editable section IDs (match ticket `section` / listing text) -----------------
export const LOWER_SECTION_IDS = [
  101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112,
];
export const UPPER_SECTION_IDS = [
  201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212,
];
export const SECTIONS_PER_RING = 12;

// ---------------------------------------------------------------------------------

export const VIEW_W = 800;
export const VIEW_H = 600;

export const CX = 400;
export const CY = 300;

const CELL_IN = 0.45;

/** Lower ring inner / outer radii (px, viewBox space) */
const R_LOWER_IN = 168;
const R_LOWER_OUT = 232;
/** Gap between lower outer and upper inner (aisle) */
const RING_GAP = 6;
/** Upper ring depth */
const R_UPPER_DEPTH = 64;

const R_UPPER_IN = R_LOWER_OUT + RING_GAP;
const R_UPPER_OUT = R_UPPER_IN + R_UPPER_DEPTH;

/** First sector starts here (radians). π/2 sweep per step from Menora-style layout: sector 101 centered at top (−π/2). */
const SECTOR_START_RAD = -Math.PI / 2 - Math.PI / SECTIONS_PER_RING;
const ANGLE_STEP = (2 * Math.PI) / SECTIONS_PER_RING;

/** Central court (matches Menora proportions) */
export const COURT_X = 280;
export const COURT_Y = 220;
export const COURT_W = 240;
export const COURT_H = 160;
export const COURT_RX = 8;

/** Arena floor ellipse (behind seats) */
export const ARENA_FLOOR_RX = 378;
export const ARENA_FLOOR_RY = 278;

function fmt(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return 0;
  return Number(v.toFixed(4));
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

/** Standalone annular sector; inner/outer radii inset by CELL_IN for crisp white grid. */
function annularSector(cx0, cy0, rIn, rOut, a0, a1, steps = 18) {
  const rin = rIn + CELL_IN;
  const rout = rOut - CELL_IN;
  if (!Number.isFinite(rin) || !Number.isFinite(rout) || rout <= rin + 1e-3) return null;
  const pts = [];
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    const a = a0 + t * (a1 - a0);
    pts.push({ x: cx0 + rout * Math.cos(a), y: cy0 + rout * Math.sin(a) });
  }
  for (let i = steps; i >= 0; i -= 1) {
    const t = i / steps;
    const a = a0 + t * (a1 - a0);
    pts.push({ x: cx0 + rin * Math.cos(a), y: cy0 + rin * Math.sin(a) });
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

const LOWER = [];
const UPPER = [];

for (let i = 0; i < SECTIONS_PER_RING; i += 1) {
  const a0 = SECTOR_START_RAD + i * ANGLE_STEP;
  const a1 = a0 + ANGLE_STEP;
  const id = String(LOWER_SECTION_IDS[i]);
  push(LOWER, id, id, 'lower', annularSector(CX, CY, R_LOWER_IN, R_LOWER_OUT, a0, a1));
}

for (let i = 0; i < SECTIONS_PER_RING; i += 1) {
  const a0 = SECTOR_START_RAD + i * ANGLE_STEP;
  const a1 = a0 + ANGLE_STEP;
  const id = String(UPPER_SECTION_IDS[i]);
  push(UPPER, id, id, 'upper', annularSector(CX, CY, R_UPPER_IN, R_UPPER_OUT, a0, a1));
}

const DRAW_ORDER = [
  ...LOWER_SECTION_IDS.map(String),
  ...UPPER_SECTION_IDS.map(String),
];

const byId = Object.fromEntries([...LOWER, ...UPPER].map((s) => [s.id, s]));

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

export const LOWER_WEDGE_IDS = LOWER.map((s) => s.id);
export const UPPER_WEDGE_IDS = UPPER.map((s) => s.id);
export const WEDGE_IDS = SECTION_WEDGES.map((s) => s.id);

export function blockIdFromSectionNumber(numStr) {
  if (!numStr || numStr === '—') return '101';
  const n = parseInt(String(numStr), 10);
  if (Number.isNaN(n)) return '101';
  const s = String(n);
  if (ALL_BLOCK_IDS.has(s)) return s;
  if (n >= 1 && n <= 12) return String(100 + n);
  return '101';
}
