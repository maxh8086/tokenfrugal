// Optional `template` field on POST /render (D50, handoff item 1). Pure checks against the real registry.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadRegistry } from '../lib/template-registry.js';
import { parseRenderTemplate } from '../lib/render-template.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const registry = await loadRegistry(root);

test('no template field keeps the default composition', () => {
  const r = parseRenderTemplate(undefined, registry, 'youtube');
  assert.equal(r.ok, true);
  assert.equal(r.entry, null);
});

test('a valid pinned template resolves to its registry entry', () => {
  const r = parseRenderTemplate({ id: 'plain-scene', version: '1.0.0', parameters: { background: '#101010' } }, registry, 'youtube');
  assert.equal(r.ok, true);
  assert.equal(r.entry.manifest.id, 'plain-scene');
  assert.match(r.entry.dir, /templates[\/]plain-scene$/);
});

test('rejects a non-object template', () => {
  assert.equal(parseRenderTemplate('plain-scene', registry, 'youtube').ok, false);
  assert.equal(parseRenderTemplate([], registry, 'youtube').ok, false);
});

test('rejects a bad id or a non-exact version', () => {
  assert.equal(parseRenderTemplate({ id: 'Plain Scene', version: '1.0.0' }, registry, 'youtube').ok, false);
  assert.equal(parseRenderTemplate({ id: 'plain-scene', version: '1.0' }, registry, 'youtube').ok, false);
});

test('rejects an unknown id and a version the registry does not hold', () => {
  const unknown = parseRenderTemplate({ id: 'nope', version: '1.0.0' }, registry, 'youtube');
  assert.equal(unknown.ok, false);
  assert.match(unknown.error, /unknown template id/);
  const wrong = parseRenderTemplate({ id: 'plain-scene', version: '2.0.0' }, registry, 'youtube');
  assert.equal(wrong.ok, false);
  assert.match(wrong.error, /version 2.0.0/);
});

test('rejects a preset the template does not claim', () => {
  const r = parseRenderTemplate({ id: 'plain-scene', version: '1.0.0' }, registry, 'shorts');
  assert.equal(r.ok, false);
  assert.match(r.error, /does not support preset shorts/);
});

test('rejects parameters that fail the manifest schema', () => {
  const r = parseRenderTemplate({ id: 'plain-scene', version: '1.0.0', parameters: { background: 'red' } }, registry, 'youtube');
  assert.equal(r.ok, false);
  assert.match(r.error, /template parameters invalid/);
});
