/**
 * Verify final ids by path signature (moveto prefix) — not spatial guessing.
 * Signatures are the post-remap targets from apply-exact-id-remap.mjs.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const geo = readFileSync(
  path.join(__dirname, '../src/utils/ramatGanStadiumGeometry.generated.js'),
  'utf8'
);

/** path moveto prefix → expected id after manual EXACT_REMAP */
const EXPECTED_BY_PATH_PREFIX = {
  'M119 375.5': '6A',
  'M215 222': '6C',
  'M541.5 377.5': 'B5',
  'M689 253.5': '13A',
  'M811 273': '13B',
  'M816.5 277': '13C',
  'M895.5 355': '13C',
  'M212.5 234': '6B',
  'M103 525': 'ACCESSIBLE',
  'M948.5 310.5': '16A',
  'M970 395': '16B',
  'M686 188.5': '11B',
  'M543.5 552.5': 'D12',
  'M479.5 255.5': '11A',
  'M293 190.5': '9A',
  'M351 600.5': 'D14',
  'M435 601': 'D13',
  'M387 187.5': '9B',
  'M321.502 752.5': '4',
  'M451.5 781.5': '3',
  'M463 774.948': '2-3',
  'M643 776.5': '2',
  'M754.733 767': '1',
};

const sectionRe = /\{\s*id:\s*'([^']+)',\s*label:\s*'[^']*',\s*path:\s*'([^']+)'/g;
let failed = 0;
let m;
while ((m = sectionRe.exec(geo)) !== null) {
  const [, id, pathD] = m;
  const prefix = pathD.slice(0, 12);
  const key = Object.keys(EXPECTED_BY_PATH_PREFIX).find((k) => pathD.startsWith(k));
  if (!key) continue;
  const expected = EXPECTED_BY_PATH_PREFIX[key];
  if (id !== expected) {
    console.log('FAIL', key, 'got', id, 'expected', expected);
    failed += 1;
  }
}

if (failed) {
  console.error(`\n${failed} path(s) mismatch — run: node scripts/apply-exact-id-remap.mjs`);
  process.exit(1);
}
console.log('VERIFY: exact manual remap path signatures OK');
