import { presets } from './job-schema.js';

// G2 format list (D27). Each format fixes its pixel size, frame rate and maximum length (D45, D56).
// maxSeconds null means the length is not fixed by the design yet (D29, Facebook Reel in O18).
// Only formats whose size and frame rate match a built preset can render today (see renderable below).

export const FORMATS = Object.freeze({
  presentation: { label: 'Presentation', width: 1920, height: 1080, fps: 30, maxSeconds: 300 }, // 5 min default, D29 (to confirm)
  video: { label: 'Video', width: 1920, height: 1080, fps: 30, maxSeconds: 300 }, // 5 min default, D29 (to confirm)
  'youtube-video': { label: 'YouTube video', width: 1920, height: 1080, fps: 30, maxSeconds: 43200 }, // 12 h, O18
  'youtube-short': { label: 'YouTube Short', width: 1080, height: 1920, fps: 30, maxSeconds: 180 }, // 3 min, O18
  'instagram-post': { label: 'Instagram post', width: 1080, height: 1350, fps: 30, maxSeconds: 3600 }, // 4:5, 60 min, O18
  'instagram-reel': { label: 'Instagram Reel', width: 1080, height: 1920, fps: 30, maxSeconds: 180 }, // 3 min, O18
  'facebook-post': { label: 'Facebook post', width: 1920, height: 1080, fps: 30, maxSeconds: 14400 }, // 240 min, O18
  'facebook-reel': { label: 'Facebook Reel', width: 1080, height: 1920, fps: 30, maxSeconds: null }, // length open, O18
  'linkedin-post': { label: 'LinkedIn post', width: 1920, height: 1080, fps: 30, maxSeconds: 600 }, // 10 min, O18
});

export const FORMAT_IDS = Object.freeze(Object.keys(FORMATS));

// The engine renders one size per destination preset (job-schema.js): youtube 1920x1080 and shorts 1080x1920, both at 30 fps.
export const RENDERABLE = Object.freeze(
  Object.entries(presets).map(([destination, p]) => Object.freeze({ destination, width: p.width, height: p.height, fps: p.fps })),
);

// Pure. Returns {ok: true, total} or {ok: false, error}. A job without a format keeps today's behaviour.
export function checkFormat(job) {
  if (job.format === undefined) return { ok: true, total: null };
  const format = FORMATS[job.format];
  if (!format) return { ok: false, error: `unknown format ${job.format}` };
  const total = job.scenes.reduce((sum, s) => sum + s.seconds, 0);
  if (format.maxSeconds !== null && total > format.maxSeconds) {
    return {
      ok: false,
      error: `format ${format.label} allows at most ${format.maxSeconds} seconds; the job runs ${total} seconds`,
    };
  }
  const rendered = RENDERABLE.find((r) => r.width === format.width && r.height === format.height && r.fps === format.fps);
  if (!rendered) {
    const sizes = RENDERABLE.map((r) => `${r.width}x${r.height} at ${r.fps} fps (${r.destination})`).join(', ');
    return {
      ok: false,
      error: `format ${format.label} (${format.width}x${format.height} at ${format.fps} fps) is not rendered yet; rendered sizes are ${sizes}`,
    };
  }
  if (job.destinations?.[0] !== rendered.destination) {
    return {
      ok: false,
      error: `format ${format.label} renders as ${rendered.destination}; name ${rendered.destination} as the job destination`,
    };
  }
  return { ok: true, total };
}
