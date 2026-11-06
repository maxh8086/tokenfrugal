// Optional `template` field on POST /render (opt-in, D50 / handoff item 1).
// With no field, /render keeps composition/index.html. With a field, the template must be in the
// registry at the exact pinned version, must list the preset the render uses, and its parameters
// must pass its own JSON Schema. Parameters are validated here; the composition does not read them yet.

import { resolveTemplate } from './template-registry.js';

const ID_SHAPE = /^[a-z0-9][a-z0-9-]{0,63}$/;
const VERSION_SHAPE = /^\d+\.\d+\.\d+$/;

export function parseRenderTemplate(raw, registry, preset) {
  if (raw === undefined) return { ok: true, entry: null, parameters: {} };
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return { ok: false, error: 'template must be an object with id and version' };
  }
  const { id, version, parameters = {} } = raw;
  if (typeof id !== 'string' || !ID_SHAPE.test(id)) {
    return { ok: false, error: 'template.id must be a lowercase id' };
  }
  if (typeof version !== 'string' || !VERSION_SHAPE.test(version)) {
    return { ok: false, error: 'template.version must be an exact semantic version such as 1.0.0' };
  }
  if (parameters === null || typeof parameters !== 'object' || Array.isArray(parameters)) {
    return { ok: false, error: 'template.parameters must be an object' };
  }
  let entry;
  try {
    entry = resolveTemplate(registry, id, version);
  } catch (err) {
    return { ok: false, error: err.message };
  }
  if (!entry.manifest.supported_presets.includes(preset)) {
    return { ok: false, error: `template "${id}" does not support preset ${preset}` };
  }
  const check = entry.validate(parameters);
  if (!check.valid) {
    return { ok: false, error: `template parameters invalid: ${check.errors.join('; ')}` };
  }
  return { ok: true, entry, parameters };
}
