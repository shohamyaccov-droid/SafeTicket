/**
 * Bloomfield concert layout — schematic blocks (pitch A/B/C, west/east towers, south curve).
 * IDs must match `concertBlockIdFromSection` in bloomfieldConcertListing.js.
 */

export const VIEW_W = 1000;
export const VIEW_H = 640;

/** @typedef {{ id: string, zone: 'pitch'|'west'|'east'|'south', x: number, y: number, w: number, h: number, label: string }} ConcertBlockRect */

function rect(id, zone, x, y, w, h, label) {
  return { id, zone, x, y, w, h, label };
}

/** Uniform ring spacing: pitch ↔ stands and between pitch rows */
const RING_GAP = 6;
const PITCH_GAP_H = 5;
const PITCH_GAP_V = 5;

/** Pitch — ~17% smaller than prior 129×94 so ring blocks can read at similar scale */
const CELL_W = 108;
const ROW_H_AB = 79;
const ROW_H_C = 77;
const ROW_A_W = 6 * CELL_W + 5 * PITCH_GAP_H;
const ROW_A_START_X = VIEW_W / 2 - ROW_A_W / 2;
const ROW_BC_START_X = ROW_A_START_X + (CELL_W + PITCH_GAP_H) / 2;
const ROW_A_Y = 102;
const PITCH_BOTTOM = ROW_A_Y + ROW_H_AB + PITCH_GAP_V + ROW_H_AB + PITCH_GAP_V + ROW_H_C;

/** @type {ConcertBlockRect[]} */
export const CONCERT_BLOCKS = [
  ...[6, 5, 4, 3, 2, 1].map((n, i) =>
    rect(`A${n}`, 'pitch', ROW_A_START_X + i * (CELL_W + PITCH_GAP_H), ROW_A_Y, CELL_W, ROW_H_AB, `A${n}`)
  ),
  ...[5, 4, 3, 2, 1].map((n, i) =>
    rect(
      `B${n}`,
      'pitch',
      ROW_BC_START_X + i * (CELL_W + PITCH_GAP_H),
      ROW_A_Y + ROW_H_AB + PITCH_GAP_V,
      CELL_W,
      ROW_H_AB,
      `B${n}`
    )
  ),
  ...[5, 4, 3, 2, 1].map((n, i) =>
    rect(
      `C${n}`,
      'pitch',
      ROW_BC_START_X + i * (CELL_W + PITCH_GAP_H),
      ROW_A_Y + ROW_H_AB + PITCH_GAP_V + ROW_H_AB + PITCH_GAP_V,
      CELL_W,
      ROW_H_C,
      `C${n}`
    )
  ),
];

/** West / east towers — thick blocks, ~same width as pitch cell; stacked height tracks pitch stack */
const WEST_W = 100;
const WEST_X = Math.round(ROW_A_START_X - RING_GAP - WEST_W);
const WEST_GAP = 4;
const PITCH_STACK_H = ROW_H_AB + PITCH_GAP_V + ROW_H_AB + PITCH_GAP_V + ROW_H_C;
const WEST_H = Math.floor((PITCH_STACK_H - 5 * WEST_GAP) / 6);
const WEST_TOP = ROW_A_Y;

/** West stand: 106 top → 101 bottom */
for (let n = 106, i = 0; n >= 101; n -= 1, i += 1) {
  CONCERT_BLOCKS.push(rect(String(n), 'west', WEST_X, WEST_TOP + i * (WEST_H + WEST_GAP), WEST_W, WEST_H, String(n)));
}

const EAST_X = Math.round(ROW_A_START_X + ROW_A_W + RING_GAP);
/** East: 42 top → 47 bottom */
for (let n = 42, i = 0; n <= 47; n += 1, i += 1) {
  CONCERT_BLOCKS.push(rect(String(n), 'east', EAST_X, WEST_TOP + i * (WEST_H + WEST_GAP), WEST_W, WEST_H, String(n)));
}

/** South — width aligned to pitch row; taller cells; snug under pitch */
const SOUTH_GAP = 5;
const SOUTH_ROW_TARGET_W = ROW_A_W;
const SOUTH_CELL_W = Math.floor((SOUTH_ROW_TARGET_W - 10 * SOUTH_GAP) / 11);
const SOUTH_ROW_W = 11 * SOUTH_CELL_W + 10 * SOUTH_GAP;
const SOUTH_START_X = VIEW_W / 2 - SOUTH_ROW_W / 2;
const SOUTH_INNER_Y = PITCH_BOTTOM + RING_GAP;
const SOUTH_INNER_H = 52;
for (let i = 0; i <= 10; i += 1) {
  const num = 80 - i;
  const id = `${num}A`;
  CONCERT_BLOCKS.push(
    rect(id, 'south', SOUTH_START_X + i * (SOUTH_CELL_W + SOUTH_GAP), SOUTH_INNER_Y, SOUTH_CELL_W, SOUTH_INNER_H, id)
  );
}

/** South outer 80B … 71B */
const SOUTH_OUTER_H = 50;
const SOUTH_OUTER_Y = SOUTH_INNER_Y + SOUTH_INNER_H + SOUTH_GAP;
const SOUTH_OUTER_ROW_W = 10 * SOUTH_CELL_W + 9 * SOUTH_GAP;
const SOUTH_OUTER_START_X = VIEW_W / 2 - SOUTH_OUTER_ROW_W / 2 + SOUTH_CELL_W * 0.5;
for (let i = 0; i <= 9; i += 1) {
  const num = 80 - i;
  const id = `${num}B`;
  CONCERT_BLOCKS.push(
    rect(id, 'south', SOUTH_OUTER_START_X + i * (SOUTH_CELL_W + SOUTH_GAP), SOUTH_OUTER_Y, SOUTH_CELL_W, SOUTH_OUTER_H, id)
  );
}

/** Stage bounding box (for label); T-shape path is in component */
export const STAGE_PATH_D = [
  'M 340 28',
  'H 660',
  'V 52',
  'H 580',
  'V 88',
  'H 420',
  'V 52',
  'H 340',
  'Z',
  'M 470 52',
  'H 530',
  'V 95',
  'H 470',
  'Z',
].join(' ');

export const STAGE_LABEL_CX = 500;
export const STAGE_LABEL_CY = 48;

/** U-bowl background — fuller ring closer to pitch */
export const BOWL_PATH_D = [
  'M 18 102',
  'Q 18 36 118 30',
  'H 882',
  'Q 982 36 982 102',
  'V 488',
  'Q 982 568 878 588',
  'H 122',
  'Q 18 568 18 488',
  'Z',
].join(' ');

export const PITCH_FLOOR_D = [
  'M 48 92',
  'H 952',
  'Q 960 92 960 102',
  'V 372',
  'Q 960 382 952 382',
  'H 48',
  'Q 40 382 40 372',
  'V 102',
  'Q 40 92 48 92',
  'Z',
].join(' ');
