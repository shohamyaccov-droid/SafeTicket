/**
 * Pais Arena Jerusalem — elongated oval bowl, 2 tiers, uniform angular sectors.
 *
 * Stage gap is on the LEFT (west, θ = π). Sections are numbered clockwise on
 * screen (= increasing θ in SVG y-down coords) starting from the upper edge
 * of the stage gap, matching the physical seating chart orientation:
 *
 *   Lower (Level 100): 18 active sections 103–120
 *     gap = 4/22 × 2π = 4π/11 ≈ 65.5° (sections 101-102 & 121-122 blocked)
 *
 *   Upper (Level 300): 24 active sections 304–327
 *     gap = 6/30 × 2π = 2π/5 ≈ 72°   (sections 301-303 & 328-330 blocked)
 */

// --- Active section IDs -------------------------------------------------------
/** Level 100: 18 active blocks, 103–120 */
export const LOWER_SECTION_IDS = Array.from({ length: 18 }, (_, i) => 103 + i);
/** Level 300: 24 active blocks, 304–327 */
export const UPPER_SECTION_IDS = Array.from({ length: 24 }, (_, i) => 304 + i);

export const SECTIONS_LOWER = 18;
export const SECTIONS_UPPER = 24;

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

/** Aisle gap between tiers (applied to both axes) */
const RING_GAP = 8;

const UPPER_RX_IN = LOWER_RX_OUT + RING_GAP;
const UPPER_RY_IN = LOWER_RY_OUT + RING_GAP;
/** Upper tier radial depth (added to both semi-axes) */
const UPPER_DEPTH = 58;
const UPPER_RX_OUT = UPPER_RX_IN + UPPER_DEPTH;
const UPPER_RY_OUT = UPPER_RY_IN + UPPER_DEPTH;

/** Arena shell (background floor ellipse) */
export const ARENA_FLOOR_RX = 392;
export const ARENA_FLOOR_RY = 268;

/** Elongated floor / court area (center of arena) */
export const COURT_X = 250;
export const COURT_Y = 228;
export const COURT_W = 300;
export const COURT_H = 144;
export const COURT_RX = 10;

// ─── Arc generation ──────────────────────────────────────────────────────────
//
// Stage gap: centered at θ = π (west/left).
//
// Lower ring: 4 slots blocked out of 22 → gap = 4/22 × 2π = 4π/11 rad
// Upper ring: 6 slots blocked out of 30 → gap = 6/30 × 2π = 2π/5  rad
//
// For each ring, `count` uniform sections fill (2π − gapAngle) of arc.
// Section i=0 (e.g. section 103) starts at (π + gapAngle/2), which is the
// upper-left edge of the stage gap in screen coordinates.
// Sections proceed clockwise on screen (= increasing θ in SVG y-down).
// ─────────────────────────────────────────────────────────────────────────────

/** Total stage-gap angle for the lower ring (4 blocked out of 22 total slots) */
const LOWER_GAP = (4 / 22) * (2 * Math.PI); // 4π/11 ≈ 1.143 rad ≈ 65.5°

/** Total stage-gap angle for the upper ring (6 blocked out of 30 total slots) */
const UPPER_GAP = (6 / 30) * (2 * Math.PI); // 2π/5  ≈ 1.257 rad ≈ 72°

/**
 * Generate `count` equal-span arc segments for one tier.
 * Sections start at the upper edge of the stage gap (π + gapAngle/2) and
 * increase clockwise (increasing θ) until the lower edge of the gap.
 *
 * @param {number} count     - number of active sections in this tier
 * @param {number} gapAngle  - total angular width of the stage gap (rad)
 * @returns {{ a0: number, a1: number }[]}
 */
function anglesForArc(count, gapAngle) {
  const arcSpan = 2 * Math.PI - gapAngle;
  const d = arcSpan / count;
  const startAngle = Math.PI + gapAngle / 2; // upper edge of stage gap
  const segments = [];
  for (let i = 0; i < count; i += 1) {
    const a0 = startAngle + i * d;
    const a1 = startAngle + (i + 1) * d;
    segments.push({ a0, a1 });
  }
  return segments;
}

// ─── Shared geometry helpers ─────────────────────────────────────────────────

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

/**
 * Build an SVG path for one elliptical annular sector, inset by CELL_IN on
 * each side to leave a visible gap between adjacent sections.
 */
function ellipticalAnnularSector(cx0, cy0, rxIn, ryIn, rxOut, ryOut, a0, a1, steps = 22) {
  const rxi = rxIn + CELL_IN;
  const ryi = ryIn + CELL_IN;
  const rxo = rxOut - CELL_IN;
  const ryo = ryOut - CELL_IN;
  if (rxo <= rxi + 1e-3 || ryo <= ryi + 1e-3) return null;
  const pts = [];
  // Outer arc (a0 → a1)
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    const a = a0 + t * (a1 - a0);
    pts.push({ x: cx0 + rxo * Math.cos(a), y: cy0 + ryo * Math.sin(a) });
  }
  // Inner arc (a1 → a0, reversed)
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

// ─── Build section wedges ────────────────────────────────────────────────────

const LOWER = [];
const UPPER = [];

const lowerAngles = anglesForArc(SECTIONS_LOWER, LOWER_GAP);
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

const upperAngles = anglesForArc(SECTIONS_UPPER, UPPER_GAP);
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

// ─── Exports ─────────────────────────────────────────────────────────────────

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

/**
 * Map a raw section string/number from ticket data to the nearest renderable
 * block id. Stage-adjacent blocked sections (101-102, 121-122, 301-303, 328-330)
 * are clamped to the nearest active section.
 */
export function blockIdFromSectionNumber(numStr) {
  if (!numStr || numStr === '—') return '103';
  const n = parseInt(String(numStr), 10);
  if (Number.isNaN(n)) return '103';
  const s = String(n);
  if (ALL_BLOCK_IDS.has(s)) return s;
  // Lower tier range (101–122) — clamp to active 103–120
  if (n >= 101 && n <= 122) {
    if (n < 103) return '103';
    if (n > 120) return '120';
    return s;
  }
  // Upper tier range (301–330) — clamp to active 304–327
  if (n >= 301 && n <= 330) {
    if (n < 304) return '304';
    if (n > 327) return '327';
    return s;
  }
  return '103';
}
