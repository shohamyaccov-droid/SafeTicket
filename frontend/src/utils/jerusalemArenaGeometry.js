/**
 * Pais Arena Jerusalem — elongated oval bowl, 2 tiers, uniform angular sectors.
 * Clockwise from 9 o'clock (middle-left): θ = π, decreasing θ (equal Δθ per section).
 */

// --- Editable section IDs (match ticket `section` / listing text) -----------------
/** Level 100: 22 blocks, 101–122 */
export const LOWER_SECTION_IDS = Array.from({ length: 22 }, (_, i) => 101 + i);
/** Level 300: 30 blocks, 301–330 */
export const UPPER_SECTION_IDS = Array.from({ length: 30 }, (_, i) => 301 + i);

export const SECTIONS_LOWER = 22;
export const SECTIONS_UPPER = 30;

// ---------------------------------------------------------------------------------

export const VIEW_W = 800;
export const VIEW_H = 600;

export const CX = 400;
export const CY = 300;

const CELL_IN = 0.45;

/** Ellipse semi-axes (px): wider than tall — horizontal major axis */
const LOWER_RX_IN = 188;
const LOWER_RY_IN = 118;
const LOWER_RX_OUT = 258;
const LOWER_RY_OUT = 162;

/** Aisle between tiers (applied to both axes) */
const RING_GAP = 8;

const UPPER_RX_IN = LOWER_RX_OUT + RING_GAP;
const UPPER_RY_IN = LOWER_RY_OUT + RING_GAP;
/** Upper tier radial depth (added to both semi-axes) */
const UPPER_DEPTH = 58;
const UPPER_RX_OUT = UPPER_RX_IN + UPPER_DEPTH;
const UPPER_RY_OUT = UPPER_RY_IN + UPPER_DEPTH;

/** Arena shell (floor behind seats) */
export const ARENA_FLOOR_RX = 392;
export const ARENA_FLOOR_RY = 268;

/** Elongated court / floor (center hole) */
export const COURT_X = 250;
export const COURT_Y = 228;
export const COURT_W = 300;
export const COURT_H = 144;
export const COURT_RX = 10;

/**
 * Math angle θ: 0 = east (3 o'clock), π = west (9 o'clock). SVG: y increases down.
 * Clockwise from 9 o'clock: θ decreases — sector i: [π − φ − iΔθ, π − φ − (i+1)Δθ].
 * Optional φ (phaseOffset): upper tier uses half-step so 301 starts just above middle-left vs 101.
 */
function anglesForRing(count, phaseOffset = 0) {
  const d = (2 * Math.PI) / count;
  const segments = [];
  for (let i = 0; i < count; i += 1) {
    const a0 = Math.PI - phaseOffset - i * d;
    const a1 = Math.PI - phaseOffset - (i + 1) * d;
    segments.push({ a0, a1 });
  }
  return segments;
}

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

/** Elliptical annular sector; CELL_IN insets along both axes (grid gaps). */
function ellipticalAnnularSector(cx0, cy0, rxIn, ryIn, rxOut, ryOut, a0, a1, steps = 22) {
  const rxi = rxIn + CELL_IN;
  const ryi = ryIn + CELL_IN;
  const rxo = rxOut - CELL_IN;
  const ryo = ryOut - CELL_IN;
  if (rxo <= rxi + 1e-3 || ryo <= ryi + 1e-3) return null;
  const pts = [];
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    const a = a0 + t * (a1 - a0);
    pts.push({ x: cx0 + rxo * Math.cos(a), y: cy0 + ryo * Math.sin(a) });
  }
  for (let i = steps; i >= 0; i -= 1) {
    const t = i / steps;
    const a = a0 + t * (a1 - a0);
    pts.push({ x: cx0 + rxi * Math.cos(a), y: cy0 + ryi * Math.sin(a) });
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

const lowerAngles = anglesForRing(SECTIONS_LOWER, 0);
for (let i = 0; i < SECTIONS_LOWER; i += 1) {
  const { a0, a1 } = lowerAngles[i];
  const id = String(LOWER_SECTION_IDS[i]);
  push(
    LOWER,
    id,
    id,
    'lower',
    ellipticalAnnularSector(CX, CY, LOWER_RX_IN, LOWER_RY_IN, LOWER_RX_OUT, LOWER_RY_OUT, a0, a1)
  );
}

const upperAngles = anglesForRing(SECTIONS_UPPER, (2 * Math.PI) / SECTIONS_UPPER / 2);
for (let i = 0; i < SECTIONS_UPPER; i += 1) {
  const { a0, a1 } = upperAngles[i];
  const id = String(UPPER_SECTION_IDS[i]);
  push(
    UPPER,
    id,
    id,
    'upper',
    ellipticalAnnularSector(CX, CY, UPPER_RX_IN, UPPER_RY_IN, UPPER_RX_OUT, UPPER_RY_OUT, a0, a1)
  );
}

const DRAW_ORDER = [...LOWER_SECTION_IDS.map(String), ...UPPER_SECTION_IDS.map(String)];

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
  if (n >= 101 && n <= 122) return String(n);
  if (n >= 301 && n <= 330) return String(n);
  return '101';
}
