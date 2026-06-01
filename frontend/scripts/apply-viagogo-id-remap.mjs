/**
 * Remap section IDs to Viagogo layout by path signature (paths unchanged).
 * Bottom row locked. Run: node scripts/apply-viagogo-id-remap.mjs
 */
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const geoPath = path.join(__dirname, '../src/utils/ramatGanStadiumGeometry.generated.js');

/** path moveto prefix -> Viagogo section id (bijection on traced SVG) */
const PATH_TO_ID = {
  'M486.5 316.5': 'STAGE',
  'M119 375.5': '6C',
  'M212.5 234': '6B',
  'M103 525': '6A',
  'M215 222': '9A',
  'M293 190.5': 'D14',
  'M387 187.5': 'ACCESSIBLE',
  'M350 310.5': 'B4',
  'M479.5 255.5': 'B5',
  'M686 188.5': '16B',
  'M689 253.5': '11B',
  'M541.5 377.5': '11A',
  'M811 273': '13A',
  'M816.5 277': '13B',
  'M895.5 355': '13B',
  'M970 395': '16A',
  'M948.5 310.5': '13C',
  'M323.5 330': 'A3',
  'M414.5 470.5': 'A2',
  'M258.5 540.5': 'A1',
  'M665.526 406': 'B6',
  'M745 326.5': 'C7',
  'M825.5 473.5': 'C8',
  'M767.809 572': 'C9',
  'M351 600.5': 'D13',
  'M435 601': 'D12',
  'M589.5 529.5': 'D11',
  'M753 603.5': 'D10',
  'M543.5 552.5': '16C',
  'M321.502 752.5': '4',
  'M451.5 781.5': '3',
  'M463 774.948': '2-3',
  'M643 776.5': '2',
  'M754.733 767': '1',
};

function pathKey(pathD) {
  const m = pathD.match(/^M[^MLHVCSQTAZ]+/);
  return m ? m[0].trim() : pathD.slice(0, 20);
}

function parseGeo(src) {
  const re = /id: '([^']+)'[^}]+path: '([^']+)'[^}]+status: '([^']+)'/g;
  const sections = [];
  let m;
  while ((m = re.exec(src))) {
    sections.push({ id: m[1], path: m[2], status: m[3] });
  }
  return sections;
}

function labelFor(id) {
  if (id === 'ACCESSIBLE') return 'Accessible';
  if (id === 'STAGE') return 'Stage';
  return id;
}

const geoSrc = readFileSync(geoPath, 'utf8');
const sections = parseGeo(geoSrc);

const remapped = [];
for (const s of sections) {
  const key = pathKey(s.path);
  const newId = PATH_TO_ID[key];
  if (!newId) {
    console.error('No mapping for', key, 'was', s.id);
    process.exit(1);
  }
  if (s.id !== newId) console.log(`  ${s.id} -> ${newId}  (${key})`);
  remapped.push({
    id: newId,
    label: labelFor(newId),
    path: s.path,
    status: newId === 'STAGE' ? 'stage' : s.status === 'stage' ? 'stage' : 'unavailable',
  });
}

const ids = remapped.map((s) => s.id);
const dup = ids.filter((id, i) => ids.indexOf(id) !== i);
if (dup.length) {
  console.warn('Note: duplicate section ids (adjacent SVG subpaths):', [...new Set(dup)]);
}

const ORDER = [
  '6C', '9A', '11A', '11B', '13A', '13B', '6B', '6A', '13C', '16A', '16B', '16C',
  'A3', 'A2', 'A1', 'B4', 'B5', 'B6', 'C7', 'C8', 'C9', 'D14', 'D13', 'D12', 'D11', 'D10',
  'ACCESSIBLE', 'STAGE', '4', '3', '2-3', '2', '1',
];
remapped.sort((a, b) => ORDER.indexOf(a.id) - ORDER.indexOf(b.id));

const lines = [
  '/** Auto-generated from Untitled.svg — re-run: node scripts/parse-ramat-gan-svg.mjs */',
  '/** Section IDs remapped to Viagogo layout (scripts/apply-viagogo-id-remap.mjs) */',
  `export const RAMAT_GAN_STADIUM_VIEWBOX = '0 0 1080 1080';`,
  'export const RAMAT_GAN_STADIUM_SECTIONS_BASE = [',
];
for (const s of remapped) {
  const escaped = s.path.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
  lines.push(`  { id: '${s.id}', label: '${s.label}', path: '${escaped}', status: '${s.status}' },`);
}
lines.push('];', '');
lines.push(
  "export const INTERACTIVE_STADIUM_SECTION_IDS = RAMAT_GAN_STADIUM_SECTIONS_BASE.filter((s) => s.id !== 'STAGE').map((s) => s.id);"
);
writeFileSync(geoPath, lines.join('\n'), 'utf8');
console.log('\nWrote', geoPath);
