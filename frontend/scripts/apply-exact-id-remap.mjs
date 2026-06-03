/**
 * Absolute path-prefix → section id mapping (Viagogo reference).
 * No spatial guessing — each SVG path is identified by its moveto prefix.
 *
 * Run: node scripts/apply-exact-id-remap.mjs
 */
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const geoPath = path.join(__dirname, '../src/utils/ramatGanStadiumGeometry.generated.js');

/** path moveto prefix → canonical section id */
const PATH_PREFIX_TO_ID = {
  // Left / top outer ring
  'M119 375.5': '6A',
  'M215 222': '6C',
  'M212.5 234': '6B',
  'M103 525': 'ACCESSIBLE',
  'M293 190.5': '9A',
  'M387 187.5': '9B',
  'M479.5 255.5': '11A',
  'M686 188.5': '11B',
  'M689 253.5': '13A',
  'M811 273': '13B',
  // Top-right corner wedge + far-right outer edge (top → bottom)
  'M816.5 277': '13C',
  'M895.5 355': '16A',
  'M948.5 310.5': '16B',
  'M970 395': '16C',
  // Inner blocks
  'M323.5 330': 'A3',
  'M414.5 470.5': 'A2',
  'M258.5 540.5': 'A1',
  'M350 310.5': 'B4',
  'M541.5 377.5': 'B5',
  'M665.526 406': 'B6',
  'M745 326.5': 'C7',
  'M825.5 473.5': 'C8',
  'M767.809 572': 'C9',
  'M351 600.5': 'D14',
  'M435 601': 'D13',
  'M543.5 552.5': 'D12',
  'M589.5 529.5': 'D11',
  'M753 603.5': 'D10',
  'M486.5 316.5': 'STAGE',
  // Bottom grandstand (left → right)
  'M321.502 752.5': '4',
  'M451.5 781.5': '3',
  'M463 774.948': '2-3',
  'M643 776.5': '2',
  'M754.733 767': '1',
};

function labelForId(id) {
  if (id === 'ACCESSIBLE') return 'Accessible';
  if (id === 'STAGE') return 'Stage';
  return id;
}

const src = readFileSync(geoPath, 'utf8');
const sectionRe = /\{\s*id:\s*'([^']+)',\s*label:\s*'([^']*)',\s*path:\s*'([^']+)',\s*status:\s*'([^']+)'\s*\}/g;

const sections = [];
let m;
while ((m = sectionRe.exec(src)) !== null) {
  const [, , , pathD, status] = m;
  sections.push({ path: pathD, status });
}

const out = sections.map(({ path: pathD, status }) => {
  const key = Object.keys(PATH_PREFIX_TO_ID).find((k) => pathD.startsWith(k));
  if (!key) {
    console.error('No PATH_PREFIX_TO_ID for path starting:', pathD.slice(0, 24));
    process.exit(1);
  }
  const id = PATH_PREFIX_TO_ID[key];
  return { id, label: labelForId(id), path: pathD, status };
});

let changed = 0;
let prevId;
const prevRe = /\{\s*id:\s*'([^']+)'/g;
const prevIds = [];
while ((m = prevRe.exec(src)) !== null) prevIds.push(m[1]);
for (let i = 0; i < out.length; i++) {
  if (prevIds[i] !== out[i].id) changed += 1;
}

const lines = [
  '/** Auto-generated from Untitled.svg — re-run: node scripts/parse-ramat-gan-svg.mjs */',
  '/** Section IDs: absolute path-prefix map (scripts/apply-exact-id-remap.mjs) */',
  "export const RAMAT_GAN_STADIUM_VIEWBOX = '0 0 1080 1080';",
  'export const RAMAT_GAN_STADIUM_SECTIONS_BASE = [',
  ...out.map(
    (s) =>
      `  { id: '${s.id}', label: '${s.label.replace(/'/g, "\\'")}', path: '${s.path}', status: '${s.status}' },`
  ),
  '];',
  '',
  "export const INTERACTIVE_STADIUM_SECTION_IDS = RAMAT_GAN_STADIUM_SECTIONS_BASE.filter((s) => s.id !== 'STAGE').map((s) => s.id);",
  '',
];

writeFileSync(geoPath, lines.join('\n'), 'utf8');

console.log(`Applied path-prefix IDs (${changed} section(s) changed).`);
console.log('IDs:', [...new Set(out.map((s) => s.id))].sort().join(', '));
