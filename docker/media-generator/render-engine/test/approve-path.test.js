import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { hashArtifact, recordApproval, resolveApprovalArtifact } from '../lib/approvals.js';
import { gateJob } from '../lib/job-gate.js';

const execFileAsync = promisify(execFile);
const APPROVE = fileURLToPath(new URL('../bin/approve.js', import.meta.url));
const BEFORE_RENDER = ['G1', 'G2', 'G3', 'G4', 'G5', 'G6'];

let dir;
let root;
let approvalsPath;

beforeEach(async () => {
  dir = await mkdtemp(path.join(os.tmpdir(), 'approve-path-test-'));
  root = path.join(dir, 'artifacts');
  approvalsPath = path.join(dir, 'approvals.json');
  await mkdir(root);
});

afterEach(async () => {
  await rm(dir, { recursive: true, force: true });
});

function job() {
  const gate_artifacts = {};
  for (const g of BEFORE_RENDER) gate_artifacts[g] = `${g.toLowerCase()}.txt`;
  return {
    schema_version: 1,
    seed: 3,
    destinations: ['youtube'],
    template: 'explainer-basic',
    template_version: 1,
    voice_profile: null,
    scenes: [{ title: 'Intro', body: 'Hello', seconds: 4 }],
    gate_artifacts,
  };
}

async function writeAll(j) {
  for (const g of BEFORE_RENDER) await writeFile(path.join(root, j.gate_artifacts[g]), `text ${g}`);
}

test('resolveApprovalArtifact returns an absolute path for a relative input', () => {
  const result = resolveApprovalArtifact('story.txt', '');
  assert.equal(result.ok, true);
  assert.equal(path.isAbsolute(result.path), true);
  assert.equal(result.path, path.resolve('story.txt'));
});

test('resolveApprovalArtifact refuses a file outside ARTIFACT_DIR', () => {
  const result = resolveApprovalArtifact(path.join(dir, 'elsewhere.txt'), root);
  assert.equal(result.ok, false);
  assert.match(result.error, /outside ARTIFACT_DIR/);
});

test('resolveApprovalArtifact accepts a file inside ARTIFACT_DIR and refuses a sibling with a shared prefix', () => {
  assert.equal(resolveApprovalArtifact(path.join(root, 'g1.txt'), root).ok, true);
  assert.equal(resolveApprovalArtifact(path.join(dir, 'artifacts-evil', 'x.txt'), root).ok, false);
});

test('approve.js records an absolute path for a relative input, run from ARTIFACT_DIR', async () => {
  const file = path.join(root, 'g1.txt');
  await writeFile(file, 'hello');
  const { stdout } = await execFileAsync(process.execPath, [APPROVE, approvalsPath, 'G1', 'g1.txt', 'alice'], {
    cwd: root,
    env: { ...process.env, ARTIFACT_DIR: root },
  });
  const entry = JSON.parse(stdout);
  assert.equal(entry.artifact, file);
  assert.equal(entry.sha256, await hashArtifact(file));
});

test('approve.js with no approver name records the requestor, with no named person', async () => {
  const file = path.join(root, 'g1.txt');
  await writeFile(file, 'hello');
  const { stdout } = await execFileAsync(process.execPath, [APPROVE, approvalsPath, 'G1', file], {
    env: { ...process.env, ARTIFACT_DIR: root },
  });
  const entry = JSON.parse(stdout);
  assert.equal(entry.approvedBy, 'requestor');
  assert.equal(entry.sha256, await hashArtifact(file));
});

test('approve.js refuses a file outside ARTIFACT_DIR and records nothing', async () => {
  const outside = path.join(dir, 'outside.txt');
  await writeFile(outside, 'x');
  await assert.rejects(
    execFileAsync(process.execPath, [APPROVE, approvalsPath, 'G1', outside, 'alice'], {
      env: { ...process.env, ARTIFACT_DIR: root },
    }),
    (err) => /outside ARTIFACT_DIR/.test(err.stderr),
  );
  await assert.rejects(readFile(approvalsPath, 'utf8'), (err) => err.code === 'ENOENT');
});

test('a 403 names the path mismatch when the hash matches an approval recorded under another path', async () => {
  const j = job();
  await writeAll(j);
  for (const g of BEFORE_RENDER) {
    const full = path.join(root, j.gate_artifacts[g]);
    // Record a relative path for each approval: the hash is right, the path is not what the server expects.
    await recordApproval(approvalsPath, {
      gate: g, artifact: j.gate_artifacts[g], sha256: await hashArtifact(full), approvedBy: 'alice',
    });
  }
  const result = await gateJob(j, { artifactRoot: root, approvalsPath });
  assert.equal(result.status, 403);
  assert.equal(result.payload.error, 'approval recorded for a different path');
  assert.equal(result.payload.mismatched.length, BEFORE_RENDER.length);
  assert.equal(result.payload.mismatched[0].gate, 'G1');
  assert.equal(result.payload.mismatched[0].recordedPath, 'g1.txt');
});

test('a 403 keeps the plain message when there is no approval at all', async () => {
  const j = job();
  await writeAll(j);
  const result = await gateJob(j, { artifactRoot: root, approvalsPath });
  assert.equal(result.payload.error, 'gates not approved');
  assert.equal(result.payload.mismatched, undefined);
});
