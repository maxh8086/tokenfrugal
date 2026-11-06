import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkTemplateLimits, loadRegistry, resolveTemplate } from '../lib/template-registry.js';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const created = [];

after(async () => {
  for (const dir of created) {
    await rm(dir, { recursive: true, force: true });
  }
});

function validManifest(overrides = {}) {
  return {
    id: 'tmp-scene',
    version: '1.0.0',
    description: 'Temporary test template.',
    composition: 'composition.html',
    supported_presets: ['youtube'],
    limits: { titleMax: 80 },
    parameters: {
      $schema: 'https://json-schema.org/draft/2020-12/schema',
      type: 'object',
      additionalProperties: false,
      properties: { background: { type: 'string', pattern: '^#[0-9a-fA-F]{6}$' } },
      required: [],
    },
    ...overrides,
  };
}

function baseFiles(manifestOverrides = {}) {
  return {
    'templates/index.json': {
      version: 1,
      templates: [{ id: 'tmp-scene', version: '1.0.0', path: 'templates/tmp-scene/manifest.json' }],
    },
    'templates/tmp-scene/manifest.json': validManifest(manifestOverrides),
    'templates/tmp-scene/composition.html': '<!doctype html><html><head><meta charset="utf-8"></head><body><!-- test --></body></html>\n',
  };
}

async function makeRoot(files) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'tpl-reg-'));
  created.push(root);
  for (const [rel, content] of Object.entries(files)) {
    const file = path.join(root, rel);
    await mkdir(path.dirname(file), { recursive: true });
    await writeFile(file, typeof content === 'string' ? content : JSON.stringify(content, null, 2));
  }
  return root;
}

test('real registry loads and contains plain-scene 1.0.0', async () => {
  const registry = await loadRegistry(repoRoot);
  assert.ok(registry.templates instanceof Map);
  const entry = registry.templates.get('plain-scene');
  assert.ok(entry, 'plain-scene missing');
  assert.equal(entry.version, '1.0.0');
  assert.equal(entry.manifest.id, 'plain-scene');
});

test('resolveTemplate returns the entry for the pinned version', async () => {
  const registry = await loadRegistry(repoRoot);
  const entry = resolveTemplate(registry, 'plain-scene', '1.0.0');
  assert.equal(entry.version, '1.0.0');
});

test('resolveTemplate throws on a version mismatch', async () => {
  const registry = await loadRegistry(repoRoot);
  assert.throws(() => resolveTemplate(registry, 'plain-scene', '2.0.0'), /version 2\.0\.0/);
});

test('resolveTemplate throws on an unknown id', async () => {
  const registry = await loadRegistry(repoRoot);
  assert.throws(() => resolveTemplate(registry, 'no-such-template', '1.0.0'), /unknown template id/);
});

test('valid parameters pass validation', async () => {
  const registry = await loadRegistry(repoRoot);
  const { validate } = resolveTemplate(registry, 'plain-scene', '1.0.0');
  assert.deepEqual(validate({ background: '#112233', accent: '#ABCDEF' }), { valid: true, errors: [] });
  assert.equal(validate({}).valid, true);
});

test('parameters with an unknown key fail validation', async () => {
  const registry = await loadRegistry(repoRoot);
  const { validate } = resolveTemplate(registry, 'plain-scene', '1.0.0');
  const result = validate({ font: 'serif' });
  assert.equal(result.valid, false);
  assert.ok(result.errors.length > 0);
});

test('a bad colour fails validation with the field path', async () => {
  const registry = await loadRegistry(repoRoot);
  const { validate } = resolveTemplate(registry, 'plain-scene', '1.0.0');
  const result = validate({ background: 'red' });
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.startsWith('/background ')), result.errors.join('; '));
});

test('a temp-dir template with valid content loads (control)', async () => {
  const root = await makeRoot(baseFiles());
  const registry = await loadRegistry(root);
  assert.equal(resolveTemplate(registry, 'tmp-scene', '1.0.0').version, '1.0.0');
});

test('a manifest with limits above the global limit is rejected', async () => {
  const root = await makeRoot(baseFiles({ limits: { titleMax: 200 } }));
  await assert.rejects(loadRegistry(root), /titleMax/);
});

test('a manifest with a non-compiling parameter schema is rejected', async () => {
  const root = await makeRoot(baseFiles({ parameters: { type: 'nonsense' } }));
  await assert.rejects(loadRegistry(root), /does not compile/);
});

test('a manifest whose composition file is missing is rejected', async () => {
  const files = baseFiles();
  delete files['templates/tmp-scene/composition.html'];
  const root = await makeRoot(files);
  await assert.rejects(loadRegistry(root), /composition file/);
});

test('a path escape in the index is rejected', async () => {
  const files = baseFiles();
  files['templates/index.json'].templates[0].path = 'templates/../../outside/manifest.json';
  const root = await makeRoot(files);
  await assert.rejects(loadRegistry(root), /escapes/);
});

test('duplicate template ids are rejected', async () => {
  const files = baseFiles();
  files['templates/index.json'].templates.push({
    id: 'tmp-scene',
    version: '1.0.0',
    path: 'templates/tmp-scene/manifest.json',
  });
  const root = await makeRoot(files);
  await assert.rejects(loadRegistry(root), /duplicate template id/);
});

test('checkTemplateLimits passes limits that tighten the global limits', () => {
  assert.deepEqual(checkTemplateLimits({ titleMax: 60, bodyMax: 100, sceneCountMax: 50, sceneSecondsMax: 300 }), []);
  assert.deepEqual(checkTemplateLimits({ titleMax: 80 }), []);
});

test('checkTemplateLimits fails a looser limit and names the key', () => {
  const errors = checkTemplateLimits({ titleMax: 200 });
  assert.equal(errors.length, 1);
  assert.match(errors[0], /titleMax/);
  assert.match(errors[0], /exceeds global limit 80/);
});

test('checkTemplateLimits fails an unknown key and names it', () => {
  const errors = checkTemplateLimits({ fooMax: 10 });
  assert.equal(errors.length, 1);
  assert.match(errors[0], /"fooMax"/);
});

test('checkTemplateLimits fails negative and non-numeric values and names the key', () => {
  const negative = checkTemplateLimits({ bodyMax: -1 });
  assert.equal(negative.length, 1);
  assert.match(negative[0], /bodyMax must be a positive number/);
  const text = checkTemplateLimits({ sceneSecondsMax: '300' });
  assert.equal(text.length, 1);
  assert.match(text[0], /sceneSecondsMax must be a positive number/);
});

test('checkTemplateLimits passes when limits are absent or empty', () => {
  assert.deepEqual(checkTemplateLimits(undefined), []);
  assert.deepEqual(checkTemplateLimits({}), []);
});
