import { test } from 'node:test';
import assert from 'node:assert/strict';
import { concatListText, coversDuration, planSegments, segmentIsValid } from '../lib/segments.js';

test('planSegments: one span per scene, clamped to the duration', () => {
  const scenes = [{ start: 0, seconds: 2 }, { start: 2, seconds: 3 }, { start: 5, seconds: 4 }];
  assert.deepEqual(planSegments(scenes, 8), [
    { index: 0, start: 0, end: 2 },
    { index: 1, start: 2, end: 5 },
    { index: 2, start: 5, end: 8 },
  ]);
});

test('planSegments: drops spans that are empty or start after the duration', () => {
  const scenes = [{ start: 0, seconds: 0 }, { start: 1, seconds: 1 }, { start: 9, seconds: 2 }];
  assert.deepEqual(planSegments(scenes, 5), [{ index: 0, start: 1, end: 2 }]);
});

test('planSegments: rounds to 3 decimals', () => {
  assert.deepEqual(planSegments([{ start: 0.1234, seconds: 1.00049 }], 10), [
    { index: 0, start: 0.123, end: 1.124 },
  ]);
});

test('planSegments: no scenes gives one span over the whole duration', () => {
  assert.deepEqual(planSegments([], 8), [{ index: 0, start: 0, end: 8 }]);
});

test('concatListText: one line per file, quotes escaped', () => {
  assert.equal(
    concatListText(['/a/b.mp4', "/c/it's.mp4"]),
    "file '/a/b.mp4'\nfile '/c/it'\\''s.mp4'\n",
  );
});

test('segmentIsValid: true only for a non-empty file', () => {
  assert.equal(segmentIsValid({ size: 10 }), true);
  assert.equal(segmentIsValid({ size: 0 }), false);
  assert.equal(segmentIsValid(null), false);
});

test('coversDuration: true for contiguous spans from 0 to duration', () => {
  assert.equal(coversDuration([{ start: 0, end: 2 }, { start: 2, end: 5 }], 5), true);
});

test('coversDuration: false for a leading gap', () => {
  assert.equal(coversDuration([{ start: 0.5, end: 2 }, { start: 2, end: 5 }], 5), false);
});

test('coversDuration: false for a gap between spans', () => {
  assert.equal(coversDuration([{ start: 0, end: 2 }, { start: 2.5, end: 5 }], 5), false);
});

test('coversDuration: false when the last span ends before duration', () => {
  assert.equal(coversDuration([{ start: 0, end: 2 }, { start: 2, end: 4 }], 5), false);
});

test('coversDuration: false for an empty array', () => {
  assert.equal(coversDuration([], 5), false);
});
