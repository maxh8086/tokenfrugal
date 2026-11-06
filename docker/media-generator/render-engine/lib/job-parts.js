// Splits a long job's scenes into parts that each fit the props limits (lib/props.js: totalMax 60 s and
// countMax 10 scenes per render). Parts are rendered one by one and joined with ffmpeg concat -c copy.
// Pure: no I/O.

export const PART_MAX_SECONDS = 60;
export const PART_MAX_SCENES = 10;

// scenes: [{seconds}] in order. Returns [[indexStart, indexEnd), ...] covering every scene once, in order.
// Greedy: a part closes when adding the next scene would exceed either limit.
export function planParts(scenes, { maxSeconds = PART_MAX_SECONDS, maxScenes = PART_MAX_SCENES } = {}) {
  if (!Array.isArray(scenes) || scenes.length === 0) return [];
  const parts = [];
  let start = 0;
  let total = 0;
  for (let i = 0; i < scenes.length; i++) {
    const seconds = scenes[i].seconds;
    if (!(seconds > 0) || seconds > maxSeconds) {
      throw new Error(`scene ${i} has ${seconds} seconds; a part can hold at most ${maxSeconds} s`);
    }
    const count = i - start;
    if (count > 0 && (total + seconds > maxSeconds || count + 1 > maxScenes)) {
      parts.push([start, i]);
      start = i;
      total = 0;
    }
    total += seconds;
  }
  parts.push([start, scenes.length]);
  return parts;
}

// Total seconds of a list of scenes.
export function totalSeconds(scenes) {
  return (Array.isArray(scenes) ? scenes : []).reduce((sum, s) => sum + (s.seconds || 0), 0);
}
