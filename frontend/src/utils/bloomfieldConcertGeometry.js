/**
 * Bloomfield concert layout — strict orthogonal grid (upright rectangles only).
 * IDs must stay in sync with `concertBlockIdFromSection` in bloomfieldConcertListing.js.
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

export const CONCERT_CELL_W = 40;
export const CONCERT_CELL_H = 30;
export const CONCERT_GAP = 5;
const GAP_ROW = 10;

const W = CONCERT_CELL_W;
const H = CONCERT_CELL_H;
const G = CONCERT_GAP;
const SX = W + G;
const SY = H + GAP_ROW;

/** Large lateral gap: center floor ↔ wing columns (X axis) */
const AISLE_SIDE = 52;
/** Clear gap: last center row (C) ↔ back seating (Y axis) */
const AISLE_BACK = 34;

const centerX = VIEW_W / 2;

const pitchRowAW = 6 * W + 5 * G;
const pitchRowBCW = 5 * W + 4 * G;

const oxA = centerX - pitchRowAW / 2;
const oxBC = centerX - pitchRowBCW / 2;
const oy = 96;

const pitchH = 3 * H + 2 * GAP_ROW;

/** @typedef {{ id: string, zone: 'pitch'|'west'|'east'|'south', x: number, y: number, w: number, h: number, label: string }} ConcertBlockRect */

function block(id, zone, x, y, label) {
  return { id, zone, x, y, w: W, h: H, label };
}

/** @typedef {{ x: number, y: number, w: number, h: number }} ConcertSpacerRect */

/** @type {ConcertBlockRect[]} */
export const CONCERT_BLOCKS = [];

// --- Center floor (rows A, B, C — straight horizontal rectangles)
for (let i = 0; i < 6; i += 1) {
  const n = 6 - i;
  CONCERT_BLOCKS.push(block(`A${n}`, 'pitch', oxA + i * SX, oy, `A${n}`));
}
for (let i = 0; i < 5; i += 1) {
  const n = 5 - i;
  CONCERT_BLOCKS.push(block(`B${n}`, 'pitch', oxBC + i * SX, oy + SY, `B${n}`));
}
for (let i = 0; i < 5; i += 1) {
  const n = 5 - i;
  CONCERT_BLOCKS.push(block(`C${n}`, 'pitch', oxBC + i * SX, oy + 2 * SY, `C${n}`));
}

// --- Left wing: outer (106–104), inner (103–101), far left of floor + wide aisle
const xWestInner = oxA - AISLE_SIDE - W;
const xWestOuter = xWestInner - G - W;
CONCERT_BLOCKS.push(block('106', 'west', xWestOuter, oy + 0 * SY, '106'));
CONCERT_BLOCKS.push(block('105', 'west', xWestOuter, oy + 1 * SY, '105'));
CONCERT_BLOCKS.push(block('104', 'west', xWestOuter, oy + 2 * SY, '104'));
CONCERT_BLOCKS.push(block('103', 'west', xWestInner, oy + 0 * SY, '103'));
CONCERT_BLOCKS.push(block('102', 'west', xWestInner, oy + 1 * SY, '102'));
CONCERT_BLOCKS.push(block('101', 'west', xWestInner, oy + 2 * SY, '101'));

// --- Right wing: inner (45–47), outer (42–44), far right of floor + wide aisle
const xEastInner = oxA + pitchRowAW + AISLE_SIDE;
const xEastOuter = xEastInner + W + G;
CONCERT_BLOCKS.push(block('45', 'east', xEastInner, oy + 0 * SY, '45'));
CONCERT_BLOCKS.push(block('46', 'east', xEastInner, oy + 1 * SY, '46'));
CONCERT_BLOCKS.push(block('47', 'east', xEastInner, oy + 2 * SY, '47'));
CONCERT_BLOCKS.push(block('42', 'east', xEastOuter, oy + 0 * SY, '42'));
CONCERT_BLOCKS.push(block('43', 'east', xEastOuter, oy + 1 * SY, '43'));
CONCERT_BLOCKS.push(block('44', 'east', xEastOuter, oy + 2 * SY, '44'));

// --- Back: two straight horizontal rows (80A–70A, 80B–71B)
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

export const CONCERT_SPACERS = /** @type {ConcertSpacerRect[]} */ ([]);

export const STAGE_RECT = {
  x: 248,
  y: 18,
  w: 504,
  h: 76,
};

export const STAGE_LABEL_CX = STAGE_RECT.x + STAGE_RECT.w / 2;
export const STAGE_LABEL_CY = STAGE_RECT.y + STAGE_RECT.h / 2;

/** Axis-aligned rectangle as SVG polygon `points` (no chamfers, no curves). */
function rectPolygonPoints(x, y, w, h) {
  const x1 = x + w;
  const y1 = y + h;
  return `${x},${y} ${x1},${y} ${x1},${y1} ${x},${y1}`;
}

/**
 * Neutral background slabs — plain orthogonal rects only.
 */
export function getConcertAmbientPolygons() {
  const padT = 12;
  const padB = 24;
  const topY = Math.min(oy - padT, STAGE_RECT.y + STAGE_RECT.h + 2);
  const bottomY = southY1 + H + padB;

  const westX = 8;
  const westW = Math.max(24, xWestOuter - westX - 8);
  const bandH = bottomY - topY;

  const eastX = xEastOuter + W + 12;
  const eastW = Math.max(24, VIEW_W - eastX - 8);

  const southPadX = 28;
  const southX = Math.min(southX0, southX1) - southPadX;
  const southW = Math.max(southX0 + south11W, southX1 + south10W) - southX + southPadX * 2;
  const southY = southY0 - 14;
  const southH = bottomY - southY + 6;

  return [
    { id: 'ambient-west', points: rectPolygonPoints(westX, topY, westW, bandH) },
    { id: 'ambient-east', points: rectPolygonPoints(eastX, topY, eastW, bandH) },
    { id: 'ambient-south', points: rectPolygonPoints(southX, southY, southW, southH) },
  ];
}

/**
 * Every seat block: upright axis-aligned rectangle (tiny inset for stroke).
 */
export function concertBlockPolygonPoints(b) {
  const { x, y, w, h } = b;
  const inset = 1.25;
  return rectPolygonPoints(x + inset, y + inset, w - 2 * inset, h - 2 * inset);
}
