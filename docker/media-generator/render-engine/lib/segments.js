// Pure helpers for per-scene MP4 segments (D54): planning the spans, the ffmpeg concat list, and reuse checks.

const round3 = (n) => Math.round(n * 1000) / 1000;

// timedScenes: [{start, seconds}] in seconds. Returns [{index, start, end}] clamped to duration.
// Spans that end at or before their start (after clamping) are dropped.
export function planSegments(timedScenes, duration) {
  if (!Array.isArray(timedScenes) || timedScenes.length === 0) {
    return [{ index: 0, start: 0, end: duration }];
  }
  const spans = [];
  for (const scene of timedScenes) {
    const start = Math.max(0, scene.start);
    const end = Math.min(duration, scene.start + scene.seconds);
    if (end <= start) continue;
    spans.push({ start: round3(start), end: round3(end) });
  }
  return spans.map((span, index) => ({ index, ...span }));
}

// ffmpeg concat demuxer list: one "file '<path>'" line per file, single quotes escaped as '\''.
export function concatListText(files) {
  return files.map((file) => `file '${file.replace(/'/g, "'\\''")}'`).join('\n') + '\n';
}

// A segment is reusable when it exists and is not empty. stats is the result of fs.stat, or null.
export function segmentIsValid(stats) {
  return stats !== null && stats !== undefined && stats.size > 0;
}

// True only when spans run contiguously from 0 to duration (within 0.001 s): no leading, middle or trailing gap.
export function coversDuration(spans, duration) {
  const EPS = 0.001;
  if (!Array.isArray(spans) || spans.length === 0) return false;
  if (Math.abs(spans[0].start) > EPS) return false;
  for (let i = 1; i < spans.length; i++) {
    if (Math.abs(spans[i].start - spans[i - 1].end) > EPS) return false;
  }
  return Math.abs(spans[spans.length - 1].end - duration) <= EPS;
}
