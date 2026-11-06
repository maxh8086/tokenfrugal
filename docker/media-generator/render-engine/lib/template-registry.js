import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import Ajv2020 from 'ajv/dist/2020.js';
import { presets } from './job-schema.js';

export const GLOBAL_LIMITS = Object.freeze({
  titleMax: 80,
  bodyMax: 120,
  sceneCountMax: 200,
  sceneSecondsMax: 600,
});

export const KNOWN_PRESETS = Object.freeze(Object.keys(presets));

const ID_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;
const VERSION_RE = /^\d+\.\d+\.\d+$/;

function fail(message) {
  throw new Error(`template registry: ${message}`);
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

async function readJson(file, label) {
  let text;
  try {
    text = await readFile(file, 'utf8');
  } catch (err) {
    fail(`cannot read ${label} at ${file} (${err.code || err.message})`);
  }
  try {
    return JSON.parse(text);
  } catch (err) {
    fail(`${label} at ${file} is not valid JSON: ${err.message}`);
  }
}

export async function loadRegistry(rootDir) {
  if (typeof rootDir !== 'string' || rootDir === '') {
    fail('rootDir must be a non-empty string');
  }
  const root = path.resolve(rootDir);
  const templatesRoot = path.join(root, 'templates');
  const index = await readJson(path.join(templatesRoot, 'index.json'), 'templates/index.json');

  if (!isPlainObject(index) || index.version !== 1 || !Array.isArray(index.templates)) {
    fail('templates/index.json must be an object with version 1 and a templates array');
  }

  const ajv = new Ajv2020({ strict: true, allErrors: true });
  const seenIds = new Set();
  const templates = new Map();

  for (const entry of index.templates) {
    if (!isPlainObject(entry)) fail('templates/index.json entries must be objects');
    const { id, version, path: relPath } = entry;

    if (typeof id !== 'string' || !ID_RE.test(id)) {
      fail(`invalid template id ${JSON.stringify(id)} in templates/index.json`);
    }
    if (seenIds.has(id)) fail(`duplicate template id "${id}" in templates/index.json`);
    seenIds.add(id);

    if (typeof version !== 'string' || !VERSION_RE.test(version)) {
      fail(`template "${id}" has invalid version ${JSON.stringify(version)} in templates/index.json`);
    }
    if (typeof relPath !== 'string' || relPath === '') {
      fail(`template "${id}" has no path in templates/index.json`);
    }

    const manifestFile = path.resolve(root, relPath);
    const rel = path.relative(templatesRoot, manifestFile);
    if (
      rel === '' ||
      rel === '..' ||
      rel.startsWith(`..${path.sep}`) ||
      path.isAbsolute(rel)
    ) {
      fail(`template "${id}" path escapes templates/: ${relPath}`);
    }

    const manifest = await readJson(manifestFile, `manifest for "${id}"`);
    if (!isPlainObject(manifest)) fail(`manifest for "${id}" must be an object`);

    if (manifest.id !== id) {
      fail(`manifest id ${JSON.stringify(manifest.id)} does not match index id "${id}"`);
    }
    if (manifest.version !== version) {
      fail(`manifest version ${JSON.stringify(manifest.version)} does not match index version "${version}" for "${id}"`);
    }

    if (!Array.isArray(manifest.supported_presets) || manifest.supported_presets.length === 0) {
      fail(`template "${id}" must list at least one supported_presets entry`);
    }
    const seenPresets = new Set();
    for (const preset of manifest.supported_presets) {
      if (!KNOWN_PRESETS.includes(preset)) {
        fail(`template "${id}" lists unknown preset ${JSON.stringify(preset)}`);
      }
      if (seenPresets.has(preset)) {
        fail(`template "${id}" lists preset "${preset}" more than once`);
      }
      seenPresets.add(preset);
    }

    if (!isPlainObject(manifest.limits)) fail(`template "${id}" must have a limits object`);
    for (const [key, value] of Object.entries(manifest.limits)) {
      if (!Object.hasOwn(GLOBAL_LIMITS, key)) {
        fail(`template "${id}" sets unknown limit "${key}"`);
      }
      if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
        fail(`template "${id}" limit ${key} must be a positive number`);
      }
      if (value > GLOBAL_LIMITS[key]) {
        fail(`template "${id}" limit ${key}=${value} exceeds global limit ${GLOBAL_LIMITS[key]} (limits may only tighten)`);
      }
    }

    if (!isPlainObject(manifest.parameters)) {
      fail(`template "${id}" must have a parameters JSON Schema object`);
    }
    let validateFn;
    try {
      validateFn = ajv.compile(manifest.parameters);
    } catch (err) {
      fail(`parameter schema for "${id}" does not compile: ${err.message}`);
    }

    const composition = manifest.composition;
    if (
      typeof composition !== 'string' ||
      composition === '' ||
      composition === '.' ||
      composition === '..' ||
      composition.includes('/') ||
      composition.includes('\\')
    ) {
      fail(`template "${id}" composition must be a plain file name`);
    }
    const dir = path.dirname(manifestFile);
    let compStat = null;
    try {
      compStat = await stat(path.join(dir, composition));
    } catch {
      compStat = null;
    }
    if (!compStat || !compStat.isFile()) {
      fail(`composition file "${composition}" for "${id}" not found next to its manifest`);
    }

    templates.set(id, {
      manifest,
      dir,
      version,
      validate(params) {
        const valid = validateFn(params);
        return {
          valid: Boolean(valid),
          errors: valid
            ? []
            : validateFn.errors.map((e) => `${e.instancePath || '/'} ${e.message}`),
        };
      },
    });
  }

  return { templates };
}

export function resolveTemplate(registry, id, version) {
  const entry = registry?.templates?.get(id);
  if (!entry) throw new Error(`template registry: unknown template id "${id}"`);
  if (entry.version !== version) {
    throw new Error(
      `template registry: template "${id}" version ${version} is not available (registry has ${entry.version}); jobs must pin an exact version`,
    );
  }
  return entry;
}
