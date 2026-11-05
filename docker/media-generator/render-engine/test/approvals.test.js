import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readdir, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  GATES,
  canOpen,
  hashArtifact,
  isApproved,
  readApprovals,
  recordApproval,
} from '../lib/approvals.js';

const ABC_SHA = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad';

let dir;

beforeEach(async () => {
  dir = await mkdtemp(path.join(os.tmpdir(), 'approvals-test-'));
});

afterEach(async () => {
  await rm(dir, { recursive: true, force: true });
});

test('hashArtifact matches the known SHA-256 of "abc"', async () => {
  const file = path.join(dir, 'abc.txt');
  await writeFile(file, 'abc');
  assert.equal(await hashArtifact(file), ABC_SHA);
});

test('readApprovals returns an empty list when the file is missing', async () => {
  const result = await readApprovals(path.join(dir, 'missing.json'));
  assert.deepEqual(result, { version: 1, approvals: [] });
});

test('recordApproval then readApprovals round-trips the entry', async () => {
  const approvalsPath = path.join(dir, 'approvals.json');
  const entry = await recordApproval(approvalsPath, {
    gate: 'G1',
    artifact: 'out/brief.md',
    sha256: ABC_SHA,
    approvedBy: 'vaibhav',
    approvedAt: '2026-11-06T10:00:00.000Z',
  });
  assert.deepEqual(entry, {
    gate: 'G1',
    artifact: 'out/brief.md',
    sha256: ABC_SHA,
    approvedBy: 'vaibhav',
    approvedAt: '2026-11-06T10:00:00.000Z',
  });
  const stored = await readApprovals(approvalsPath);
  assert.deepEqual(stored, { version: 1, approvals: [entry] });
  assert.equal(isApproved(stored, 'G1', 'out/brief.md', ABC_SHA), true);
  // The temp file is renamed away, so only the approvals file is left in the folder.
  assert.deepEqual(await readdir(dir), ['approvals.json']);
});

test('isApproved is false after the artifact content changes', async () => {
  const artifact = path.join(dir, 'brief.md');
  const approvalsPath = path.join(dir, 'approvals.json');
  await writeFile(artifact, 'abc');
  const sha = await hashArtifact(artifact);
  await recordApproval(approvalsPath, { gate: 'G1', artifact: 'brief.md', sha256: sha, approvedBy: 'vaibhav' });

  const before = await readApprovals(approvalsPath);
  assert.equal(isApproved(before, 'G1', 'brief.md', await hashArtifact(artifact)), true);

  await writeFile(artifact, 'abcd');
  const newSha = await hashArtifact(artifact);
  assert.notEqual(newSha, sha);
  assert.equal(isApproved(before, 'G1', 'brief.md', newSha), false);
});

test('recordApproval rejects an invalid gate', async () => {
  await assert.rejects(
    recordApproval(path.join(dir, 'a.json'), {
      gate: 'G8',
      artifact: 'x',
      sha256: ABC_SHA,
      approvedBy: 'vaibhav',
    }),
    /invalid gate/,
  );
});

test('recordApproval rejects an invalid sha256', async () => {
  const approvalsPath = path.join(dir, 'a.json');
  const base = { gate: 'G1', artifact: 'x', approvedBy: 'vaibhav' };
  await assert.rejects(recordApproval(approvalsPath, { ...base, sha256: ABC_SHA.toUpperCase() }), /sha256/);
  await assert.rejects(recordApproval(approvalsPath, { ...base, sha256: 'abc' }), /sha256/);
  await assert.rejects(recordApproval(approvalsPath, { ...base, sha256: undefined }), /sha256/);
});

test('readApprovals throws a clear error on a bad shape', async () => {
  const approvalsPath = path.join(dir, 'bad.json');
  await writeFile(approvalsPath, JSON.stringify({ version: 2, approvals: [] }));
  await assert.rejects(readApprovals(approvalsPath), /version/);
  await writeFile(approvalsPath, JSON.stringify({ version: 1, approvals: {} }));
  await assert.rejects(readApprovals(approvalsPath), /"approvals" array/);
});

test('canOpen is false until every earlier gate is approved', async () => {
  const approvalsPath = path.join(dir, 'approvals.json');
  const current = {
    G1: { artifact: 'g1.md', sha256: ABC_SHA },
    G2: { artifact: 'g2.md', sha256: ABC_SHA },
  };
  const lookup = (gate) => current[gate];

  assert.equal(GATES.length, 7);
  assert.equal(canOpen(await readApprovals(approvalsPath), 'G1', lookup), true);
  assert.equal(canOpen(await readApprovals(approvalsPath), 'G3', lookup), false);

  await recordApproval(approvalsPath, { gate: 'G1', artifact: 'g1.md', sha256: ABC_SHA, approvedBy: 'vaibhav' });
  assert.equal(canOpen(await readApprovals(approvalsPath), 'G3', lookup), false);

  await recordApproval(approvalsPath, { gate: 'G2', artifact: 'g2.md', sha256: ABC_SHA, approvedBy: 'vaibhav' });
  assert.equal(canOpen(await readApprovals(approvalsPath), 'G3', lookup), true);

  // An earlier artifact that changed voids its approval and blocks later gates.
  const changed = { ...current, G2: { artifact: 'g2.md', sha256: 'f'.repeat(64) } };
  assert.equal(canOpen(await readApprovals(approvalsPath), 'G3', (g) => changed[g]), false);
});
