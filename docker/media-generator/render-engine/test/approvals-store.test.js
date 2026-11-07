import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readdir, readFile, rm, writeFile, mkdir } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  canOpen,
  isApproved,
  migrateLegacyApprovals,
  readApprovals,
  recordApproval,
} from '../lib/approvals.js';

const SHA = 'a'.repeat(64);
let dir;

beforeEach(async () => {
  dir = await mkdtemp(path.join(os.tmpdir(), 'approvals-store-'));
});

afterEach(async () => {
  await rm(dir, { recursive: true, force: true });
});

test('a folder path writes one file per gate and reads them back', async () => {
  const store = path.join(dir, 'approvals');
  await recordApproval(store, { gate: 'G1', artifact: '/a/g1.md', sha256: SHA, approvedBy: 'vaibhav' });
  await recordApproval(store, { gate: 'G2', artifact: '/a/g2.md', sha256: SHA, approvedBy: 'vaibhav' });
  assert.deepEqual((await readdir(store)).sort(), ['G1.json', 'G2.json']);
  const stored = JSON.parse(await readFile(path.join(store, 'G1.json'), 'utf8'));
  assert.equal(stored.gate, 'G1');
  assert.equal(stored.human, true);
  const read = await readApprovals(store);
  assert.deepEqual(read.approvals.map((e) => e.gate), ['G1', 'G2']);
});

test('a second approval for a gate replaces the first', async () => {
  const store = path.join(dir, 'approvals');
  await recordApproval(store, { gate: 'G1', artifact: '/a/g1.md', sha256: SHA, approvedBy: 'alice' });
  await recordApproval(store, { gate: 'G1', artifact: '/a/g1.md', sha256: 'b'.repeat(64), approvedBy: 'bob' });
  const read = await readApprovals(store);
  assert.equal(read.approvals.length, 1);
  assert.equal(read.approvals[0].approvedBy, 'bob');
});

test('a missing folder reads as no approvals', async () => {
  assert.deepEqual(await readApprovals(path.join(dir, 'none')), { version: 1, approvals: [] });
});

test('a gate file without the human flag is ignored, so the gate stays closed', async () => {
  const store = path.join(dir, 'approvals');
  await mkdir(store);
  await writeFile(path.join(store, 'G1.json'), JSON.stringify({ gate: 'G1', artifact: '/a', sha256: SHA }));
  assert.deepEqual((await readApprovals(store)).approvals, []);
});

test('a gate file that names a different gate is refused', async () => {
  const store = path.join(dir, 'approvals');
  await mkdir(store);
  await writeFile(path.join(store, 'G1.json'), JSON.stringify({ gate: 'G2', human: true }));
  await assert.rejects(readApprovals(store), /names gate "G2"; expected G1/);
});

test('a malformed gate file is refused with its path', async () => {
  const store = path.join(dir, 'approvals');
  await mkdir(store);
  await writeFile(path.join(store, 'G3.json'), '{not json');
  await assert.rejects(readApprovals(store), /G3\.json is not valid JSON/);
});

test('a hash change voids the per-gate approval', async () => {
  const store = path.join(dir, 'approvals');
  await recordApproval(store, { gate: 'G1', artifact: '/a/g1.md', sha256: SHA, approvedBy: 'vaibhav' });
  const read = await readApprovals(store);
  assert.equal(isApproved(read, 'G1', '/a/g1.md', SHA), true);
  assert.equal(isApproved(read, 'G1', '/a/g1.md', 'c'.repeat(64)), false);
  const lookup = (g) => (g === 'G1' ? { artifact: '/a/g1.md', sha256: 'c'.repeat(64) } : null);
  assert.equal(canOpen(read, 'G2', lookup), false);
});

test('the legacy single .json file still round-trips', async () => {
  const legacy = path.join(dir, 'approvals.json');
  await recordApproval(legacy, { gate: 'G1', artifact: '/a/g1.md', sha256: SHA, approvedBy: 'vaibhav' });
  assert.deepEqual((await readdir(dir)), ['approvals.json']);
  assert.equal((await readApprovals(legacy)).approvals.length, 1);
});

test('migrateLegacyApprovals keeps the newest approval per gate in the folder', async () => {
  const legacy = path.join(dir, 'approvals.json');
  await recordApproval(legacy, { gate: 'G1', artifact: '/a/g1.md', sha256: SHA, approvedBy: 'alice' });
  await recordApproval(legacy, { gate: 'G1', artifact: '/a/g1.md', sha256: 'b'.repeat(64), approvedBy: 'bob' });
  await recordApproval(legacy, { gate: 'G2', artifact: '/a/g2.md', sha256: SHA, approvedBy: 'alice' });
  const store = path.join(dir, 'approvals');
  const written = await migrateLegacyApprovals(legacy, store);
  assert.deepEqual(written, ['G1', 'G2']);
  const read = await readApprovals(store);
  assert.equal(read.approvals.find((e) => e.gate === 'G1').approvedBy, 'bob');
  assert.equal(read.approvals.every((e) => e.human === true), true);
  assert.equal((await readApprovals(legacy)).approvals.length, 3, 'legacy file is left in place');
});

test('migration refuses a folder source and a .json target', async () => {
  await assert.rejects(migrateLegacyApprovals(path.join(dir, 'x'), path.join(dir, 'y')), /legacy .json/);
  await assert.rejects(migrateLegacyApprovals(path.join(dir, 'x.json'), path.join(dir, 'y.json')), /folder/);
});
