import { test } from 'node:test';
import assert from 'node:assert/strict';
import { jobOutputRel, jobOutputUrl, JOB_PRESETS } from '../lib/job-output.js';

test('a job preset file sits in the job folder', () => {
  assert.equal(jobOutputRel('abc-123', 'youtube'), 'abc-123/youtube.mp4');
  assert.equal(jobOutputUrl('abc-123', 'youtube'), '/output/abc-123/youtube.mp4');
});

test('the youtube preset is the only one for now (shorts is refused upstream)', () => {
  assert.deepEqual(JOB_PRESETS, ['youtube']);
});

test('a job id that could escape the output folder is refused', () => {
  for (const bad of ['../x', 'a/b', 'a\\b', '', '.', 'a b', 'x'.repeat(65), null, 7]) {
    assert.throws(() => jobOutputRel(bad, 'youtube'), /bad job id/, `id ${JSON.stringify(bad)}`);
  }
});

test('an unknown preset is refused', () => {
  assert.throws(() => jobOutputRel('abc', 'shorts'), /unknown output preset/);
  assert.throws(() => jobOutputRel('abc', '../youtube'), /unknown output preset/);
});
