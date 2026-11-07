// G6 preview (D59, D64): the first 60 s of the job, rendered at the chosen format's full resolution and
// muxed with the G4 voice sample. The film goes through the same render path as POST /render (the caller
// supplies `render`, which server.js wires to renderJob); this module only decides the window, checks the
// approvals and places the file. Gate order: G1 to G3 and G4 must be approved before any preview renders.

import { cp, mkdir, rename, rm } from 'node:fs/promises';
import path from 'node:path';
import { canOpen, hashArtifact, isApproved, readApprovals } from './approvals.js';
import { resolveGateArtifacts, jobToPropsBody } from './job-gate.js';
import { checkFormat } from './formats.js';
import { validateJob } from './job-schema.js';
import { SCENE_LIMITS } from './props.js';
import { SAMPLE_SECONDS, buildVoiceSample } from './voice-sample.js';
import { checkVoiceChoice } from './voice-choice.js';

export const PREVIEW_SECONDS = SAMPLE_SECONDS;
export const PREVIEW_FILE = 'preview.mp4';
const EARLIER_GATES = ['G1', 'G2', 'G3'];

// A refusal from the preview path: an HTTP status and the JSON body to send with it.
export class PreviewRefused extends Error {
  constructor(status, payload) {
    super(payload.error);
    this.status = status;
    this.payload = payload;
  }
}

// The scenes that make up the first `target` seconds of the film. Whole scenes are taken while they fit; the
// scene that crosses the target is cut to the remaining time. Pure.
// Returns {ok: true, scenes, seconds} or {ok: false, error}. A cut that would leave a clip shorter than the
// props minimum is refused, because props validation would reject it.
export function previewWindow(scenes, target = PREVIEW_SECONDS) {
  if (!Array.isArray(scenes)) throw new Error('previewWindow: scenes must be an array');
  const out = [];
  let start = 0;
  for (let i = 0; i < scenes.length; i += 1) {
    const scene = scenes[i];
    if (!scene || typeof scene.seconds !== 'number' || !Number.isFinite(scene.seconds) || scene.seconds <= 0) {
      throw new Error(`previewWindow: scene ${i} needs a positive seconds value`);
    }
    if (start >= target) break;
    const take = Math.min(scene.seconds, target - start);
    if (take < scene.seconds && take < SCENE_LIMITS.secondsMin) {
      return {
        ok: false,
        error: `the ${target} s preview would end ${take.toFixed(2)} s into scene ${i + 1}; a scene needs at least ${SCENE_LIMITS.secondsMin} s, so the preview cannot be cut on this scene boundary`,
      };
    }
    out.push({ ...scene, seconds: take });
    start += take;
  }
  if (start < target - 1e-9) {
    const total = scenes.reduce((sum, s) => sum + (s && s.seconds > 0 ? s.seconds : 0), 0);
    return { ok: false, error: `the job runs ${total} seconds; a preview needs ${target} seconds` };
  }
  return { ok: true, scenes: out, seconds: target };
}

// Everything that can be checked without rendering or synthesizing: the job schema, the format, the voice,
// the window and the props mapping. Returns {ok: true, props} (the props body for the render) or {ok: false, status, payload}.
export async function validatePreviewJob(job) {
  const checked = await validateJob(job);
  if (!checked.valid) {
    return { ok: false, status: 400, payload: { error: 'invalid job', findings: checked.errors } };
  }
  const format = checkFormat(job);
  if (!format.ok) return { ok: false, status: 400, payload: { error: format.error } };
  const voice = checkVoiceChoice(job);
  if (!voice.ok) return { ok: false, status: 400, payload: { error: voice.error } };
  const win = previewWindow(job.scenes);
  if (!win.ok) return { ok: false, status: 400, payload: { error: win.error } };
  const mapped = jobToPropsBody({ ...job, scenes: win.scenes });
  if (!mapped.ok) return { ok: false, status: 400, payload: { error: mapped.error } };
  return { ok: true, props: mapped.body };
}

// The approval check for a preview (D38, D39). It needs the sample that was just built: G1 to G3 must be
// approved against their current files, and G4 must be approved at the job's declared G4 path against the
// SHA-256 of that sample. Returns {ok: true} or {ok: false, status, payload}.
export async function checkG4Approval(job, { artifactRoot, approvalsPath, sample }) {
  if (!artifactRoot || !approvalsPath) {
    return { ok: false, status: 503, payload: { error: 'previews need ARTIFACT_DIR and APPROVALS_PATH set' } };
  }
  let approvals;
  try {
    approvals = await readApprovals(approvalsPath);
  } catch (err) {
    return { ok: false, status: 503, payload: { error: `approvals unreadable: ${err.message}` } };
  }
  const earlier = await resolveGateArtifacts(job, artifactRoot, EARLIER_GATES);
  if (!earlier.ok) return { ok: false, status: 400, payload: { error: earlier.error } };
  if (!canOpen(approvals, 'G4', (g) => earlier.artifacts[g])) {
    const gates = EARLIER_GATES.filter(
      (g) => !isApproved(approvals, g, earlier.artifacts[g].artifact, earlier.artifacts[g].sha256),
    );
    return { ok: false, status: 403, payload: { error: 'gates not approved', gates } };
  }
  const declared = job.gate_artifacts && job.gate_artifacts.G4;
  if (typeof declared !== 'string' || declared === '') {
    return { ok: false, status: 400, payload: { error: 'gate_artifacts is missing G4' } };
  }
  const root = path.resolve(artifactRoot);
  const g4Path = path.resolve(root, declared);
  if (!g4Path.startsWith(root + path.sep)) {
    return { ok: false, status: 400, payload: { error: 'gate G4 artifact must stay inside ARTIFACT_DIR' } };
  }
  const sha256 = await hashArtifact(sample.file);
  if (!isApproved(approvals, 'G4', g4Path, sha256)) {
    return {
      ok: false,
      status: 403,
      payload: { error: 'G4 is not approved against the current voice sample', gate: 'G4', artifact: g4Path, sha256 },
    };
  }
  return { ok: true };
}

// Builds outDir/preview.mp4 for a job: the voice sample (G4 window), the approval check, then the render.
// `render(props, {audioFile, seconds})` must resolve to {file} with the rendered MP4 (its audio is replaced by
// audioFile). `checkApproval(sample)` must resolve to {ok: true} or {ok: false, status, payload}; it runs after
// the sample is built and before any render. Returns {file, seconds}. Refusals throw PreviewRefused.
export async function buildPreview(job, {
  baseUrl,
  outDir,
  render,
  checkApproval,
  fetchImpl,
  runFfmpeg,
} = {}) {
  if (!outDir) throw new Error('buildPreview: outDir is required');
  if (typeof render !== 'function') throw new Error('buildPreview: render is required');
  if (typeof checkApproval !== 'function') throw new Error('buildPreview: checkApproval is required');

  const validated = await validatePreviewJob(job);
  if (!validated.ok) throw new PreviewRefused(validated.status, validated.payload);

  const sample = await buildVoiceSample(job, { baseUrl, outDir, fetchImpl, runFfmpeg });

  const decision = await checkApproval(sample);
  if (!decision || !decision.ok) {
    throw new PreviewRefused(decision?.status ?? 403, decision?.payload ?? { error: 'G4 is not approved' });
  }

  const rendered = await render(validated.props, { audioFile: sample.file, seconds: PREVIEW_SECONDS });
  const file = path.join(outDir, PREVIEW_FILE);
  await mkdir(outDir, { recursive: true });
  await rename(rendered.file, file).catch(async () => {
    // rename fails across devices (the render folder to the output folder); fall back to copy.
    await cp(rendered.file, file);
    await rm(rendered.file, { force: true });
  });
  return { file, seconds: PREVIEW_SECONDS };
}
