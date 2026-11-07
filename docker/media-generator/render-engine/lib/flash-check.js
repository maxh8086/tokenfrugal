// WCAG 2.3.1 (three flashes or below threshold) checker for a sequence of RGBA frames.
//
// Passes if EITHER:
//   (a) there are no more than three general flashes and no more than three red flashes
//       within any one-second period, OR
//   (b) the combined area of flashes occurring concurrently is no more than .006 steradians.
//
// Source: https://www.w3.org/WAI/WCAG21/Understanding/three-flashes-or-below-threshold
//   - general flash: a pair of opposing changes in relative luminance of 10% or more of the
//     maximum relative luminance (1.0), where the relative luminance of the darker image is below 0.80.
//   - red flash: a pair of opposing transitions involving a saturated red. Working definition
//     (Note 3): one state has R/(R+G+B) >= 0.8, and the two states differ by more than 0.2 in
//     the CIE 1976 UCS (u', v') chromaticity diagram.
//   - area: .006 sr is 25% of a 10-degree field, which is a 341 x 256 px rectangle on a
//     1024 x 768 screen. The area limit here is that rectangle's share of the screen, applied
//     to any frame size (a fraction, so it does not depend on the decode size).
//
// Assumptions (see the design doc, D49): general and red flash counts use whole-frame state
// (mean luminance; any red-flashing pixel); area uses per-pixel flashes, and the concurrent
// area is the largest set of distinct pixels that flash within any one-second window. That
// is conservative: it can only overstate the area.

const CHANGE_THRESHOLD = 0.10;
const DARK_STATE_LIMIT = 0.80;
const MAX_FLASHES_PER_SECOND = 3;
const RED_SATURATION = 0.80;
const RED_CHROMA_DISTANCE = 0.20;
const AREA_LIMIT_PIXELS_1024X768 = 341 * 256; // 87,296 px
export const AREA_LIMIT_FRACTION = AREA_LIMIT_PIXELS_1024X768 / (1024 * 768);

// D65 white point in u'v', used for black pixels so their chromaticity is well defined.
const WHITE_U = 0.1978;
const WHITE_V = 0.4683;

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

// Largest number of indices (ascending frame indices) that fall in any window of fps frames.
function maxInWindow(indices, fps) {
  let max = 0;
  let right = 0;
  for (let left = 0; left < indices.length; left++) {
    if (right < left) right = left;
    while (right < indices.length && indices[right] - indices[left] < fps) right++;
    max = Math.max(max, right - left);
  }
  return max;
}

// Frame-level general flashes: indices where a reversing change lands.
function generalFlashFrames(lum) {
  const out = [];
  let prev = null; // { dir, from, to } of the last significant change
  for (let i = 1; i < lum.length; i++) {
    const delta = lum[i] - lum[i - 1];
    if (Math.abs(delta) < CHANGE_THRESHOLD) continue;
    const dir = delta > 0 ? 1 : -1;
    if (prev !== null && prev.dir === -dir) {
      const darker = Math.min(prev.from, prev.to, lum[i]);
      if (darker < DARK_STATE_LIMIT) out.push(i);
    }
    prev = { dir, from: lum[i - 1], to: lum[i] };
  }
  return out;
}

// Per-pixel pass: red flashes at frame level, and the largest concurrent flashing area.
function pixelFlashAnalysis(frames, fps) {
  const redFrames = [];
  if (frames.length < 2) return { redFrames, maxAreaFraction: 0 };

  const n = Math.floor(frames[0].rgba.length / 4);
  if (n === 0) return { redFrames, maxAreaFraction: 0 };

  const lumPrev = new Float64Array(n);
  const uPrev = new Float64Array(n);
  const vPrev = new Float64Array(n);
  const redPrev = new Uint8Array(n);
  const lastDir = new Int8Array(n);
  const lastFrom = new Float64Array(n);
  const lastTo = new Float64Array(n);
  const lastRedKind = new Int8Array(n); // 0 none, 1 entered red, 2 left red

  // Sliding window of flashing pixels: distinct pixels flashing in the last fps frames.
  const evFrame = [];
  const evPix = [];
  let head = 0;
  const counts = new Map();
  let maxDistinct = 0;

  function chroma(rgba, p) {
    // rgba index for pixel p
    const o = p * 4;
    const r = SRGB_TO_LINEAR[rgba[o]];
    const g = SRGB_TO_LINEAR[rgba[o + 1]];
    const b = SRGB_TO_LINEAR[rgba[o + 2]];
    const X = 0.4124 * r + 0.3576 * g + 0.1805 * b;
    const Y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    const Z = 0.0193 * r + 0.1192 * g + 0.9505 * b;
    const denom = X + 15 * Y + 3 * Z;
    if (denom === 0) return [WHITE_U, WHITE_V, 0, 0, 0];
    return [4 * X / denom, 9 * Y / denom, r, g, b];
  }

  // Frame 0 initialises the per-pixel state.
  {
    const rgba = frames[0].rgba;
    for (let p = 0; p < n; p++) {
      const c = chroma(rgba, p);
      uPrev[p] = c[0];
      vPrev[p] = c[1];
      const [, , r, g, b] = c;
      lumPrev[p] = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      const sum = r + g + b;
      redPrev[p] = sum > 0 && r / sum >= RED_SATURATION ? 1 : 0;
    }
  }

  for (let i = 1; i < frames.length; i++) {
    const rgba = frames[i].rgba;

    // Evict flashes that have left the one-second window ending at frame i.
    while (head < evFrame.length && evFrame[head] <= i - fps) {
      const p = evPix[head];
      const c = counts.get(p) - 1;
      if (c === 0) counts.delete(p);
      else counts.set(p, c);
      head++;
    }

    let anyRedFlash = false;
    for (let p = 0; p < n; p++) {
      const c = chroma(rgba, p);
      const [u, v, r, g, b] = c;
      const L = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      const sum = r + g + b;
      const red = sum > 0 && r / sum >= RED_SATURATION ? 1 : 0;

      // General flash at this pixel.
      const delta = L - lumPrev[p];
      if (Math.abs(delta) >= CHANGE_THRESHOLD) {
        const dir = delta > 0 ? 1 : -1;
        if (lastDir[p] === -dir) {
          const darker = Math.min(lastFrom[p], lastTo[p], L);
          if (darker < DARK_STATE_LIMIT) {
            evFrame.push(i);
            evPix.push(p);
            counts.set(p, (counts.get(p) ?? 0) + 1);
          }
        }
        lastDir[p] = dir;
        lastFrom[p] = lumPrev[p];
        lastTo[p] = L;
      }

      // Red flash at this pixel: opposing transitions into and out of a saturated red state.
      if (red !== redPrev[p]) {
        const dist = Math.hypot(u - uPrev[p], v - vPrev[p]);
        if (dist > RED_CHROMA_DISTANCE) {
          const kind = red ? 1 : 2;
          if (lastRedKind[p] !== 0 && lastRedKind[p] !== kind) anyRedFlash = true;
          lastRedKind[p] = kind;
        }
      }

      lumPrev[p] = L;
      uPrev[p] = u;
      vPrev[p] = v;
      redPrev[p] = red;
    }

    if (anyRedFlash) redFrames.push(i);
    if (counts.size > maxDistinct) maxDistinct = counts.size;
  }

  return { redFrames, maxAreaFraction: maxDistinct / n };
}

export function checkFlashes(frames, fps = 30) {
  const lum = frames.map(frameLuminance);
  const generalFrames = generalFlashFrames(lum);
  const maxGeneral = maxInWindow(generalFrames, fps);

  const pixels = pixelFlashAnalysis(frames, fps);
  const maxRed = maxInWindow(pixels.redFrames, fps);
  const countsPass = maxGeneral <= MAX_FLASHES_PER_SECOND && maxRed <= MAX_FLASHES_PER_SECOND;
  const areaPass = pixels.maxAreaFraction <= AREA_LIMIT_FRACTION;

  return {
    pass: countsPass || areaPass,
    flashes: generalFrames.length,
    maxInOneSecond: maxGeneral,
    redFlashes: pixels.redFrames.length,
    maxRedInOneSecond: maxRed,
    maxAreaFraction: pixels.maxAreaFraction,
    areaLimitFraction: AREA_LIMIT_FRACTION,
  };
}
