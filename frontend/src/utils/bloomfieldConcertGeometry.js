/**
 * Bloomfield concert layout — grid aligned to real bowl zones (stage, wings, floor, back).
 * IDs must stay in sync with `concertBlockIdFromSection` in bloomfieldConcertListing.js.
 *
 * Zones (SVG y grows downward):
 * - STAGE: top center (`STAGE_RECT`).
 * - LEFT WING: two vertical columns — 106–104 (outer), 103–101 (inner, aisle to floor).
 * - CENTER FLOOR: row A (6), rows B & C (5 each), B/C horizontally centered under A.
 * - RIGHT WING: two vertical columns — 45–47 (inner), 42–44 (outer). 47 is bottom of inner column, not beside center rows.
 * - BACK: 80A–70A (inner), 80B–71B (outer), full-width rows with aisle above.
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

export const CONCERT_CELL_W = 40;
export const CONCERT_CELL_H = 30;
/** Gap between adjacent seat blocks (horizontal within a row, vertical between wing columns) */
export const CONCERT_GAP = 5;
/** Extra vertical gap between horizontal tiers (A/B/C and south rows) */
const GAP_ROW = 10;

const W = CONCERT_CELL_W;
const H = CONCERT_CELL_H;
const G = CONCERT_GAP;
const SX = W + G;
const SY = H + GAP_ROW;

/** Lateral aisle: center floor ↔ inner wing column */
const AISLE_WING = 22;
/** Aisle: last center row (C) ↔ back (south) seating */
const AISLE_BACK = 28;

/** @typedef {{ id: string, zone: 'pitch'|'west'|'east'|'south', x: number, y: number, w: number, h: number, label: string }} ConcertBlockRect */

function block(id, zone, x, y, label) {
  return { id, zone, x, y, w: W, h: H, label };
}

/** @typedef {{ x: number, y: number, w: number, h: number }} ConcertSpacerRect */

/** Venue vertical centerline (used for centering floor + back rows) */
const centerX = VIEW_W / 2;

/** Row A: six blocks A6…A1 (left → right on screen) */
const pitchRowAW = 6 * W + 5 * G;
/** Rows B & C: five blocks each — width narrower than A; centered under A for symmetric “holes” */
const pitchRowBCW = 5 * W + 4 * G;

const oxA = centerX - pitchRowAW / 2;
const oxBC = centerX - pitchRowBCW / 2;
const oy = 96;

/** Vertical span of the three center rows (top of A → bottom of C) */
const pitchH = 3 * H + 2 * GAP_ROW;

/** @type {ConcertBlockRect[]} */
export const CONCERT_BLOCKS = [];

// --- Center floor: Row 1 — A6 … A1 (closest to stage)
for (let i = 0; i < 6; i += 1) {
  const n = 6 - i;
  CONCERT_BLOCKS.push(block(`A${n}`, 'pitch', oxA + i * SX, oy, `A${n}`));
}

// Row 2 — B5 … B1 (centered under A; aisle space left + right vs row A)
for (let i = 0; i < 5; i += 1) {
  const n = 5 - i;
  CONCERT_BLOCKS.push(block(`B${n}`, 'pitch', oxBC + i * SX, oy + SY, `B${n}`));
}

// Row 3 — C5 … C1
for (let i = 0; i < 5; i += 1) {
  const n = 5 - i;
  CONCERT_BLOCKS.push(block(`C${n}`, 'pitch', oxBC + i * SX, oy + 2 * SY, `C${n}`));
}

// --- Left wing (entirely west of center floor): outer 106–104, inner 103–101
const xWestInner = oxA - AISLE_WING - W;
const xWestOuter = xWestInner - G - W;
CONCERT_BLOCKS.push(block('106', 'west', xWestOuter, oy + 0 * SY, '106'));
CONCERT_BLOCKS.push(block('105', 'west', xWestOuter, oy + 1 * SY, '105'));
CONCERT_BLOCKS.push(block('104', 'west', xWestOuter, oy + 2 * SY, '104'));
CONCERT_BLOCKS.push(block('103', 'west', xWestInner, oy + 0 * SY, '103'));
CONCERT_BLOCKS.push(block('102', 'west', xWestInner, oy + 1 * SY, '102'));
CONCERT_BLOCKS.push(block('101', 'west', xWestInner, oy + 2 * SY, '101'));

// --- Right wing (entirely east of center floor): inner 45–47 (aisle side), outer 42–44
const xEastInner = oxA + pitchRowAW + AISLE_WING;
const xEastOuter = xEastInner + W + G;
CONCERT_BLOCKS.push(block('45', 'east', xEastInner, oy + 0 * SY, '45'));
CONCERT_BLOCKS.push(block('46', 'east', xEastInner, oy + 1 * SY, '46'));
CONCERT_BLOCKS.push(block('47', 'east', xEastInner, oy + 2 * SY, '47'));
CONCERT_BLOCKS.push(block('42', 'east', xEastOuter, oy + 0 * SY, '42'));
CONCERT_BLOCKS.push(block('43', 'east', xEastOuter, oy + 1 * SY, '43'));
CONCERT_BLOCKS.push(block('44', 'east', xEastOuter, oy + 2 * SY, '44'));

// --- Back seating: inner 80A–70A, outer 80B–71B
const southY0 = oy + pitchH + AISLE_BACK;
const south11W = 11 * W + 10 * G;
const southX0 = centerX - south11W / 2;
for (let i = 0; i <= 10; i += 1) {
  const num = 80 - i;
  const id = `${num}A`;
  CONCERT_BLOCKS.push(block(id, 'south', southX0 + i * SX, southY0, id));
}

const southY1 = southY0 + SY;
const south10W = 10 * W + 9 * G;
const southX1 = centerX - south10W / 2;
for (let i = 0; i <= 9; i += 1) {
  const num = 80 - i;
  const id = `${num}B`;
  CONCERT_BLOCKS.push(block(id, 'south', southX1 + i * SX, southY1, id));
}

/** No phantom spacer polygons — aisles are negative space (map background). */
export const CONCERT_SPACERS = /** @type {ConcertSpacerRect[]} */ ([]);

export const STAGE_RECT = {
  x: 248,
  y: 18,
  w: 504,
  h: 76,
};

export const STAGE_LABEL_CX = STAGE_RECT.x + STAGE_RECT.w / 2;
export const STAGE_LABEL_CY = STAGE_RECT.y + STAGE_RECT.h / 2;

function chamferedRectPoints(x, y, w, h, c) {
  const cc = Math.min(c, w / 2 - 0.5, h / 2 - 0.5);
  return [
    [x + cc, y],
    [x + w - cc, y],
    [x + w, y + cc],
    [x + w, y + h - cc],
    [x + w - cc, y + h],
    [x + cc, y + h],
    [x, y + h - cc],
    [x, y + cc],
  ]
    .map((p) => `${p[0]},${p[1]}`)
    .join(' ');
}

/**
 * Large light-gray ambient zones (non-seating) outside wings + behind south rows.
 */
export function getConcertAmbientPolygons() {
  const padT = 12;
  const padB = 24;
  const c = 16;
  const topY = Math.min(oy - padT, STAGE_RECT.y + STAGE_RECT.h + 2);
  const bottomY = southY1 + H + padB;

  const westW = Math.max(28, xWestOuter - 16 - 8);
  const west = chamferedRectPoints(8, topY, westW, bottomY - topY, c);

  const eastStart = xEastOuter + W + 12;
  const eastW = Math.max(28, VIEW_W - eastStart - 8);
  const east = chamferedRectPoints(eastStart, topY, eastW, bottomY - topY, c);

  const southPadX = 36;
  const southW = Math.min(VIEW_W - 20, south11W + southPadX * 2);
  const southX = centerX - southW / 2;
  const southTop = southY0 - 16;
  const southH = bottomY - southTop + 8;
  const south = chamferedRectPoints(southX, southTop, southW, southH, 14);

  return [
    { id: 'ambient-west', points: west },
    { id: 'ambient-east', points: east },
    { id: 'ambient-south', points: south },
  ];
}

/**
 * Straight, axis-aligned seat tiles with a tiny inset for stroke (clean Viagogo-like blocks).
 */
export function concertBlockPolygonPoints(b) {
  const { x, y, w, h } = b;
  const inset = 1.25;
  const x0 = x + inset;
  const y0 = y + inset;
  const x1 = x + w - inset;
  const y1 = y + h - inset;
  return `${x0},${y0} ${x1},${y0} ${x1},${y1} ${x0},${y1}`;
}
