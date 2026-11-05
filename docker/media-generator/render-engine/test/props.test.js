import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateProps, propsToJs, DEFAULTS } from '../lib/props.js';

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

test('propsToJs escapes angle brackets so a value cannot close a script tag', () => {
  const js = propsToJs({ title: '</script><b>x</b>' });
  assert.ok(!js.includes('</script>'));
  assert.ok(js.startsWith('window.PROPS = '));
  // The JS must still evaluate to the original string.
  const sandbox = {};
  new Function('window', js)(sandbox);
  assert.equal(sandbox.PROPS.title, '</script><b>x</b>');
});
