// Writes a Markdown licence report for the render-engine npm dependencies.
// Licences are read from the `license` field of each package.json. This is not legal advice.
//
// Usage: node scripts/licence-report.js [output-path]   (default: ./LICENCE-REPORT.md)

import { readFile, readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export function buildReport(packages, generatedAt = new Date().toISOString()) {
  const rows = [...packages].sort((a, b) =>
    a.name < b.name ? -1 : a.name > b.name ? 1 : a.version < b.version ? -1 : a.version > b.version ? 1 : 0
  );
  const lines = [
    '# Licence report',
    '',
    `Generated: ${generatedAt}`,
    '',
    'Licences are read from the `license` field of each package.json. This report is not legal advice.',
    '',
    '| Package | Version | Licence |',
    '| --- | --- | --- |',
    ...rows.map((p) => `| ${p.name} | ${p.version} | ${p.license || 'UNKNOWN'} |`),
    '',
  ];
  return lines.join('\n');
}

function licenceOf(pkgJson) {
  const value = pkgJson && pkgJson.license;
  if (typeof value === 'string' && value.trim()) return value.trim();
  if (value && typeof value.type === 'string') return value.type;
  return 'UNKNOWN';
}

async function readPkgJson(dir) {
  try {
    return JSON.parse(await readFile(path.join(dir, 'package.json'), 'utf8'));
  } catch {
    return null;
  }
}

// Packages from package-lock.json (lockfile v2/v3 "packages" map). Licence comes from the installed package.json when present.
async function fromLockfile(lockPath) {
  const lock = JSON.parse(await readFile(lockPath, 'utf8'));
  const entries = Object.entries(lock.packages || {}).filter(([key]) => key.includes('node_modules/'));
  const result = [];
  for (const [key, meta] of entries) {
    const name = key.slice(key.lastIndexOf('node_modules/') + 'node_modules/'.length);
    const installed = await readPkgJson(path.join(ROOT, key));
    const license = installed ? licenceOf(installed) : licenceOf({ license: meta.license });
    result.push({ name, version: meta.version || installed?.version || 'UNKNOWN', license });
  }
  return result;
}

// Packages found by walking node_modules (used when no lockfile is present, e.g. inside the image).
async function fromNodeModules(nmDir) {
  const result = [];
  const visit = async (dir) => {
    const names = await readdir(dir, { withFileTypes: true });
    for (const entry of names) {
      if (!entry.isDirectory() && !entry.isSymbolicLink()) continue;
      if (entry.name.startsWith('.')) continue;
      const full = path.join(dir, entry.name);
      if (entry.name.startsWith('@')) {
        const scoped = await readdir(full, { withFileTypes: true });
        for (const s of scoped) {
          if (!s.isDirectory() && !s.isSymbolicLink()) continue;
          await addPackage(path.join(full, s.name));
        }
      } else {
        await addPackage(full);
      }
    }
  };
  const addPackage = async (dir) => {
    const pkg = await readPkgJson(dir);
    if (pkg && pkg.name) {
      result.push({ name: pkg.name, version: pkg.version || 'UNKNOWN', license: licenceOf(pkg) });
    }
    const nested = path.join(dir, 'node_modules');
    try {
      await visit(nested);
    } catch {
      // no nested node_modules
    }
  };
  await visit(nmDir);
  return result;
}

export async function collectPackages(root = ROOT) {
  const lockPath = path.join(root, 'package-lock.json');
  try {
    return await fromLockfile(lockPath);
  } catch (err) {
    if (err.code !== 'ENOENT') throw err;
  }
  return fromNodeModules(path.join(root, 'node_modules'));
}

async function main() {
  const outPath = path.resolve(process.argv[2] || 'LICENCE-REPORT.md');
  const packages = await collectPackages();
  await writeFile(outPath, buildReport(packages), 'utf8');
  console.log(`Wrote ${packages.length} rows to ${outPath}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((err) => {
    console.error(`licence-report: ${err.message}`);
    process.exit(1);
  });
}
