import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildContactSheetArgs, contactSheetFps } from '../lib/contact-sheet.js';

test('the sampling rate spreads 16 tiles over the whole film, capped at 1 fps', () => {
  assert.equal(contactSheetFps(8), 1);
  assert.equal(contactSheetFps(16), 1);
  assert.equal(contactSheetFps(60), 16 / 60);
  assert.throws(() => contactSheetFps(0), /seconds/);
  assert.throws(() => contactSheetFps(NaN), /seconds/);
});

test('builds a one-frame PNG tile with dense 1 fps sampling by default', () => {
  const args = buildContactSheetArgs({ input: '/work/renders/a.mp4', output: '/work/renders/a-sheet.png' });
  assert.deepEqual(args, [
    '-y', '-loglevel', 'error',
    '-i', '/work/renders/a.mp4',
    '-vf', 'fps=1,scale=320:-2,tile=4x4',
    '-frames:v', '1',
    '/work/renders/a-sheet.png',
  ]);
});

test('uses the given grid, width and sampling rate', () => {
  const args = buildContactSheetArgs({ input: 'in.mp4', output: 'out.png', cols: 5, rows: 3, frameWidth: 480, fps: 2 });
  assert.equal(args[args.indexOf('-vf') + 1], 'fps=2,scale=480:-2,tile=5x3');
});

test('rejects paths that could be read as ffmpeg options', () => {
  assert.throws(() => buildContactSheetArgs({ input: '-i', output: 'out.png' }), /input/);
  assert.throws(() => buildContactSheetArgs({ input: 'in.mp4', output: '' }), /output/);
});

test('rejects grid, width and fps outside the allowed range', () => {
  assert.throws(() => buildContactSheetArgs({ input: 'a', output: 'b', cols: 0 }), /cols/);
  assert.throws(() => buildContactSheetArgs({ input: 'a', output: 'b', rows: 17 }), /rows/);
  assert.throws(() => buildContactSheetArgs({ input: 'a', output: 'b', frameWidth: 321 }), /frameWidth/);
  assert.throws(() => buildContactSheetArgs({ input: 'a', output: 'b', frameWidth: 2000 }), /frameWidth/);
  assert.throws(() => buildContactSheetArgs({ input: 'a', output: 'b', fps: 0 }), /fps/);
  assert.throws(() => buildContactSheetArgs({ input: 'a', output: 'b', fps: 31 }), /fps/);
});
