import { test } from 'node:test';
import assert from 'node:assert/strict';
import { jobOutputRel, jobOutputUrl, jobContactSheetRel, jobContactSheetUrl, JOB_PRESETS } from '../lib/job-output.js';

test('the contact sheet sits beside the preset file in the job folder', () => {
  assert.equal(jobContactSheetRel('abc-123'), 'abc-123/contact.png');
  assert.equal(jobContactSheetUrl('abc-123'), '/output/abc-123/contact.png');
  assert.throws(() => jobContactSheetRel('../x'), /bad job id/);
});

test('a job preset file sits in the job folder', () => {
  assert.equal(jobOutputRel('abc-123', 'youtube'), 'abc-123/youtube.mp4');
  assert.equal(jobOutputUrl('abc-123', 'youtube'), '/output/abc-123/youtube.mp4');
});

test('the job presets are youtube and shorts (one destination per job, see job-gate.js)', () => {
  assert.deepEqual(JOB_PRESETS, ['youtube', 'shorts']);
});

test('a job id that could escape the output folder is refused', () => {
  for (const bad of ['../x', 'a/b', 'a\\b', '', '.', 'a b', 'x'.repeat(65), null, 7]) {
    assert.throws(() => jobOutputRel(bad, 'youtube'), /bad job id/, `id ${JSON.stringify(bad)}`);
  }
});

test('an unknown preset is refused', () => {
  assert.equal(jobOutputRel('abc', 'shorts'), 'abc/shorts.mp4');
  assert.throws(() => jobOutputRel('abc', '../youtube'), /unknown output preset/);
});
