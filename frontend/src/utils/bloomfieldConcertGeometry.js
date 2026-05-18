/**
 * Bloomfield concert layout — strict orthogonal grid (upright rectangles only).
 * IDs must stay in sync with `concertBlockIdFromSection` in bloomfieldConcertListing.js.
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

/** ~45% larger than legacy 40×30 for readability */
export const CONCERT_CELL_W = 58;
export const CONCERT_CELL_H = 44;
export const CONCERT_GAP = 5;
const GAP_ROW = 8;

const W = CONCERT_CELL_W;
const H = CONCERT_CELL_H;
const G = CONCERT_GAP;
const SX = W + G;
const SY = H + GAP_ROW;

/** Center floor ↔ single wing column */
const AISLE_SIDE = 26;
/** Last center row (C) ↔ back row (80A) */
const AISLE_BACK = 18;

const centerX = VIEW_W / 2;

const pitchRowAW = 6 * W + 5 * G;
const pitchRowBCW = 5 * W + 4 * G;

const oxA = centerX - pitchRowAW / 2;
const oxBC = centerX - pitchRowBCW / 2;
const oy = 88;

const pitchH = 3 * H + 2 * GAP_ROW;

/** Y gap: bottom of wing column ↔ top of back row (80A) */
const AISLE_WING_TO_SOUTH = 10;

/** @typedef {{ id: string, zone: 'pitch'|'west'|'east'|'south', x: number, y: number, w: number, h: number, label: string }} ConcertBlockRect */

function block(id, zone, x, y, label, hh = H) {
  return { id, zone, x, y, w: W, h: hh, label };
}

/** @typedef {{ x: number, y: number, w: number, h: number }} ConcertSpacerRect */

/** @type {ConcertBlockRect[]} */
export const CONCERT_BLOCKS = [];

// --- Center floor (rows A, B, C)
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

const southY0 = oy + pitchH + AISLE_BACK;

const wingSpanMax = southY0 - AISLE_WING_TO_SOUTH;
const wingInterGap = 2;
const wingH = Math.max(
  18,
  Math.min(H, Math.floor((wingSpanMax - oy - 5 * wingInterGap) / 6))
);
const wingStep = wingH + wingInterGap;

const xWest = oxA - AISLE_SIDE - W;
const leftWingIds = ['106', '105', '104', '103', '102', '101'];
for (let i = 0; i < 6; i += 1) {
  const id = leftWingIds[i];
  CONCERT_BLOCKS.push(block(id, 'west', xWest, oy + i * wingStep, id, wingH));
}

const xEast = oxA + pitchRowAW + AISLE_SIDE;
const rightWingIds = ['42', '43', '44', '45', '46', '47'];
for (let i = 0; i < 6; i += 1) {
  const id = rightWingIds[i];
  CONCERT_BLOCKS.push(block(id, 'east', xEast, oy + i * wingStep, id, wingH));
}

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

function rectPolygonPoints(x, y, w, h) {
  const x1 = x + w;
  const y1 = y + h;
  return `${x},${y} ${x1},${y} ${x1},${y1} ${x},${y1}`;
}

/** Background slabs removed — keep export for callers; returns nothing to draw. */
export function getConcertAmbientPolygons() {
  return [];
}

export function concertBlockPolygonPoints(b) {
  const { x, y, w, h } = b;
  const inset = 1.5;
  return rectPolygonPoints(x + inset, y + inset, w - 2 * inset, h - 2 * inset);
}
