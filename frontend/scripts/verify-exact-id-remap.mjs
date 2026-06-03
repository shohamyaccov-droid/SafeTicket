/**
 * Verify final ids by path signature (moveto prefix) — not spatial guessing.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const geo = readFileSync(
  path.join(__dirname, '../src/utils/ramatGanStadiumGeometry.generated.js'),
  'utf8'
);

/** path moveto prefix → expected id */
const EXPECTED_BY_PATH_PREFIX = {
  'M119 375.5': '6A',
  'M215 222': '6C',
  'M486.5 316.5': 'B5',
  'M541.5 377.5': 'STAGE',
  'M689 253.5': '13A',
  'M811 273': '13B',
  'M816.5 277': '13C',
  'M895.5 355': '16A',
  'M948.5 310.5': '16B',
  'M970 395': '16C',
  'M212.5 234': '6B',
  'M103 525': 'ACCESSIBLE',
  'M686 188.5': '11B',
  'M543.5 552.5': 'D12',
  'M479.5 255.5': '11A',
  'M665.526 406': 'B6',
  'M745 326.5': 'C7',
  'M825.5 473.5': 'C8',
  'M767.809 572': 'C9',
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
  const key = Object.keys(EXPECTED_BY_PATH_PREFIX).find((k) => pathD.startsWith(k));
  if (!key) continue;
  const expected = EXPECTED_BY_PATH_PREFIX[key];
  if (id !== expected) {
    console.log('FAIL', key, 'got', id, 'expected', expected);
    failed += 1;
  }
}

// Right-side layout checks
const rightSideChecks = [
  { prefix: 'M816.5 277', expected: '13C', note: 'top-right corner wedge' },
  { prefix: 'M895.5 355', expected: '16A', note: 'below 13C' },
  { prefix: 'M948.5 310.5', expected: '16B', note: 'below 16A' },
  { prefix: 'M970 395', expected: '16C', note: 'bottom-right outer edge' },
  { prefix: 'M486.5 316.5', expected: 'B5', note: 'U-shaped top center' },
  { prefix: 'M541.5 377.5', expected: 'STAGE', note: 'center diamond stage' },
];

for (const check of rightSideChecks) {
  const re = new RegExp(`id:\\s*'([^']+)'[^}]+path:\\s*'${check.prefix.replace('.', '\\.')}`);
  const match = geo.match(re);
  if (!match) {
    console.log('FAIL missing path', check.prefix);
    failed += 1;
  } else if (match[1] !== check.expected) {
    console.log('FAIL', check.note, check.prefix, 'got', match[1], 'expected', check.expected);
    failed += 1;
  } else {
    console.log('OK', check.expected, '—', check.note);
  }
}

if (failed) {
  console.error(`\n${failed} path(s) mismatch — run: node scripts/apply-exact-id-remap.mjs`);
  process.exit(1);
}
console.log('\nVERIFY: exact path-prefix ID mapping OK');
