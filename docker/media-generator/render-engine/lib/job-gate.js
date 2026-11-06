// Gated job renders (D9, D39). A job.json body is validated, every gate before the full render
// (G1 to G6) must be approved against the artifact that job names for it, then the job is mapped
// to the props body the existing render path accepts. I/O is limited to hashing artifact files.
//
// Approval records hold the artifact path exactly as resolved here (absolute, under ARTIFACT_DIR),
// so a human must run bin/approve.js with that absolute path.

import path from 'node:path';
import { GATES, canOpen, hashArtifact, isApproved, readApprovals } from './approvals.js';
import { presets, validateJob } from './job-schema.js';

// A full render may open only once G1 to G6 are approved; G7 is the publish approval after the render.
export const RENDER_GATE = 'G7';
const RENDERED_DESTINATION = 'youtube'; // the engine renders 1920x1080 only; shorts (1080x1920) is not built yet

function gatesBeforeRender() {
  return GATES.slice(0, GATES.indexOf(RENDER_GATE));
}

// Maps a validated job to a props body for validateProps. Pure.
export function jobToPropsBody(job) {
  const unsupported = job.destinations.filter((d) => d !== RENDERED_DESTINATION);
  if (unsupported.length > 0) {
    return {
      ok: false,
      error: `destination ${unsupported.join(', ')} is not rendered yet; only ${RENDERED_DESTINATION} (1920x1080) is supported`,
    };
  }
  return {
    ok: true,
    body: {
      fps: presets.youtube.fps,
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

// Full gate decision for a job body. Returns {ok: true, body} with the props body to render, or
// {ok: false, status, payload} for the HTTP response.
export async function gateJob(job, { artifactRoot, approvalsPath }) {
  const checked = await validateJob(job);
  if (!checked.valid) {
    return { ok: false, status: 400, payload: { error: 'invalid job', findings: checked.errors } };
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
    return {
      ok: false,
      status: 403,
      payload: { error: 'gates not approved', gates: unapprovedGates(approvals, resolved.artifacts) },
    };
  }
  return { ok: true, body: mapped.body };
}
