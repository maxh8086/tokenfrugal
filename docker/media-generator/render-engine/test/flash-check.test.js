import { test } from 'node:test';
import assert from 'node:assert/strict';
import { checkFlashes } from '../lib/flash-check.js';

function solidFrame(level) {
  const rgba = new Uint8Array(4 * 4 * 4);
  for (let p = 0; p < 16; p++) {
    rgba[p * 4] = level;
    rgba[p * 4 + 1] = level;
    rgba[p * 4 + 2] = level;
    rgba[p * 4 + 3] = 255;
  }
  return { width: 4, height: 4, rgba };
}

test('static clip of 60 frames at one level has no flashes', () => {
  const frames = Array.from({ length: 60 }, () => solidFrame(128));
  const result = checkFlashes(frames, 30);
  assert.equal(result.pass, true);
  assert.equal(result.flashes, 0);
  assert.equal(result.maxInOneSecond, 0);
});

test('black, white, black within one second passes', () => {
  const frames = [];
  for (let i = 0; i < 60; i++) {
    let level = 0;
    if (i >= 10 && i < 20) level = 255;
    frames.push(solidFrame(level));
  }
  const result = checkFlashes(frames, 30);
  assert.equal(result.pass, true);
  assert.equal(result.flashes, 1);
  assert.equal(result.maxInOneSecond, 1);
});

test('strobe alternating black and white every 5 frames fails', () => {
  const frames = [];
  for (let i = 0; i < 60; i++) {
    frames.push(solidFrame(Math.floor(i / 5) % 2 === 0 ? 0 : 255));
  }
  const result = checkFlashes(frames, 30);
  assert.equal(result.pass, false);
  assert.ok(result.maxInOneSecond > 3, `expected > 3, got ${result.maxInOneSecond}`);
});
