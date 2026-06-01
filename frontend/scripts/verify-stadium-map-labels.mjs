/**
 * Self-verification: section label placement uses path bbox center.
 * Run: node scripts/verify-stadium-map-labels.mjs
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const geometryPath = path.join(root, 'src/utils/ramatGanStadiumGeometry.generated.js');

// Dynamic import of exported helper via vite-less eval — duplicate minimal parser check
const geometry = readFileSync(geometryPath, 'utf8');
const stageMatch = geometry.match(/id: 'STAGE'[^}]+path: '([^']+)'/);
if (!stageMatch) {
  console.error('FAIL: STAGE path not found');
  process.exit(1);
}

const stagePath = stageMatch[1];
const nums = stagePath.match(/-?\d+(\.\d+)?/g)?.map(Number) ?? [];
let minX = Infinity,
  maxX = -Infinity,
  minY = Infinity,
  maxY = -Infinity;
for (let i = 0; i + 1 < nums.length; i += 2) {
  minX = Math.min(minX, nums[i]);
  maxX = Math.max(maxX, nums[i]);
  minY = Math.min(minY, nums[i + 1]);
  maxY = Math.max(maxY, nums[i + 1]);
}
const cx = (minX + maxX) / 2;
const cy = (minY + maxY) / 2;

console.log('STAGE bbox center (approx):', { cx: cx.toFixed(1), cy: cy.toFixed(1) });
if (cx < 400 || cx > 700 || cy < 250 || cy > 450) {
  console.error('FAIL: STAGE center outside expected top-center region');
  process.exit(1);
}

const mapSrc = readFileSync(path.join(root, 'src/components/InteractiveStadiumMap.jsx'), 'utf8');
const checks = [
  ['#ea580c available fill', /available: '#ea580c'/],
  ['#c2410c hover fill', /availableHover: '#c2410c'/],
  ['#9a3412 selected fill', /selected: '#9a3412'/],
  ['BOTTOM_GRANDSTAND_LABEL_COORDS', /BOTTOM_GRANDSTAND_LABEL_COORDS/],
  ['grandstand 2 bbox center', /'2':\s*\{\s*x:\s*545,\s*y:\s*805\s*\}/],
  ['grandstand D10 bbox center', /D10:\s*\{\s*x:\s*841,\s*y:\s*768\s*\}/],
  ['render uses grandstandCoords', /grandstandCoords[\s\S]*?\? grandstandCoords\.x/],
  ['labels use translate()', /transform=\{`translate\(\$\{labelX\}, \$\{labelY\}\)`\}/],
  ['middle text baseline', /dominantBaseline="middle"/],
  ['labels layer', /interactive-stadium-map__labels-layer/],
  ['resolveLabelCoordinates', /resolveLabelCoordinates/],
  ['no shoelace centroid', () => !/polygonCentroid/.test(mapSrc)],
  ['stage slate fill', /stage: '#334155'/],
  ['stage grey stroke', /stageStroke: '#94a3b8'/],
  ['section-id-label class', /interactive-stadium-map__section-id-label/],
  ['pointerEvents none on labels', /pointerEvents="none"/],
];

let failed = 0;
for (const [label, re] of checks) {
  const ok = typeof re === 'function' ? re() : re.test(mapSrc);
  console.log(ok ? `OK  ${label}` : `FAIL ${label}`);
  if (!ok) failed += 1;
}

if (failed) {
  console.error(`VERIFY FAILED (${failed})`);
  process.exit(1);
}
console.log('VERIFY: stadium map labels & styling PASSED');
