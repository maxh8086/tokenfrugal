// G5 stills (D59, D64): one PNG per scene, taken at each scene's start time across the whole job. The stills
// use the same job body, format, voice and gate checks as the film, but no MP4 is rendered. The snapshot itself
// is supplied by the caller (server.js wires it to hyperframes snapshot over a prepared work folder), so this
// module only validates, decides, takes the times and places the files. Gate order: G1 to G4 must be approved
// before any snapshot runs.

import { cp, mkdir, rm } from 'node:fs/promises';
import path from 'node:path';
import { isApproved, readApprovals } from './approvals.js';
import { resolveGateArtifacts, jobToPropsBody } from './job-gate.js';
import { checkFormat } from './formats.js';
import { validateJob } from './job-schema.js';
import { totalSeconds } from './job-parts.js';
import { checkVoiceChoice } from './voice-choice.js';
import { PreviewRefused } from './preview.js';

export const STILLS_GATES = ['G1', 'G2', 'G3', 'G4'];

// Start time of each scene, in seconds from the start of the film. Scene i starts where scene i-1 ends, so the
// starts follow the author's seconds exactly; the scene list is never reordered or trimmed here. Pure.
export function sceneStartTimes(scenes) {
  if (!Array.isArray(scenes)) throw new Error('sceneStartTimes: scenes must be an array');
  const out = [];
  let start = 0;
  for (let i = 0; i < scenes.length; i += 1) {
    const scene = scenes[i];
    if (!scene || typeof scene.seconds !== 'number' || !Number.isFinite(scene.seconds) || scene.seconds <= 0) {
      throw new Error(`sceneStartTimes: scene ${i} needs a positive finite seconds value`);
    }
    out.push({ index: i, start });
    start += scene.seconds;
  }
  return out;
}

// The argument list for `hyperframes snapshot`: one frame at each time, written into outDir. A time of exactly 0
// is nudged to 0.05 s, so the first still is taken just inside the first scene rather than on its opening frame
// (the nudge is only where the frame is grabbed; the scene still starts at 0). --no-end asks hyperframes not to
// add an extra end frame, so the file count matches the scene count. Pure.
export function buildSnapshotArgs({ projectDir, outDir, times }) {
  const at = times.map((t) => (t === 0 ? 0.05 : t)).join(',');
  return ['snapshot', '--at', at, '--no-end', '-o', outDir, projectDir];
}

// The approval check for stills (G5). G1 to G4 must each be approved against the SHA-256 of their current
// artifact files. The stills read no approval of their own: the G4 voice gate is the last one a still depends on.
// Returns {ok: true} or {ok: false, status, payload}. Same status shapes as checkG4Approval in lib/preview.js.
export async function checkStillsApproval(job, { artifactRoot, approvalsPath }) {
  // Without the root and the approvals file nothing can be checked, so the request is unavailable, not refused.
  if (!artifactRoot || !approvalsPath) {
    return { ok: false, status: 503, payload: { error: 'stills need ARTIFACT_DIR and APPROVALS_PATH set' } };
  }
  let approvals;
  try {
    approvals = await readApprovals(approvalsPath);
  } catch (err) {
    return { ok: false, status: 503, payload: { error: `approvals unreadable: ${err.message}` } };
  }
  const resolved = await resolveGateArtifacts(job, artifactRoot, STILLS_GATES);
  if (!resolved.ok) return { ok: false, status: 400, payload: { error: resolved.error } };
  // Every unapproved gate is named, so the caller can see the whole list in one response.
  const gates = STILLS_GATES.filter(
    (g) => !isApproved(approvals, g, resolved.artifacts[g].artifact, resolved.artifacts[g].sha256),
  );
  if (gates.length > 0) return { ok: false, status: 403, payload: { error: 'gates not approved', gates } };
  return { ok: true };
}

// Everything that can be checked without snapshotting: the job schema, format, voice and the props mapping.
// Returns {ok: true, props, scenes} or {ok: false, status, payload}. `scenes` are the mapped scenes with their
// seconds, which give the snapshot times. The props carry the whole job's duration.
// The props validation a render runs (validateProps) is not applied here on purpose: it limits each scene to
// 0.83 to 8 s and the film to 60 s, and a still only needs the scene starts. A job the render would refuse can
// therefore still get stills; the render stays the place where those limits hold.
async function mapStillsJob(job) {
  const checked = await validateJob(job);
  if (!checked.valid) return { ok: false, status: 400, payload: { error: 'invalid job', findings: checked.errors } };
  const format = checkFormat(job);
  if (!format.ok) return { ok: false, status: 400, payload: { error: format.error } };
  const voice = checkVoiceChoice(job);
  if (!voice.ok) return { ok: false, status: 400, payload: { error: voice.error } };
  const mapped = jobToPropsBody(job);
  if (!mapped.ok) return { ok: false, status: 400, payload: { error: mapped.error } };
  const props = { ...mapped.body, duration: totalSeconds(mapped.body.scenes) };
  return { ok: true, props, scenes: mapped.body.scenes };
}

// Builds outDir/scene-NN.png (NN from 01, two digits or more) for a job, one still per scene in time order.
// `checkApproval(job)` must resolve to {ok: true} or {ok: false, status, payload}; it runs after the job is
// validated and before any snapshot. `snapshot({times, outDir, props})` must resolve to {files}: one PNG path
// per time, in time order, written into outDir. Returns {count, files}. Refusals throw PreviewRefused.
export async function buildStills(job, { outDir, checkApproval, snapshot } = {}) {
  if (!outDir) throw new Error('buildStills: outDir is required');
  if (typeof checkApproval !== 'function') throw new Error('buildStills: checkApproval is required');
  if (typeof snapshot !== 'function') throw new Error('buildStills: snapshot is required');

  const mapped = await mapStillsJob(job);
  if (!mapped.ok) throw new PreviewRefused(mapped.status, mapped.payload);

  const decision = await checkApproval(job);
  if (!decision || !decision.ok) {
    throw new PreviewRefused(decision?.status ?? 403, decision?.payload ?? { error: 'gates not approved' });
  }

  const count = mapped.scenes.length;
  const times = sceneStartTimes(mapped.scenes).map((s) => s.start);
  // The snapshot writes into a scratch folder; only the named scene files are kept in outDir.
  const frameDir = path.join(outDir, 'frames');
  await mkdir(frameDir, { recursive: true });
  const files = [];
  try {
    const shot = await snapshot({ times, outDir: frameDir, props: mapped.props });
    const got = shot && Array.isArray(shot.files) ? shot.files : [];
    // A count mismatch means the scenes and the stills no longer line up, so no partial set is kept.
    if (got.length !== count) {
      throw new Error(`snapshot returned ${got.length} files for ${count} scenes`);
    }
    for (let i = 0; i < count; i += 1) {
      const dest = path.join(outDir, `scene-${String(i + 1).padStart(2, '0')}.png`);
      await cp(got[i], dest);
      files.push(dest);
    }
  } finally {
    await rm(frameDir, { recursive: true, force: true });
  }
  return { count, files };
}
