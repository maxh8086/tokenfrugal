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

// 10 x 10 frame; `mask(p)` is true for pixels that strobe black/white every 5 frames.
function maskedStrobe(mask, frames = 60) {
  const out = [];
  for (let i = 0; i < frames; i++) {
    const level = Math.floor(i / 5) % 2 === 0 ? 0 : 255;
    const rgba = new Uint8Array(100 * 4);
    for (let p = 0; p < 100; p++) {
      const v = mask(p) ? level : 128;
      rgba[p * 4] = v;
      rgba[p * 4 + 1] = v;
      rgba[p * 4 + 2] = v;
      rgba[p * 4 + 3] = 255;
    }
    out.push({ width: 10, height: 10, rgba });
  }
  return out;
}

test('strobe over 11% of the frame has too many flashes but passes on area', () => {
  const frames = maskedStrobe((p) => p < 11);
  const result = checkFlashes(frames, 30);
  assert.ok(result.maxInOneSecond > 3, `expected > 3 frame flashes, got ${result.maxInOneSecond}`);
  assert.ok(result.maxAreaFraction <= result.areaLimitFraction, `area ${result.maxAreaFraction}`);
  assert.equal(result.pass, true);
});

test('strobe over half the frame fails both the count and the area rules', () => {
  const frames = maskedStrobe((p) => p < 50);
  const result = checkFlashes(frames, 30);
  assert.ok(result.maxInOneSecond > 3);
  assert.ok(result.maxAreaFraction > result.areaLimitFraction, `area ${result.maxAreaFraction}`);
  assert.equal(result.pass, false);
});

test('red and green strobe is counted as red flashes and fails', () => {
  const frames = [];
  for (let i = 0; i < 60; i++) {
    const red = Math.floor(i / 5) % 2 === 0;
    const rgba = new Uint8Array(16 * 4);
    for (let p = 0; p < 16; p++) {
      rgba[p * 4] = red ? 255 : 0;
      rgba[p * 4 + 1] = red ? 0 : 255;
      rgba[p * 4 + 2] = 0;
      rgba[p * 4 + 3] = 255;
    }
    frames.push({ width: 4, height: 4, rgba });
  }
  const result = checkFlashes(frames, 30);
  assert.ok(result.maxRedInOneSecond > 3, `expected > 3 red flashes, got ${result.maxRedInOneSecond}`);
  assert.equal(result.pass, false);
});
