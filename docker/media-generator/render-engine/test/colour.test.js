import { test } from 'node:test';
import assert from 'node:assert/strict';
import { COLOUR_TARGET, colourArgs, colourFailures } from '../lib/colour.js';

test('colourArgs tags bt709 and yuv420p and copies audio', () => {
  const args = colourArgs({ input: '/job/video.mp4', out: '/job/tagged.mp4' });
  const pairs = (flag) => args[args.indexOf(flag) + 1];
  assert.equal(pairs('-pix_fmt'), 'yuv420p');
  assert.equal(pairs('-colorspace'), 'bt709');
  assert.equal(pairs('-color_primaries'), 'bt709');
  assert.equal(pairs('-color_trc'), 'bt709');
  assert.equal(pairs('-c:a'), 'copy');
  assert.equal(args.at(-1), '/job/tagged.mp4');
});

test('colourArgs never lets the video stream be copied untagged', () => {
  const args = colourArgs({ input: 'a.mp4', out: 'b.mp4' });
  assert.equal(args[args.indexOf('-c:v') + 1], 'libx264');
});

test('colourFailures passes an ffprobe stream that matches the target', () => {
  assert.deepEqual(colourFailures({ ...COLOUR_TARGET }), []);
});

test('colourFailures names every mismatch and a missing tag', () => {
  const failures = colourFailures({ pix_fmt: 'yuv444p', color_space: 'bt709', color_primaries: 'bt709' });
  assert.equal(failures.length, 2);
  assert.match(failures[0], /pix_fmt is yuv444p/);
  assert.match(failures[1], /color_transfer is missing, expected bt709/);
});
