// Validation and defaults for the /render request body.
// Kept free of I/O so it can be unit tested with `node --test`.

export const LIMITS = {
  titleMax: 80,
  subtitleMax: 120,
  durationMin: 3,
  durationMax: 60,
};

export const DEFAULTS = {
  title: 'Hello from HyperFrames',
  subtitle: '',
  duration: 3,
  background: '#0d1117',
  accent: '#2f81f7',
  textColor: '#e6edf3',
  subColor: '#8b949e',
};

const HEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

// Returns { ok: true, props } or { ok: false, error }.
// Unknown keys are rejected so a typo in a request is visible to the caller.
export function validateProps(body) {
  if (body === undefined || body === null) body = {};
  if (typeof body !== 'object' || Array.isArray(body)) {
    return { ok: false, error: 'body must be a JSON object' };
  }

  const allowed = Object.keys(DEFAULTS);
  for (const key of Object.keys(body)) {
    if (!allowed.includes(key)) {
      return { ok: false, error: `unknown field: ${key}` };
    }
  }

  const props = { ...DEFAULTS };

  if (body.title !== undefined) {
    if (typeof body.title !== 'string' || body.title.trim() === '') {
      return { ok: false, error: 'title must be a non-empty string' };
    }
    if (body.title.length > LIMITS.titleMax) {
      return { ok: false, error: `title is longer than ${LIMITS.titleMax} characters` };
    }
    props.title = body.title.trim();
  }

  if (body.subtitle !== undefined) {
    if (typeof body.subtitle !== 'string') {
      return { ok: false, error: 'subtitle must be a string' };
    }
    if (body.subtitle.length > LIMITS.subtitleMax) {
      return { ok: false, error: `subtitle is longer than ${LIMITS.subtitleMax} characters` };
    }
    props.subtitle = body.subtitle.trim();
  }

  if (body.duration !== undefined) {
    const d = body.duration;
    if (typeof d !== 'number' || !Number.isFinite(d) || d < LIMITS.durationMin || d > LIMITS.durationMax) {
      return { ok: false, error: `duration must be a number of seconds from ${LIMITS.durationMin} to ${LIMITS.durationMax}` };
    }
    props.duration = d;
  }

  for (const key of ['background', 'accent', 'textColor', 'subColor']) {
    if (body[key] !== undefined) {
      if (typeof body[key] !== 'string' || !HEX.test(body[key])) {
        return { ok: false, error: `${key} must be a hex colour such as #0d1117 or #fff` };
      }
      props[key] = body[key];
    }
  }

  return { ok: true, props };
}

// Serialises props as a JS file. Escapes < and > so a value cannot close a <script> tag.
export function propsToJs(props) {
  const json = JSON.stringify(props).replace(/</g, '\\u003c').replace(/>/g, '\\u003e');
  return `window.PROPS = ${json};\n`;
}
