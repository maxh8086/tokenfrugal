import { test } from 'node:test';
import assert from 'node:assert/strict';
import { planParts, totalSeconds, PART_MAX_SECONDS, PART_MAX_SCENES } from '../lib/job-parts.js';

const scenes = (n, seconds) => Array.from({ length: n }, () => ({ seconds }));

test('a job within the limits is one part', () => {
  assert.deepEqual(planParts(scenes(3, 8)), [[0, 3]]);
});

test('parts cover every scene once, in order, and each part stays within both limits', () => {
  const input = scenes(25, 8); // 200 s, 25 scenes
  const parts = planParts(input);
  assert.equal(parts[0][0], 0);
  assert.equal(parts[parts.length - 1][1], input.length);
  for (let k = 1; k < parts.length; k++) assert.equal(parts[k][0], parts[k - 1][1]);
  for (const [a, b] of parts) {
    assert.ok(b - a <= PART_MAX_SCENES, `part ${a}-${b} has too many scenes`);
    assert.ok(totalSeconds(input.slice(a, b)) <= PART_MAX_SECONDS, `part ${a}-${b} is too long`);
  }
});

test('a part closes when the next scene would exceed the seconds limit', () => {
  // 7 scenes of 8 s = 56 s fit; the 8th would make 64 s, so it starts a new part.
  assert.deepEqual(planParts(scenes(8, 8)), [[0, 7], [7, 8]]);
});

test('a part closes at the scene count limit', () => {
  // 12 scenes of 1 s: 10 scenes per part.
  assert.deepEqual(planParts(scenes(12, 1)), [[0, 10], [10, 12]]);
});

test('empty input gives no parts; a scene over the part limit is refused', () => {
  assert.deepEqual(planParts([]), []);
  assert.throws(() => planParts([{ seconds: 61 }]), /at most 60 s/);
});
