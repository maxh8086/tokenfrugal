import { test } from 'node:test';
import assert from 'node:assert/strict';
import { flashFailure } from '../lib/flash-preflight.js';

const findings = [{ pass: false, flashes: 5, maxInOneSecond: 5 }];

test('flashFailure returns null when enforcement is off', () => {
  assert.equal(flashFailure({ enforce: false, findings }), null);
  assert.equal(flashFailure({ enforce: undefined, findings }), null);
});

test('flashFailure returns null when enforced with no findings', () => {
  assert.equal(flashFailure({ enforce: true, findings: [] }), null);
});

test('flashFailure returns the 422 object when enforced with findings', () => {
  assert.deepEqual(flashFailure({ enforce: true, findings }), {
    status: 422,
    stage: 'flash',
    message: 'Render blocked: the video fails the WCAG 2.3.1 flash check.',
    findings,
  });
});
