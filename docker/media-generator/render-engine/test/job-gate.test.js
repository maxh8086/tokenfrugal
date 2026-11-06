import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { gateJob, jobToPropsBody, resolveGateArtifacts, unapprovedGates } from '../lib/job-gate.js';
import { hashArtifact, readApprovals, recordApproval } from '../lib/approvals.js';
import { validateJob } from '../lib/job-schema.js';

const BEFORE_RENDER = ['G1', 'G2', 'G3', 'G4', 'G5', 'G6'];

let dir;
let root;
let approvalsPath;

beforeEach(async () => {
  dir = await mkdtemp(path.join(os.tmpdir(), 'job-gate-test-'));
  root = path.join(dir, 'artifacts');
  approvalsPath = path.join(dir, 'approvals.json');
  await mkdir(root);
});

afterEach(async () => {
  await rm(dir, { recursive: true, force: true });
});

function validJob(overrides = {}) {
  const gate_artifacts = {};
  for (const g of BEFORE_RENDER) gate_artifacts[g] = `${g.toLowerCase()}.txt`;
  return {
    schema_version: 1,
    seed: 7,
    destinations: ['youtube'],
    template: 'explainer-basic',
    template_version: 1,
    voice_profile: null,
    scenes: [{ title: 'Intro', body: 'Hello world', seconds: 5 }],
    gate_artifacts,
    ...overrides,
  };
}

async function writeArtifacts(job) {
  for (const g of BEFORE_RENDER) {
    await writeFile(path.join(root, job.gate_artifacts[g]), `content for ${g}`);
  }
}

async function approve(job, gates) {
  for (const g of gates) {
    const full = path.join(root, job.gate_artifacts[g]);
    await recordApproval(approvalsPath, { gate: g, artifact: full, sha256: await hashArtifact(full), approvedBy: 'tester' });
  }
}

test('jobToPropsBody maps scenes to props scenes and uses the youtube fps', () => {
  const result = jobToPropsBody(validJob({ scenes: [{ title: 'A', body: 'B', seconds: 4 }] }));
  assert.equal(result.ok, true);
  assert.deepEqual(result.body, { fps: 30, scenes: [{ text: 'A', sub: 'B', seconds: 4 }] });
});

test('jobToPropsBody refuses shorts because the engine renders landscape only', () => {
  const result = jobToPropsBody(validJob({ destinations: ['shorts'] }));
  assert.equal(result.ok, false);
  assert.match(result.error, /shorts/);
});

test('jobToPropsBody refuses a job that names youtube and shorts together', () => {
  const result = jobToPropsBody(validJob({ destinations: ['youtube', 'shorts'] }));
  assert.equal(result.ok, false);
});

test('the job schema accepts gate_artifacts and rejects unknown gates and unsafe paths', async () => {
  assert.equal((await validateJob(validJob())).valid, true);
  assert.equal((await validateJob(validJob({ gate_artifacts: { G8: 'x.txt' } }))).valid, false);
  assert.equal((await validateJob(validJob({ gate_artifacts: { G1: '/etc/passwd' } }))).valid, false);
  assert.equal((await validateJob(validJob({ gate_artifacts: { G1: '..\\x' } }))).valid, false);
});

test('resolveGateArtifacts refuses a missing gate, a path outside the root, and a missing file', async () => {
  const job = validJob();
  await writeArtifacts(job);

  const noG3 = validJob();
  delete noG3.gate_artifacts.G3;
  assert.match((await resolveGateArtifacts(noG3, root)).error, /G3/);

  const escape = validJob();
  escape.gate_artifacts.G2 = '../outside.txt';
  assert.match((await resolveGateArtifacts(escape, root)).error, /inside ARTIFACT_DIR/);

  const missing = validJob();
  missing.gate_artifacts.G4 = 'nope.txt';
  assert.match((await resolveGateArtifacts(missing, root)).error, /G4 artifact not found/);
});

test('gateJob refuses with 403 and lists every gate when nothing is approved', async () => {
  const job = validJob();
  await writeArtifacts(job);
  const result = await gateJob(job, { artifactRoot: root, approvalsPath });
  assert.equal(result.ok, false);
  assert.equal(result.status, 403);
  assert.deepEqual(result.payload.gates, BEFORE_RENDER);
});

test('gateJob refuses when one earlier gate is missing and names only that gate', async () => {
  const job = validJob();
  await writeArtifacts(job);
  await approve(job, ['G1', 'G2', 'G3', 'G4', 'G5']);
  const result = await gateJob(job, { artifactRoot: root, approvalsPath });
  assert.equal(result.status, 403);
  assert.deepEqual(result.payload.gates, ['G6']);
});

test('gateJob opens the render once G1 to G6 are approved against their current artifacts', async () => {
  const job = validJob();
  await writeArtifacts(job);
  await approve(job, BEFORE_RENDER);
  const result = await gateJob(job, { artifactRoot: root, approvalsPath });
  assert.equal(result.ok, true);
  assert.equal(result.body.scenes[0].text, 'Intro');
});

test('an approval is void once its artifact changes', async () => {
  const job = validJob();
  await writeArtifacts(job);
  await approve(job, BEFORE_RENDER);
  await writeFile(path.join(root, job.gate_artifacts.G5), 'edited after approval');
  const result = await gateJob(job, { artifactRoot: root, approvalsPath });
  assert.equal(result.status, 403);
  assert.deepEqual(result.payload.gates, ['G5']);
});

test('gateJob returns 503 when the server has no artifact root or approvals file', async () => {
  const job = validJob();
  await writeArtifacts(job);
  assert.equal((await gateJob(job, { artifactRoot: '', approvalsPath })).status, 503);
  assert.equal((await gateJob(job, { artifactRoot: root, approvalsPath: '' })).status, 503);
});

test('gateJob returns 400 for an invalid job before touching any file', async () => {
  const result = await gateJob(validJob({ seed: -1 }), { artifactRoot: root, approvalsPath });
  assert.equal(result.status, 400);
  assert.equal(result.payload.error, 'invalid job');
});

test('unapprovedGates lists nothing when every gate matches', async () => {
  const job = validJob();
  await writeArtifacts(job);
  await approve(job, BEFORE_RENDER);
  const resolved = await resolveGateArtifacts(job, root);
  assert.deepEqual(unapprovedGates(await readApprovals(approvalsPath), resolved.artifacts), []);
});
