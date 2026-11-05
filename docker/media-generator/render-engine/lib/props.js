// Validation and defaults for the /render request body.
// Kept free of I/O so it can be unit tested with `node --test`.

export const LIMITS = {
  titleMax: 80,
  subtitleMax: 120,
  durationMin: 3,
  durationMax: 60,
};

export const FPS_VALUES = [24, 30, 60];

export const SCENE_LIMITS = {
  countMin: 1,
  countMax: 10,
  textMax: 80,
  subMax: 120,
  secondsMin: 0.83,
  secondsMax: 8,
  totalMax: 60,
};

export const DEFAULTS = {
  title: 'Hello from HyperFrames',
  subtitle: '',
  duration: 3,
  background: '#0d1117',
  accent: '#2f81f7',
  textColor: '#e6edf3',
  subColor: '#8b949e',
  fps: 60,
  narration: false,
  music: false,
  scenes: [{ text: 'Hello from HyperFrames', sub: '', seconds: 3 }],
};

const HEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
// Scene keys. sub/subtitle and seconds/duration are aliases: give one form of each, not both.
const SCENE_KEYS = ['text', 'sub', 'subtitle', 'seconds', 'duration'];

function isPlainObject(v) {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

// Validates the scenes array. Returns { ok: true, scenes, total } or { ok: false, error }.
function parseScenes(list) {
  if (!Array.isArray(list)) {
    return { ok: false, error: 'scenes must be an array' };
  }
  if (list.length < SCENE_LIMITS.countMin || list.length > SCENE_LIMITS.countMax) {
    return { ok: false, error: `scenes must have from ${SCENE_LIMITS.countMin} to ${SCENE_LIMITS.countMax} items` };
  }

  const scenes = [];
  for (let i = 0; i < list.length; i++) {
    const item = list[i];
    const where = `scenes[${i}]`;
    if (!isPlainObject(item)) {
      return { ok: false, error: `${where} must be an object` };
    }
    for (const key of Object.keys(item)) {
      if (!SCENE_KEYS.includes(key)) {
        return { ok: false, error: `${where} has unknown field: ${key}` };
      }
    }
    if (item.sub !== undefined && item.subtitle !== undefined) {
      return { ok: false, error: 'use either sub or subtitle' };
    }
    if (item.seconds !== undefined && item.duration !== undefined) {
      return { ok: false, error: 'use either seconds or duration' };
    }

    if (typeof item.text !== 'string' || item.text.trim() === '') {
      return { ok: false, error: `${where}.text must be a non-empty string` };
    }
    if (item.text.trim().length > SCENE_LIMITS.textMax) {
      return { ok: false, error: `${where}.text is longer than ${SCENE_LIMITS.textMax} characters` };
    }

    const rawSub = item.sub !== undefined ? item.sub : item.subtitle;
    let sub = '';
    if (rawSub !== undefined) {
      if (typeof rawSub !== 'string') {
        return { ok: false, error: `${where}.sub must be a string` };
      }
      if (rawSub.trim().length > SCENE_LIMITS.subMax) {
        return { ok: false, error: `${where}.sub is longer than ${SCENE_LIMITS.subMax} characters` };
      }
      sub = rawSub.trim();
    }

    const s = item.seconds !== undefined ? item.seconds : item.duration;
    if (typeof s !== 'number' || !Number.isFinite(s) || s < SCENE_LIMITS.secondsMin || s > SCENE_LIMITS.secondsMax) {
      return { ok: false, error: `${where}.seconds must be a number from ${SCENE_LIMITS.secondsMin} to ${SCENE_LIMITS.secondsMax}` };
    }

    scenes.push({ text: item.text.trim(), sub, seconds: s });
  }

  const total = Math.round(scenes.reduce((sum, sc) => sum + sc.seconds, 0) * 100) / 100;
  if (total > SCENE_LIMITS.totalMax) {
    return { ok: false, error: `scenes total ${total} seconds, the limit is ${SCENE_LIMITS.totalMax}` };
  }

  return { ok: true, scenes, total };
}

// Returns { ok: true, props, hasScenes } or { ok: false, error }.
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

  const hasScenes = body.scenes !== undefined;
  if (hasScenes && body.title !== undefined) {
    return { ok: false, error: 'use either scenes or title' };
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

  if (body.fps !== undefined) {
    if (!FPS_VALUES.includes(body.fps)) {
      return { ok: false, error: `fps must be one of ${FPS_VALUES.join(', ')}` };
    }
    props.fps = body.fps;
  }

  for (const key of ['narration', 'music']) {
    if (body[key] !== undefined) {
      if (typeof body[key] !== 'boolean') {
        return { ok: false, error: `${key} must be true or false` };
      }
      props[key] = body[key];
    }
  }

  if (hasScenes) {
    const parsed = parseScenes(body.scenes);
    if (!parsed.ok) return parsed;
    props.scenes = parsed.scenes;
    props.duration = parsed.total;
  } else {
    // One code path for the template: a single title becomes a single scene.
    props.scenes = [{ text: props.title, sub: props.subtitle, seconds: props.duration }];
  }

  return { ok: true, props, hasScenes };
}

// Response props: only the fields the caller sent (normalised values), never the defaults.
export function echoProps(body, props) {
  const out = {};
  for (const key of Object.keys(props)) {
    if (body && Object.prototype.hasOwnProperty.call(body, key)) {
      out[key] = props[key];
    }
  }
  return out;
}

// Serialises props as a JS file. Escapes < and > so a value cannot close a <script> tag.
export function propsToJs(props) {
  const json = JSON.stringify(props).replace(/</g, '\\u003c').replace(/>/g, '\\u003e');
  return `window.PROPS = ${json};\n`;
}
