// WCAG 2.3.1 (general flash threshold) checker for a sequence of RGBA frames.
// A flash is a pair of opposing luminance changes, each at least 0.10, where the
// darker of the two states is below 0.80. Each reversal is counted once, at the
// frame index where the reversing change lands.

const CHANGE_THRESHOLD = 0.10;
const DARK_STATE_LIMIT = 0.80;
const MAX_FLASHES_PER_SECOND = 3;

const SRGB_TO_LINEAR = new Float64Array(256);
for (let c = 0; c < 256; c++) {
  const v = c / 255;
  SRGB_TO_LINEAR[c] = v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
}

// Mean relative luminance of a frame, in [0, 1].
function frameLuminance(frame) {
  const { rgba } = frame;
  const pixels = Math.floor(rgba.length / 4);
  if (pixels === 0) return 0;
  let sum = 0;
  for (let p = 0; p < pixels; p++) {
    const o = p * 4;
    sum += 0.2126 * SRGB_TO_LINEAR[rgba[o]]
      + 0.7152 * SRGB_TO_LINEAR[rgba[o + 1]]
      + 0.0722 * SRGB_TO_LINEAR[rgba[o + 2]];
  }
  return sum / pixels;
}

export function checkFlashes(frames, fps = 30) {
  const lum = frames.map(frameLuminance);

  // Frame indices at which a flash completes (the reversing change lands).
  const flashIndices = [];
  let prev = null; // { dir, from, to } of the last significant change
  for (let i = 1; i < lum.length; i++) {
    const delta = lum[i] - lum[i - 1];
    if (Math.abs(delta) < CHANGE_THRESHOLD) continue;
    const dir = delta > 0 ? 1 : -1;
    if (prev !== null && prev.dir === -dir) {
      const darker = Math.min(prev.from, prev.to, lum[i]);
      if (darker < DARK_STATE_LIMIT) flashIndices.push(i);
    }
    prev = { dir, from: lum[i - 1], to: lum[i] };
  }

  // Largest number of flashes whose frame index falls in any window of fps frames.
  let maxInOneSecond = 0;
  let right = 0;
  for (let left = 0; left < flashIndices.length; left++) {
    if (right < left) right = left;
    while (right < flashIndices.length && flashIndices[right] - flashIndices[left] < fps) right++;
    maxInOneSecond = Math.max(maxInOneSecond, right - left);
  }

  return {
    pass: maxInOneSecond <= MAX_FLASHES_PER_SECOND,
    flashes: flashIndices.length,
    maxInOneSecond,
  };
}
