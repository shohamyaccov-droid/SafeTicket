import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(__dirname, '..');
const distDir = join(frontendRoot, 'dist');
const fileName = 'apple-developer-merchantid-domain-association';

const sourceCandidates = [
  join(frontendRoot, 'public', '.well-known', fileName),
  join(frontendRoot, 'public', `${fileName}.txt`),
  join(frontendRoot, '..', 'backend', '.well-known', fileName),
];

const sourcePath = sourceCandidates.find((candidate) => existsSync(candidate));
if (!sourcePath) {
  throw new Error('Apple Pay domain association file is missing from public/.well-known and backend/.well-known');
}

mkdirSync(join(distDir, '.well-known'), { recursive: true });
copyFileSync(sourcePath, join(distDir, '.well-known', fileName));
copyFileSync(sourcePath, join(distDir, `${fileName}.txt`));

console.log(`Copied Apple Pay domain association file into ${distDir}`);
