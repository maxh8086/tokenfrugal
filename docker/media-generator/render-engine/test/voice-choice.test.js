import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { checkVoiceChoice } from '../lib/voice-choice.js';
import { gateJob } from '../lib/job-gate.js';

const BEFORE_RENDER = ['G1', 'G2', 'G3', 'G4', 'G5', 'G6'];

let dir;
let root;
let approvalsPath;

beforeEach(async () => {
  dir = await mkdtemp(path.join(os.tmpdir(), 'voice-choice-test-'));
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

test('a null narration voice is accepted and means the service default voice', () => {
  assert.deepEqual(checkVoiceChoice({ voice_profile: null }), { ok: true, voice: null });
});

test('an absent narration voice is accepted and means the service default voice', () => {
  assert.deepEqual(checkVoiceChoice({}), { ok: true, voice: null });
});

test('a Kokoro voice name is accepted and returned unchanged', () => {
  assert.deepEqual(checkVoiceChoice({ voice_profile: 'af_heart' }), { ok: true, voice: 'af_heart' });
  assert.deepEqual(checkVoiceChoice({ voice_profile: 'bm_george' }), { ok: true, voice: 'bm_george' });
});

test('a voice name with digits after the prefix is accepted', () => {
  assert.deepEqual(checkVoiceChoice({ voice_profile: 'af_sky2' }), { ok: true, voice: 'af_sky2' });
});

test('an empty narration voice is refused', () => {
  const r = checkVoiceChoice({ voice_profile: '' });
  assert.equal(r.ok, false);
  assert.match(r.error, /narration voice/);
});

test('an uppercase narration voice is refused', () => {
  const r = checkVoiceChoice({ voice_profile: 'Af_Heart' });
  assert.equal(r.ok, false);
  assert.match(r.error, /narration voice/);
});

test('a narration voice with spaces is refused', () => {
  const r = checkVoiceChoice({ voice_profile: 'Bad Voice!' });
  assert.equal(r.ok, false);
  assert.match(r.error, /narration voice/);
});

test('a narration voice with no name after the underscore is refused', () => {
  const r = checkVoiceChoice({ voice_profile: 'af_' });
  assert.equal(r.ok, false);
  assert.match(r.error, /narration voice/);
});

test('a path-like narration voice is refused', () => {
  const r = checkVoiceChoice({ voice_profile: '../x' });
  assert.equal(r.ok, false);
  assert.match(r.error, /narration voice/);
});

test('a numeric narration voice is refused', () => {
  const r = checkVoiceChoice({ voice_profile: 42 });
  assert.equal(r.ok, false);
  assert.match(r.error, /narration voice/);
});

test('gateJob refuses a job with a bad narration voice with 400 and the voice error, before any artifact is read', async () => {
  // No artifact files are written, so a voice check that ran after artifact resolution would fail differently.
  const result = await gateJob(validJob({ voice_profile: 'Bad Voice!' }), { artifactRoot: root, approvalsPath });
  assert.equal(result.ok, false);
  assert.equal(result.status, 400);
  assert.equal(typeof result.payload.error, 'string');
  assert.match(result.payload.error, /narration voice/);
  assert.equal(result.payload.findings, undefined);
});

test('gateJob does not refuse a job with a good narration voice on voice grounds', async () => {
  // Artifacts are absent, so the gate check fails with 400 and not on voice grounds.
  const result = await gateJob(validJob({ voice_profile: 'af_heart' }), { artifactRoot: root, approvalsPath });
  assert.equal(result.status, 400);
  assert.doesNotMatch(result.payload.error, /narration voice/);
});
