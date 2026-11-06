// Contact sheet for review (D41): one PNG tiling frames sampled at a fixed rate from a finished MP4.
// Dense sampling is the default (one frame per second, every frame of a short clip is not required).
// This module only builds the ffmpeg argument list and validates it; the caller runs ffmpeg.

const MAX_TILE = 16;
const MIN_WIDTH = 64;
const MAX_WIDTH = 1920;

function positiveInt(value, name, max) {
  if (!Number.isInteger(value) || value < 1 || value > max) {
    throw new Error(`${name} must be an integer from 1 to ${max}`);
  }
  return value;
}

// Returns the ffmpeg argv (without the leading "ffmpeg") that writes one PNG contact sheet.
// Throws on invalid input so a bad request never reaches ffmpeg.
export function buildContactSheetArgs({
  input,
  output,
  cols = 4,
  rows = 4,
  frameWidth = 320,
  fps = 1,
} = {}) {
  for (const [name, value] of [['input', input], ['output', output]]) {
    if (typeof value !== 'string' || value === '' || value.startsWith('-')) {
      throw new Error(`${name} must be a non-empty path that does not start with "-"`);
    }
  }
  const c = positiveInt(cols, 'cols', MAX_TILE);
  const r = positiveInt(rows, 'rows', MAX_TILE);
  if (!Number.isInteger(frameWidth) || frameWidth < MIN_WIDTH || frameWidth > MAX_WIDTH || frameWidth % 2 !== 0) {
    throw new Error(`frameWidth must be an even integer from ${MIN_WIDTH} to ${MAX_WIDTH}`);
  }
  if (typeof fps !== 'number' || !Number.isFinite(fps) || fps <= 0 || fps > 30) {
    throw new Error('fps must be a number above 0 and at most 30');
  }
  const vf = `fps=${fps},scale=${frameWidth}:-2,tile=${c}x${r}`;
  return ['-y', '-loglevel', 'error', '-i', input, '-vf', vf, '-frames:v', '1', output];
}
