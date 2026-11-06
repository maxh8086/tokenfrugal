import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  planNarration,
  narrationFilter,
  narrationArgs,
  musicArgs,
  muxArgs,
  audioMode,
  NARRATION_RULE,
} from '../lib/audio-plan.js';

const scenes = [
  { id: 'scene-1', start: 0, seconds: 3 },
  { id: 'scene-2', start: 3, seconds: 4 },
];

test('planNarration reports a narration longer than its scene, with both lengths', () => {
  const r = planNarration(scenes, [2.5, 4.25]);
  assert.equal(r.ok, false);
  assert.equal(r.findings.length, 1);
  const f = r.findings[0];
  assert.equal(f.scene, 'scene-2');
  assert.equal(f.rule, NARRATION_RULE);
  assert.equal(f.narrationSeconds, 4.25);
  assert.equal(f.sceneSeconds, 4);
  assert.match(f.message, /4\.25s/);
});

test('planNarration has no findings when every narration fits its scene', () => {
  // Equal length is allowed: only a longer narration is a finding.
  assert.deepEqual(planNarration(scenes, [3, 3.9]), { ok: true, findings: [] });
});

test('planNarration reports every long clip', () => {
  const r = planNarration(scenes, [3.5, 4.5]);
  assert.deepEqual(r.findings.map((f) => f.scene), ['scene-1', 'scene-2']);
});

test('planNarration rejects a duration list that does not match the scenes', () => {
  assert.throws(() => planNarration(scenes, [1]), TypeError);
});

test('narrationFilter delays each clip by its start time in ms and mixes them', () => {
  const f = narrationFilter([
    { inputIndex: 0, startSeconds: 0 },
    { inputIndex: 1, startSeconds: 3 },
  ]);
  assert.match(f, /\[0:a\]adelay=0:all=1\[d0\]/);
  assert.match(f, /\[1:a\]adelay=3000:all=1\[d1\]/);
  assert.match(f, /\[d0\]\[d1\]amix=inputs=2:normalize=0/);
  assert.ok(f.endsWith('[narr]'));
});

test('narrationFilter with one clip needs no amix', () => {
  const f = narrationFilter([{ inputIndex: 0, startSeconds: 1.5 }]);
  assert.equal(f.includes('amix'), false);
  assert.match(f, /adelay=1500:all=1\[d0\]/);
});

test('narrationArgs builds a stereo WAV of exactly the film length', () => {
  const args = narrationArgs({
    clips: [{ file: '/job/s0.wav', startSeconds: 0 }, { file: '/job/s1.wav', startSeconds: 3 }],
    totalSeconds: 7,
    out: '/job/narration.wav',
  });
  assert.deepEqual(args.slice(0, 2), ['-y', '-nostdin']);
  assert.equal(args[args.indexOf('-t') + 1], '7');
  assert.equal(args[args.indexOf('-ac') + 1], '2');
  assert.equal(args[args.length - 1], '/job/narration.wav');
});

test('musicArgs is deterministic: fixed sines, -22 dB peak, fades, and the film length', () => {
  const a = musicArgs({ totalSeconds: 10, out: '/job/music.wav' });
  const b = musicArgs({ totalSeconds: 10, out: '/job/music.wav' });
  assert.deepEqual(a, b);
  const source = a[a.indexOf('-i') + 1];
  assert.match(source, /^aevalsrc=/);
  for (const hz of ['110', '165', '220']) {
    assert.ok(source.includes(`sin(2*PI*${hz}*t)`), hz);
  }
  assert.ok(source.includes('0.0794'), 'about -22 dB');
  assert.ok(source.includes(':d=10'));
  const af = a[a.indexOf('-af') + 1];
  assert.match(af, /afade=t=in:st=0:d=0\.5/);
  assert.match(af, /afade=t=out:st=9\.000:d=1/);
});

test('audioMode names the audio the film carries', () => {
  assert.equal(audioMode({ narration: false, music: false }), 'none');
  assert.equal(audioMode({ narration: true, music: false }), 'narration');
  assert.equal(audioMode({ narration: false, music: true }), 'music');
  assert.equal(audioMode({ narration: true, music: true }), 'both');
});

test('muxArgs copies video and encodes audio as AAC 192k stereo, stopping at the shorter stream', () => {
  const args = muxArgs({ videoFile: '/job/video.mp4', narrationFile: '/job/n.wav', mode: 'narration', out: '/job/m.mp4' });
  assert.equal(args[args.indexOf('-c:v') + 1], 'copy');
  assert.equal(args[args.indexOf('-c:a') + 1], 'aac');
  assert.equal(args[args.indexOf('-b:a') + 1], '192k');
  assert.equal(args[args.indexOf('-ac') + 1], '2');
  assert.ok(args.includes('-shortest'));
  assert.equal(args[args.indexOf('-map') + 1], '0:v:0');
});

test('muxArgs with both mixes narration and music without normalising', () => {
  const args = muxArgs({
    videoFile: '/job/video.mp4',
    narrationFile: '/job/n.wav',
    musicFile: '/job/m.wav',
    mode: 'both',
    out: '/job/m.mp4',
  });
  const filter = args[args.indexOf('-filter_complex') + 1];
  assert.match(filter, /amix=inputs=2:normalize=0/);
});

test('muxArgs rejects an unknown mode', () => {
  assert.throws(() => muxArgs({ videoFile: 'v', mode: 'none', out: 'o' }), TypeError);
});
