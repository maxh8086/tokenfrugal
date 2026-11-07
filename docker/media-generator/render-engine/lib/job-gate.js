// Gated job renders (D9, D39). A job.json body is validated, every gate before the full render
// (G1 to G6) must be approved against the artifact that job names for it, then the job is mapped
// to the props body the existing render path accepts. I/O is limited to hashing artifact files.
//
// Approval records hold the artifact path exactly as resolved here (absolute, under ARTIFACT_DIR),
// so a human must run bin/approve.js with that absolute path.

import path from 'node:path';
import { GATES, canOpen, hashArtifact, isApproved, readApprovals } from './approvals.js';
import { presets, validateJob } from './job-schema.js';
import { checkFormat } from './formats.js';
import { checkVoiceChoice } from './voice-choice.js';
import { PART_MAX_SECONDS, totalSeconds } from './job-parts.js';

// A full render may open only once G1 to G6 are approved; G7 is the publish approval after the render.
export const RENDER_GATE = 'G7';

// One destination per job for now: a job that names both would need two renders with two compositions.
// shorts uses its own vertical composition (D60) and is limited to one render part (PART_MAX_SECONDS).
const DESTINATION_PRESETS = Object.freeze({ youtube: presets.youtube, shorts: presets.shorts });

function gatesBeforeRender() {
  return GATES.slice(0, GATES.indexOf(RENDER_GATE));
}

// Maps a validated job to a props body for validateProps, plus the destination (a preset name) that picks
// the output file and the composition. Pure.
export function jobToPropsBody(job) {
  if (job.destinations.length !== 1) {
    return { ok: false, error: 'a job renders one destination at a time; name either youtube or shorts' };
  }
  const destination = job.destinations[0];
  const preset = DESTINATION_PRESETS[destination];
  if (!preset) {
    return { ok: false, error: `destination ${destination} is not rendered yet` };
  }
  if (destination === 'shorts' && totalSeconds(job.scenes) > PART_MAX_SECONDS) {
    return {
      ok: false,
      error: `shorts renders up to ${PART_MAX_SECONDS} seconds for now; the job runs ${totalSeconds(job.scenes)} seconds`,
    };
  }
  return {
    ok: true,
    destination,
    body: {
      fps: preset.fps,
      // Narration is stage 1 (D20): G1 reviews the narrated script, so a gated render always carries it.
      narration: true,
      narration_voice: checkVoiceChoice(job).voice,
      scenes: job.scenes.map((s) => ({ text: s.title, sub: s.body, seconds: s.seconds })),
    },
  };
}

// Resolves and hashes the artifact for each gate before the render. Returns {ok, artifacts} where
// artifacts[gate] = {artifact: absolute path, sha256}, or {ok: false, error}.
export async function resolveGateArtifacts(job, artifactRoot) {
  const root = path.resolve(artifactRoot);
  const declared = job.gate_artifacts || {};
  const artifacts = {};
  for (const gate of gatesBeforeRender()) {
    const rel = declared[gate];
    if (rel === undefined) {
      return { ok: false, error: `gate_artifacts is missing ${gate}` };
    }
    const full = path.resolve(root, rel);
    if (!full.startsWith(root + path.sep)) {
      return { ok: false, error: `gate ${gate} artifact must stay inside ARTIFACT_DIR` };
    }
    let sha256;
    try {
      sha256 = await hashArtifact(full);
    } catch {
      return { ok: false, error: `gate ${gate} artifact not found: ${rel}` };
    }
    artifacts[gate] = { artifact: full, sha256 };
  }
  return { ok: true, artifacts };
}

// Gates before the render that are not approved against their current artifact hash.
export function unapprovedGates(approvals, artifacts) {
  return gatesBeforeRender().filter(
    (g) => !isApproved(approvals, g, artifacts[g].artifact, artifacts[g].sha256),
  );
}

// Gates whose current hash has an approval recorded under a different path (for example a relative path
// typed into bin/approve.js). Used only to explain a refusal; it never grants approval.
export function pathMismatches(approvals, artifacts) {
  const entries = approvals && Array.isArray(approvals.approvals) ? approvals.approvals : [];
  const out = [];
  for (const g of gatesBeforeRender()) {
    const want = artifacts[g];
    if (isApproved(approvals, g, want.artifact, want.sha256)) continue;
    const other = entries.find((e) => e.gate === g && e.sha256 === want.sha256 && e.artifact !== want.artifact);
    if (other) out.push({ gate: g, recordedPath: other.artifact, expectedPath: want.artifact });
  }
  return out;
}

// Full gate decision for a job body. Returns {ok: true, body} with the props body to render, or
// {ok: false, status, payload} for the HTTP response.
export async function gateJob(job, { artifactRoot, approvalsPath }) {
  const checked = await validateJob(job);
  if (!checked.valid) {
    return { ok: false, status: 400, payload: { error: 'invalid job', findings: checked.errors } };
  }
  const format = checkFormat(job);
  if (!format.ok) {
    return { ok: false, status: 400, payload: { error: format.error } };
  }
  const voice = checkVoiceChoice(job);
  if (!voice.ok) {
    return { ok: false, status: 400, payload: { error: voice.error } };
  }
  const mapped = jobToPropsBody(job);
  if (!mapped.ok) {
    return { ok: false, status: 400, payload: { error: mapped.error } };
  }
  if (!artifactRoot || !approvalsPath) {
    return { ok: false, status: 503, payload: { error: 'job renders need ARTIFACT_DIR and APPROVALS_PATH set' } };
  }
  const resolved = await resolveGateArtifacts(job, artifactRoot);
  if (!resolved.ok) {
    return { ok: false, status: 400, payload: { error: resolved.error } };
  }
  let approvals;
  try {
    approvals = await readApprovals(approvalsPath);
  } catch (err) {
    return { ok: false, status: 503, payload: { error: `approvals unreadable: ${err.message}` } };
  }
  if (!canOpen(approvals, RENDER_GATE, (g) => resolved.artifacts[g])) {
    const mismatched = pathMismatches(approvals, resolved.artifacts);
    return {
      ok: false,
      status: 403,
      payload: {
        error: mismatched.length > 0 ? 'approval recorded for a different path' : 'gates not approved',
        gates: unapprovedGates(approvals, resolved.artifacts),
        ...(mismatched.length > 0 ? { mismatched } : {}),
      },
    };
  }
  return { ok: true, body: mapped.body, destination: mapped.destination };
}
