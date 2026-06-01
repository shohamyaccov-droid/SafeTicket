/**
 * Strict 1-to-1 section id remap — no spatial heuristics.
 * Each entry: current id → new id (paths unchanged).
 *
 * Run: node scripts/apply-exact-id-remap.mjs
 */
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const geoPath = path.join(__dirname, '../src/utils/ramatGanStadiumGeometry.generated.js');

/** @type {Record<string, string>} oldId → newId */
const EXACT_REMAP = {
  // Outer Ring (Left to Right)
  '6A': 'ACCESSIBLE',
  '6C': '6A',
  '6B': '6B',
  '9A': '6C',
  D14: '9A',
  ACCESSIBLE: '9B',
  B5: '11A',
  '16B': '11B',
  '11B': '13A',
  '13A': '13B',
  '13B': '13C',
  '13C': '16A',
  '16A': '16B',

  // Inner blocks
  D13: 'D14',
  '11A': 'B5',
  D12: 'D13',
  '16C': 'D12',
};

function labelForId(id) {
  if (id === 'ACCESSIBLE') return 'Accessible';
  if (id === 'STAGE') return 'Stage';
  return id;
}

/** Diamond path still labeled 11A => pre-remap file; B5 => already remapped. */
const PRE_REMAP_MARKER = { pathPrefix: 'M541.5 377.5', preRemapId: '11A' };

const src = readFileSync(geoPath, 'utf8');
const sectionRe = /\{\s*id:\s*'([^']+)',\s*label:\s*'([^']*)',\s*path:\s*'([^']+)',\s*status:\s*'([^']+)'\s*\}/g;

const sections = [];
let m;
while ((m = sectionRe.exec(src)) !== null) {
  const [, oldId, , pathD, status] = m;
  sections.push({ oldId, path: pathD, status });
}

const marker = sections.find((s) => s.path.startsWith(PRE_REMAP_MARKER.pathPrefix));
if (marker && marker.oldId !== PRE_REMAP_MARKER.preRemapId) {
  console.log(
    `Skip: geometry already has ${PRE_REMAP_MARKER.pathPrefix} as "${marker.oldId}" (expected pre-remap "${PRE_REMAP_MARKER.preRemapId}").`
  );
  console.log('Run verify-exact-id-remap.mjs to confirm.');
  process.exit(0);
}

const out = sections.map(({ oldId, path: pathD, status }) => {
  const newId = EXACT_REMAP[oldId] ?? oldId;
  return { id: newId, label: labelForId(newId), path: pathD, status };
});

let remapCount = 0;
for (let i = 0; i < sections.length; i++) {
  if (sections[i].oldId !== out[i].id) remapCount += 1;
}

const lines = [
  '/** Auto-generated from Untitled.svg — re-run: node scripts/parse-ramat-gan-svg.mjs */',
  `/** Section IDs: strict remap (scripts/apply-exact-id-remap.mjs) */`,
  "export const RAMAT_GAN_STADIUM_VIEWBOX = '0 0 1080 1080';",
  'export const RAMAT_GAN_STADIUM_SECTIONS_BASE = [',
  ...out.map(
    (s) =>
      `  { id: '${s.id}', label: '${s.label.replace(/'/g, "\\'")}', path: '${s.path}', status: '${s.status}' },`
  ),
  '];',
  '',
  'export const INTERACTIVE_STADIUM_SECTION_IDS = RAMAT_GAN_STADIUM_SECTIONS_BASE.filter((s) => s.id !== \'STAGE\').map((s) => s.id);',
  '',
];

writeFileSync(geoPath, lines.join('\n'), 'utf8');

console.log(`Remapped ${remapCount} section id(s) via EXACT_REMAP (${Object.keys(EXACT_REMAP).length} rules).`);
console.log('IDs after remap:', [...new Set(out.map((s) => s.id))].sort().join(', '));

const dupes = out.filter((s) => s.id !== 'STAGE').reduce((acc, s) => {
  acc[s.id] = (acc[s.id] || 0) + 1;
  return acc;
}, {});
for (const [id, n] of Object.entries(dupes)) {
  if (n > 1) console.warn(`Note: id "${id}" appears on ${n} paths (expected for split polygons).`);
}
