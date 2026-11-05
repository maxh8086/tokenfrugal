import { test } from 'node:test';
import assert from 'node:assert/strict';
import { presets, validateJob } from '../lib/job-schema.js';

function validJob(overrides = {}) {
  return {
    schema_version: 1,
    seed: 42,
    destinations: ['youtube'],
    template: 'explainer-basic',
    template_version: 1,
    voice_profile: null,
    scenes: [{ title: 'Intro', body: 'Hello world', seconds: 5 }],
    ...overrides,
  };
}

function withBody(body) {
  const job = validJob();
  job.scenes[0].body = body;
  return job;
}

test('a valid job passes', async () => {
  const result = await validateJob(validJob());
  assert.equal(result.valid, true);
  assert.deepEqual(result.errors, []);
});

test('schema_version 2 fails', async () => {
  const result = await validateJob(validJob({ schema_version: 2 }));
  assert.equal(result.valid, false);
  assert.ok(result.errors.length > 0);
});

test('an extra root key fails', async () => {
  const result = await validateJob(validJob({ extra: true }));
  assert.equal(result.valid, false);
});

test('empty scenes fails', async () => {
  const result = await validateJob(validJob({ scenes: [] }));
  assert.equal(result.valid, false);
});

test('duplicate destinations fail', async () => {
  const result = await validateJob(validJob({ destinations: ['youtube', 'youtube'] }));
  assert.equal(result.valid, false);
});

test('body of 120 characters passes and 121 fails', async () => {
  assert.equal((await validateJob(withBody('a'.repeat(120)))).valid, true);
  assert.equal((await validateJob(withBody('a'.repeat(121)))).valid, false);
});

test('seconds of 0 fails', async () => {
  const job = validJob();
  job.scenes[0].seconds = 0;
  assert.equal((await validateJob(job)).valid, false);
});

test('a non-integer seed fails', async () => {
  const result = await validateJob(validJob({ seed: 1.5 }));
  assert.equal(result.valid, false);
});

test('presets.shorts equals the expected dimensions', () => {
  assert.deepEqual({ ...presets.shorts }, { width: 1080, height: 1920, fps: 30 });
});
