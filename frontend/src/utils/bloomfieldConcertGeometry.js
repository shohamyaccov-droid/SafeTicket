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

/** Row A (6): A6…A1 — maximized to fill inner pitch; tight gaps; geometry centered in view */
const GAP_H = 1;
const GAP_V = 2;
const CELL_W = 129;
const ROW_H_AB = 94;
const ROW_H_C = 92;
const ROW_A_W = 6 * CELL_W + 5 * GAP_H;
const ROW_A_START_X = VIEW_W / 2 - ROW_A_W / 2;
const ROW_BC_START_X = ROW_A_START_X + (CELL_W + GAP_H) / 2;
const ROW_A_Y = 98;

/** @type {ConcertBlockRect[]} */
export const CONCERT_BLOCKS = [
  ...[6, 5, 4, 3, 2, 1].map((n, i) =>
    rect(`A${n}`, 'pitch', ROW_A_START_X + i * (CELL_W + GAP_H), ROW_A_Y, CELL_W, ROW_H_AB, `A${n}`)
  ),
  ...[5, 4, 3, 2, 1].map((n, i) =>
    rect(
      `B${n}`,
      'pitch',
      ROW_BC_START_X + i * (CELL_W + GAP_H),
      ROW_A_Y + ROW_H_AB + GAP_V,
      CELL_W,
      ROW_H_AB,
      `B${n}`
    )
  ),
  ...[5, 4, 3, 2, 1].map((n, i) =>
    rect(
      `C${n}`,
      'pitch',
      ROW_BC_START_X + i * (CELL_W + GAP_H),
      ROW_A_Y + ROW_H_AB + GAP_V + ROW_H_AB + GAP_V,
      CELL_W,
      ROW_H_C,
      `C${n}`
    )
  ),
];

const WEST_X = 34;
const WEST_W = 76;
const WEST_TOP = 108;
const WEST_H = 54;
const WEST_GAP = 2;
/** West stand: 106 top → 101 bottom */
for (let n = 106, i = 0; n >= 101; n -= 1, i += 1) {
  CONCERT_BLOCKS.push(rect(String(n), 'west', WEST_X, WEST_TOP + i * (WEST_H + WEST_GAP), WEST_W, WEST_H, String(n)));
}

const EAST_X = VIEW_W - WEST_X - WEST_W;
/** East: 42 top → 47 bottom */
for (let n = 42, i = 0; n <= 47; n += 1, i += 1) {
  CONCERT_BLOCKS.push(rect(String(n), 'east', EAST_X, WEST_TOP + i * (WEST_H + WEST_GAP), WEST_W, WEST_H, String(n)));
}

/** South inner row 80A … 70A (11 blocks) */
const SOUTH_INNER_Y = 392;
const SOUTH_CELL_W = 58;
const SOUTH_GAP = 2;
const SOUTH_ROW_W = 11 * SOUTH_CELL_W + 10 * SOUTH_GAP;
const SOUTH_START_X = (VIEW_W - SOUTH_ROW_W) / 2;
const SOUTH_INNER_H = 46;
for (let i = 0; i <= 10; i += 1) {
  const num = 80 - i;
  const id = `${num}A`;
  CONCERT_BLOCKS.push(
    rect(id, 'south', SOUTH_START_X + i * (SOUTH_CELL_W + SOUTH_GAP), SOUTH_INNER_Y, SOUTH_CELL_W, SOUTH_INNER_H, id)
  );
}

/** South outer 80B … 71B */
const SOUTH_OUTER_H = 44;
const SOUTH_OUTER_Y = SOUTH_INNER_Y + SOUTH_INNER_H + SOUTH_GAP;
for (let i = 0; i <= 9; i += 1) {
  const num = 80 - i;
  const id = `${num}B`;
  const rowW = 10 * SOUTH_CELL_W + 9 * SOUTH_GAP;
  const startX = (VIEW_W - rowW) / 2 + SOUTH_CELL_W * 0.55;
  CONCERT_BLOCKS.push(
    rect(id, 'south', startX + i * (SOUTH_CELL_W + SOUTH_GAP), SOUTH_OUTER_Y, SOUTH_CELL_W, SOUTH_OUTER_H, id)
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
  'M 106 88',
  'H 894',
  'Q 902 88 902 98',
  'V 388',
  'Q 902 398 894 398',
  'H 106',
  'Q 98 398 98 388',
  'V 98',
  'Q 98 88 106 88',
  'Z',
].join(' ');
