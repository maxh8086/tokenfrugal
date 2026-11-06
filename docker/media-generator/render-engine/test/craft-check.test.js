import { test } from 'node:test';
import assert from 'node:assert/strict';
import { checkScenes, CRAFT_RULES, toTimeline, applyCraftPolicy } from '../lib/craft-check.js';
import { validateProps } from '../lib/props.js';

// Runs the same path as POST /render: validate, build the timeline, check, then apply the policy.
function craftFor(body) {
  const checked = validateProps(body);
  assert.equal(checked.ok, true, checked.error);
  const timed = toTimeline(checked.props.scenes);
  const craft = checkScenes(timed);
  return { ...applyCraftPolicy(checked.hasScenes, craft.findings), findings: craft.findings };
}

test('toTimeline gives each scene its start time and read text', () => {
  const t = toTimeline([
    { text: 'A', sub: 'x', seconds: 1.5 },
    { text: 'B', sub: '', seconds: 2 },
  ]);
  assert.deepEqual(t.map((s) => [s.id, s.start, s.duration]), [
    ['scene-1', 0, 1.5],
    ['scene-2', 1.5, 2],
  ]);
  assert.equal(t[0].readText, 'A x');
});

test('title-only requests are not rejected: craft findings come back as warnings', () => {
  // 80 characters in 3 s is far above the read-speed limit, but a title-only request still succeeds.
  const r = craftFor({ title: 'x'.repeat(80), duration: 3 });
  assert.equal(r.reject, false);
  assert.ok(r.warnings.length > 0);
  assert.deepEqual(r.warnings.map((f) => f.rule), [CRAFT_RULES.READ_SPEED]);
});

test('title-only requests with no findings have an empty warnings array', () => {
  const r = craftFor({ title: 'Hello', duration: 3 });
  assert.deepEqual(r, { reject: false, warnings: [], findings: [] });
});

test('requests that send scenes are still rejected on a craft finding', () => {
  const r = craftFor({ scenes: [{ text: 'x'.repeat(80), seconds: 3 }] });
  assert.equal(r.reject, true);
  assert.deepEqual(r.findings.map((f) => f.rule), [CRAFT_RULES.READ_SPEED]);
  assert.deepEqual(r.warnings, []);
});

test('requests that send clean scenes are accepted with no warnings', () => {
  const r = craftFor({ scenes: [{ text: 'Hi', seconds: 3 }] });
  assert.deepEqual(r, { reject: false, warnings: [], findings: [] });
});

const ruleIds = (r) => r.findings.map((f) => f.rule);

test('READ_SPEED passes at 20 characters per second and fails above it', () => {
  // 40 non-space characters in 2 s = 20 per second: allowed.
  const ok = checkScenes([{ id: 'a', start: 0, duration: 2, readText: 'x'.repeat(40) }]);
  assert.equal(ok.ok, true);
  // 41 characters in 2 s is above 20 per second.
  const bad = checkScenes([{ id: 'a', start: 0, duration: 2, readText: 'x'.repeat(41) }]);
  assert.equal(bad.ok, false);
  assert.deepEqual(ruleIds(bad), [CRAFT_RULES.READ_SPEED]);
  assert.equal(bad.findings[0].scene, 'a');
});

test('READ_SPEED ignores whitespace', () => {
  const r = checkScenes([{ id: 'a', start: 0, duration: 2, readText: 'x '.repeat(20) }]);
  assert.equal(r.ok, true);
});

test('MIN_EXPOSURE passes at 0.83 s and fails below it', () => {
  const ok = checkScenes([{ id: 'a', start: 0, duration: 0.83, readText: 'hi' }]);
  assert.equal(ok.ok, true);
  const bad = checkScenes([{ id: 'a', start: 0, duration: 0.8, readText: 'hi' }]);
  assert.equal(bad.ok, false);
  assert.deepEqual(ruleIds(bad), [CRAFT_RULES.MIN_EXPOSURE]);
});

test('CUT_BUDGET counts boundary cuts and fails when over 12 per 30 s', () => {
  // 30 s film, 12 allowed. 6 scenes give 5 boundary cuts; 7 internal cuts makes 12: allowed.
  const scenes = [0, 1, 2, 3, 4, 5].map((i) => ({ id: `s${i}`, start: i * 5, duration: 5, readText: 'hi' }));
  scenes[0].cuts = 7;
  assert.equal(checkScenes(scenes).ok, true);
  // One more internal cut makes 13: over budget.
  scenes[0].cuts = 8;
  const bad = checkScenes(scenes);
  assert.equal(bad.ok, false);
  assert.deepEqual(ruleIds(bad), [CRAFT_RULES.CUT_BUDGET]);
  assert.equal(bad.findings[0].scene, 'film');
});

test('LAST_SCENE passes at 5 s and fails above it', () => {
  const ok = checkScenes([
    { id: 'a', start: 0, duration: 4, readText: 'hi' },
    { id: 'b', start: 4, duration: 5, readText: 'hi' },
  ]);
  assert.equal(ok.ok, true);
  const bad = checkScenes([
    { id: 'a', start: 0, duration: 4, readText: 'hi' },
    { id: 'b', start: 4, duration: 5.5, readText: 'hi' },
  ]);
  assert.equal(bad.ok, false);
  assert.deepEqual(ruleIds(bad), [CRAFT_RULES.LAST_SCENE]);
  assert.equal(bad.findings[0].scene, 'b');
});

test('a clean film returns ok with no findings', () => {
  const r = checkScenes([{ id: 'only', start: 0, duration: 3, readText: 'Hello there' }]);
  assert.deepEqual(r, { ok: true, findings: [] });
});
