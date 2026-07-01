import { copyFileSync, existsSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(__dirname, '..');
const distDir = join(frontendRoot, 'dist');
const fileName = 'apple-developer-merchantid-domain-association';

const sourceCandidates = [
  join(frontendRoot, 'public', `${fileName}.txt`),
  join(frontendRoot, 'public', '.well-known', fileName),
  join(frontendRoot, '..', 'backend', '.well-known', fileName),
];

const sourcePath = sourceCandidates.find((candidate) => existsSync(candidate));
if (!sourcePath) {
  throw new Error('Apple Pay domain association file is missing from frontend public and backend/.well-known');
}

// Deploy only the .txt artifact. Render serves extensionless files as application/octet-stream;
// the render.yaml rewrite maps /.well-known/... to this .txt payload as text/plain.
copyFileSync(sourcePath, join(distDir, `${fileName}.txt`));
rmSync(join(distDir, '.well-known'), { recursive: true, force: true });

console.log(`Prepared Apple Pay domain association at ${join(distDir, `${fileName}.txt`)}`);
