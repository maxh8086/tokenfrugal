// Output layout for gated job renders (D25, D57): OUTPUT_DIR/<job_id>/<preset>.mp4.
// Props renders and the intermediate parts of a long job keep the flat OUTPUT_DIR/<name>.mp4 layout.
// Pure: no I/O.

import path from 'node:path';

export const JOB_PRESETS = ['youtube'];
const JOB_ID_RE = /^[A-Za-z0-9_-]{1,64}$/;

// Returns the path of a job's preset file, relative to OUTPUT_DIR, e.g. "abc/youtube.mp4".
export function jobOutputRel(jobId, preset) {
  if (typeof jobId !== 'string' || !JOB_ID_RE.test(jobId)) {
    throw new Error('bad job id for output folder');
  }
  if (!JOB_PRESETS.includes(preset)) {
    throw new Error(`unknown output preset: ${preset}`);
  }
  return path.posix.join(jobId, `${preset}.mp4`);
}

// Returns the served URL of a job's preset file, e.g. "/output/abc/youtube.mp4".
export function jobOutputUrl(jobId, preset) {
  return `/output/${jobOutputRel(jobId, preset)}`;
}
