/**
 * Self-verification: EventDetailsPage wires InteractiveStadiumMap for Ramat Gan.
 * Run: node scripts/verify-event-details-ramat-gan.mjs (from frontend/)
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const eventPage = readFileSync(path.join(root, 'src/pages/EventDetailsPage.jsx'), 'utf8');
const listingUtil = readFileSync(path.join(root, 'src/utils/ramatGanStadiumListing.js'), 'utf8');

const geometry = readFileSync(path.join(root, 'src/utils/ramatGanStadiumGeometry.generated.js'), 'utf8');
const mapJsx = readFileSync(path.join(root, 'src/components/InteractiveStadiumMap.jsx'), 'utf8');

const checks = [
  ['imports InteractiveStadiumMap', /import InteractiveStadiumMap from/, eventPage],
  ['imports VENUE_RAMAT_GAN', /VENUE_RAMAT_GAN/, eventPage],
  ['isRamatGanVenue flag', /isRamatGanVenue/, eventPage],
  ['ramatGanActiveListingsSummary', /ramatGanActiveListingsSummary/, eventPage],
  ['onSelectSection handler', /handleRamatGanSectionSelect/, eventPage],
  ['renders InteractiveStadiumMap', /<InteractiveStadiumMap/, eventPage],
  ['venue_place in canonical venue', /venue_detail\?\.name/, eventPage],
  ['section filter banner', /ramat-gan-section-filter-banner/, eventPage],
  ['listing util exports', /buildRamatGanActiveListingsSummary/, listingUtil],
  ['geometry viewBox 1080', /0 0 1080 1080/, geometry],
  ['geometry STAGE path', /486\.5 316\.5H600\.5/, geometry],
  ['map imports traced geometry', /ramatGanStadiumGeometry/, mapJsx],
  ['34 sections in geometry', () => (geometry.match(/id: '/g) || []).length === 34],
];

let failed = 0;
for (const [label, re, src] of checks) {
  const ok = typeof re === 'function' ? re() : re.test(src);
  console.log(ok ? `OK  ${label}` : `FAIL ${label}`);
  if (!ok) failed += 1;
}

// Sample section normalization (inline, mirrors util)
const sample = 'גוש 11A';
const normalized = sample.replace(/^גוש\s*/i, '').trim().toUpperCase();
if (normalized !== '11A') {
  console.log(`FAIL section normalize expected 11A got ${normalized}`);
  failed += 1;
} else {
  console.log('OK  section normalize גוש 11A -> 11A');
}

if (failed) {
  console.error(`\nVERIFY FAILED (${failed} check(s))`);
  process.exit(1);
}
console.log('\nVERIFY: EventDetails Ramat Gan map integration PASSED');
