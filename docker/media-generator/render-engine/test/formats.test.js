import { test } from 'node:test';
import assert from 'node:assert/strict';
import { FORMAT_IDS, FORMATS, checkFormat } from '../lib/formats.js';
import { validateJob } from '../lib/job-schema.js';

function job(overrides = {}, seconds = 5) {
  return {
    schema_version: 1,
    seed: 42,
    destinations: ['youtube'],
    template: 'explainer-basic',
    template_version: 1,
    voice_profile: null,
    scenes: [{ title: 'Intro', body: 'Hello world', seconds }],
    ...overrides,
  };
}

test('the nine D27 formats are registered', () => {
  assert.equal(FORMAT_IDS.length, 9);
  for (const id of FORMAT_IDS) assert.ok(FORMATS[id].label, id);
});

test('a job without a format keeps today behaviour', () => {
  assert.deepEqual(checkFormat(job()), { ok: true, total: null });
});

test('a 1920x1080 format within its length renders and reports the total', () => {
  assert.deepEqual(checkFormat(job({ format: 'video' }, 120)), { ok: true, total: 120 });
});

test('a format refuses a job longer than its maximum length', () => {
  const r = checkFormat(job({ format: 'youtube-short' }, 200));
  assert.equal(r.ok, false);
  assert.match(r.error, /at most 180 seconds; the job runs 200 seconds/);
});

test('a 1080x1920 format renders when the job names the shorts destination', () => {
  assert.deepEqual(checkFormat({ ...job({ format: 'youtube-short' }, 10), destinations: ['shorts'] }), { ok: true, total: 10 });
});

test('a 1080x1920 format is refused when the job names a different destination', () => {
  const r = checkFormat(job({ format: 'youtube-short' }, 10));
  assert.equal(r.ok, false);
  assert.match(r.error, /renders as shorts; name shorts as the job destination/);
});

test('a format whose size is not built is refused even when the length fits', () => {
  const r = checkFormat(job({ format: 'instagram-post' }, 10));
  assert.equal(r.ok, false);
  assert.match(r.error, /1080x1350 at 30 fps\) is not rendered yet/);
});

test('Facebook Reel has no fixed length, so only the size check applies', () => {
  assert.equal(checkFormat(job({ format: 'facebook-reel' }, 100000)).ok, false);
});

test('an unknown format id is refused', () => {
  assert.equal(checkFormat(job({ format: 'tiktok' })).ok, false);
});

test('the job schema accepts a listed format and rejects an unlisted one', async () => {
  assert.equal((await validateJob(job({ format: 'linkedin-post' }))).valid, true);
  assert.equal((await validateJob(job({ format: 'tiktok' }))).valid, false);
});
