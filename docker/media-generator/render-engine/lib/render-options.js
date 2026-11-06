// Render options from D54: motion-blur samples, resolution, and the measured-fps budget.
// Pure functions with no I/O, so they can be unit tested with `node --test`.

export const BLUR_SAMPLES_DEFAULT = 32;
export const BLUR_SAMPLES_MIN = 4;   // 0 turns motion blur off; 1 to 3 is not a useful setting
export const BLUR_SAMPLES_MAX = 32;
export const BUDGET_SAFETY = 1.5;    // projected time is multiplied by this before the budget check
export const SEGMENT_TIMEOUT_FACTOR = 3; // per-call timeout is this many times the expected segment time

// Returns { ok: true, value } with value 0 (off) or 4..32, or { ok: false, error }.
export function parseMotionBlurSamples(v) {
  if (v === undefined) return { ok: true, value: BLUR_SAMPLES_DEFAULT };
  if (v === 0) return { ok: true, value: 0 };
  if (!Number.isInteger(v) || v < BLUR_SAMPLES_MIN || v > BLUR_SAMPLES_MAX) {
    return { ok: false, error: `motion_blur_samples must be 0 (off) or an integer from ${BLUR_SAMPLES_MIN} to ${BLUR_SAMPLES_MAX}` };
  }
  return { ok: true, value: v };
}

// Only 1080p is built. 4K is out of scope by default (D54); it is rejected until a measured machine and a user request allow it.
export function parseResolution(v) {
  if (v === undefined || v === '1080p') return { ok: true, value: '1080p' };
  if (v === '4k') {
    return { ok: false, error: 'resolution 4k is not enabled; 4K is out of scope by default (D54)' };
  }
  return { ok: false, error: 'resolution must be "1080p"' };
}

export function framesFor(seconds, fps) {
  return Math.round(seconds * fps);
}

// Expected wall-clock time (ms) for `frames` frames, given the frame rate measured on an earlier scene.
export function expectedMs(frames, measuredFps) {
  return (frames / measuredFps) * 1000;
}

// Per-call timeout for one segment: never below the floor, and scaled to the measured speed once it is known.
export function segmentTimeoutMs(frames, measuredFps, floorMs) {
  if (!measuredFps) return floorMs;
  return Math.max(floorMs, Math.ceil(expectedMs(frames, measuredFps) * SEGMENT_TIMEOUT_FACTOR));
}

// True when the remaining work, with the safety margin, still fits in the job budget.
export function fitsBudget({ elapsedMs, remainingFrames, measuredFps, budgetMs }) {
  if (!measuredFps) return true;
  const projected = elapsedMs + expectedMs(remainingFrames, measuredFps) * BUDGET_SAFETY;
  return projected <= budgetMs;
}

// A segment is only reusable when the motion-blur setting that made it is the same as the current one.
export function settingsKey({ blurSamples, resolution }) {
  return `blur=${blurSamples};res=${resolution}`;
}
