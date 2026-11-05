import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateProps, propsToJs, echoProps, DEFAULTS } from '../lib/props.js';

test('empty body uses defaults', () => {
  const r = validateProps({});
  assert.equal(r.ok, true);
  assert.deepEqual(r.props, DEFAULTS);
});

test('valid fields override defaults and title is trimmed', () => {
  const r = validateProps({ title: '  Ship it  ', accent: '#fff', subtitle: 'Now' });
  assert.equal(r.ok, true);
  assert.equal(r.props.title, 'Ship it');
  assert.equal(r.props.accent, '#fff');
  assert.equal(r.props.subtitle, 'Now');
});

test('unknown fields are rejected', () => {
  const r = validateProps({ titel: 'typo' });
  assert.equal(r.ok, false);
  assert.match(r.error, /unknown field: titel/);
});

test('non-object bodies are rejected', () => {
  assert.equal(validateProps([]).ok, false);
  assert.equal(validateProps('text').ok, false);
});

test('title must be non-empty and within the length limit', () => {
  assert.equal(validateProps({ title: '   ' }).ok, false);
  assert.equal(validateProps({ title: 'x'.repeat(81) }).ok, false);
  assert.equal(validateProps({ title: 'x'.repeat(80) }).ok, true);
});

test('duration is optional and limited to 3 to 60 seconds', () => {
  assert.equal(validateProps({}).props.duration, 3);
  assert.equal(validateProps({ duration: 30 }).props.duration, 30);
  for (const bad of [2, 61, '30', NaN]) {
    assert.equal(validateProps({ duration: bad }).ok, false, String(bad));
  }
});

test('colours must be 3 or 6 digit hex', () => {
  for (const bad of ['red', '#12345', '#GGGGGG', 'rgb(0,0,0)', 42]) {
    assert.equal(validateProps({ background: bad }).ok, false, String(bad));
  }
  assert.equal(validateProps({ background: '#0d1117' }).ok, true);
});

test('fps defaults to 60 and accepts only 24, 30 or 60', () => {
  assert.equal(validateProps({}).props.fps, 60);
  assert.equal(validateProps({ fps: 24 }).props.fps, 24);
  assert.equal(validateProps({ fps: 30 }).props.fps, 30);
  for (const bad of [25, '60', 0, null]) {
    assert.equal(validateProps({ fps: bad }).ok, false, String(bad));
  }
});

test('without scenes, the title becomes a single scene', () => {
  const r = validateProps({ title: 'One', subtitle: 'Two', duration: 5 });
  assert.equal(r.ok, true);
  assert.deepEqual(r.props.scenes, [{ text: 'One', sub: 'Two', seconds: 5 }]);
});

test('scenes set duration to the rounded sum and skip title', () => {
  const r = validateProps({
    scenes: [
      { text: ' First ', sub: 'a', seconds: 1.111 },
      { text: 'Second', seconds: 2.5 },
    ],
  });
  assert.equal(r.ok, true);
  assert.equal(r.props.duration, 3.61);
  assert.deepEqual(r.props.scenes, [
    { text: 'First', sub: 'a', seconds: 1.111 },
    { text: 'Second', sub: '', seconds: 2.5 },
  ]);
});

test('scenes and title together are rejected', () => {
  const r = validateProps({ title: 'x', scenes: [{ text: 'y', seconds: 3 }] });
  assert.equal(r.ok, false);
  assert.equal(r.error, 'use either scenes or title');
});

test('scenes are limited in count, length, seconds, total and keys', () => {
  const one = (extra) => ({ text: 'hi', seconds: 3, ...extra });
  assert.equal(validateProps({ scenes: [] }).ok, false);
  assert.equal(validateProps({ scenes: Array.from({ length: 11 }, () => one()) }).ok, false);
  assert.equal(validateProps({ scenes: [one({ text: '' })] }).ok, false);
  assert.equal(validateProps({ scenes: [one({ text: 'x'.repeat(81) })] }).ok, false);
  assert.equal(validateProps({ scenes: [one({ sub: 'x'.repeat(121) })] }).ok, false);
  assert.equal(validateProps({ scenes: [one({ seconds: 0.82 })] }).ok, false);
  assert.equal(validateProps({ scenes: [one({ seconds: 8.01 })] }).ok, false);
  assert.equal(validateProps({ scenes: [one({ colour: 'red' })] }).ok, false);
  // Eight scenes of 8 s is 64 s: over the 60 s total.
  const long = Array.from({ length: 8 }, () => one({ seconds: 8 }));
  assert.equal(validateProps({ scenes: long }).ok, false);
  const fits = Array.from({ length: 7 }, () => one({ seconds: 8 }));
  assert.equal(validateProps({ scenes: fits }).ok, true);
});

test('propsToJs escapes angle brackets so a value cannot close a script tag', () => {
  const js = propsToJs({ title: '</script><b>x</b>' });
  assert.ok(!js.includes('</script>'));
  assert.ok(js.startsWith('window.PROPS = '));
  // The JS must still evaluate to the original string.
  const sandbox = {};
  new Function('window', js)(sandbox);
  assert.equal(sandbox.PROPS.title, '</script><b>x</b>');
});

test('scene aliases: subtitle is sub and duration is seconds', () => {
  const r = validateProps({
    scenes: [{ text: 'One', subtitle: ' Two ', duration: 2 }],
  });
  assert.equal(r.ok, true);
  assert.deepEqual(r.props.scenes, [{ text: 'One', sub: 'Two', seconds: 2 }]);
  assert.equal(r.props.duration, 2);
});

test('scene alias limits are unchanged', () => {
  assert.equal(validateProps({ scenes: [{ text: 'hi', subtitle: 'x'.repeat(121), seconds: 3 }] }).ok, false);
  assert.equal(validateProps({ scenes: [{ text: 'hi', duration: 0.82 }] }).ok, false);
  assert.equal(validateProps({ scenes: [{ text: 'hi', duration: 8.01 }] }).ok, false);
});

test('scene aliases given with their long form are rejected', () => {
  const bothSub = validateProps({ scenes: [{ text: 'a', sub: 'b', subtitle: 'c', seconds: 3 }] });
  assert.equal(bothSub.ok, false);
  assert.equal(bothSub.error, 'use either sub or subtitle');
  const bothSeconds = validateProps({ scenes: [{ text: 'a', seconds: 3, duration: 3 }] });
  assert.equal(bothSeconds.ok, false);
  assert.equal(bothSeconds.error, 'use either seconds or duration');
});

test('unknown scene keys are still rejected alongside the aliases', () => {
  const r = validateProps({ scenes: [{ text: 'a', duration: 3, colour: 'red' }] });
  assert.equal(r.ok, false);
  assert.match(r.error, /unknown field: colour/);
});

test('hasScenes reports whether the request sent scenes', () => {
  assert.equal(validateProps({ title: 'x' }).hasScenes, false);
  assert.equal(validateProps({}).hasScenes, false);
  assert.equal(validateProps({ scenes: [{ text: 'x', seconds: 3 }] }).hasScenes, true);
});

test('echoProps returns only the fields the caller sent, never the defaults', () => {
  const r = validateProps({ subtitle: 'Now' });
  const echoed = echoProps({ subtitle: 'Now' }, r.props);
  assert.deepEqual(echoed, { subtitle: 'Now' });
  assert.equal(JSON.stringify(echoed).includes('Hello from HyperFrames'), false);
});

test('echoProps of an empty body is empty', () => {
  const r = validateProps({});
  assert.deepEqual(echoProps({}, r.props), {});
});

test('echoProps returns the normalised scenes when the caller sent scenes', () => {
  const body = { scenes: [{ text: ' A ', duration: 3 }] };
  const r = validateProps(body);
  const echoed = echoProps(body, r.props);
  assert.deepEqual(Object.keys(echoed), ['scenes']);
  assert.deepEqual(echoed.scenes, [{ text: 'A', sub: '', seconds: 3 }]);
});

test('narration and music default to false and must be booleans', () => {
  const r = validateProps({});
  assert.equal(r.props.narration, false);
  assert.equal(r.props.music, false);
  assert.equal(validateProps({ narration: true, music: true }).props.narration, true);
  assert.equal(validateProps({ narration: 'yes' }).ok, false);
  assert.equal(validateProps({ music: 1 }).ok, false);
});
