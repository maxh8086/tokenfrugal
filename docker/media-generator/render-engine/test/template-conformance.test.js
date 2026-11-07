// Conformance (D50, O10): every registered template against every preset.
// A template that claims a preset must be one the render engine can render today (lib/job-output.js
// JOB_PRESETS), must pass its default parameters, and must ship a full HTML composition.
// Pairs the template does not claim are reported as skipped.
// The HyperFrames smoke render (2-second clip per pair) is not part of this file; it needs the
// HyperFrames CLI and ffmpeg, so it runs in the image, not in the offline unit tests.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadRegistry, GLOBAL_LIMITS, KNOWN_PRESETS } from '../lib/template-registry.js';
import { JOB_PRESETS } from '../lib/job-output.js';
import { LIMITS, SCENE_LIMITS } from '../lib/props.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const registry = await loadRegistry(root);

// The limits the render engine enforces on every job (lib/props.js). A manifest may declare tighter limits, never looser.
const ENGINE_LIMITS = {
  titleMax: LIMITS.titleMax,
  bodyMax: SCENE_LIMITS.subMax,
  sceneCountMax: SCENE_LIMITS.countMax,
  sceneSecondsMax: SCENE_LIMITS.secondsMax,
};

test('at least one registered template can render each preset the engine renders', () => {
  for (const preset of JOB_PRESETS) {
    const claimed = [...registry.templates.values()].some((t) => t.manifest.supported_presets.includes(preset));
    assert.ok(claimed, `no template supports ${preset}`);
  }
});

for (const [id, entry] of registry.templates) {
  for (const preset of KNOWN_PRESETS) {
    const claims = entry.manifest.supported_presets.includes(preset);
    test(`${id} ${entry.version} x ${preset}`, { skip: claims ? false : `${id} does not claim ${preset}` }, async () => {
      assert.ok(JOB_PRESETS.includes(preset), `${id} claims ${preset}, which the render engine cannot render yet`);

      const defaults = entry.validate({});
      assert.deepEqual(defaults, { valid: true, errors: [] }, 'default parameters must validate');

      for (const [key, value] of Object.entries(entry.manifest.limits)) {
        assert.ok(value <= GLOBAL_LIMITS[key], `${key}=${value} is looser than the global limit`);
        assert.ok(value <= ENGINE_LIMITS[key], `${key}=${value} is looser than the engine limit ${ENGINE_LIMITS[key]}`);
      }

      const html = await readFile(path.join(entry.dir, entry.manifest.composition), 'utf8');
      assert.match(html, /<!doctype html>/i, 'composition must start with a doctype');
      assert.match(html, /<html[\s>]/i, 'composition must have an html element');
    });
  }
}
