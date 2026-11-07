import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readdir, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  buildVoiceSample,
  narrationFor,
  planSampleWindow,
  wavSeconds,
} from '../lib/voice-sample.js';

const RATE = 22050;

// A 16-bit mono PCM WAV of the given length (silence).
function makeWav(seconds, sampleRate = RATE) {
  const byteRate = sampleRate * 2;
  const dataSize = Math.round(seconds * byteRate);
  const buf = Buffer.alloc(44 + dataSize);
  buf.write('RIFF', 0, 'ascii');
  buf.writeUInt32LE(36 + dataSize, 4);
  buf.write('WAVE', 8, 'ascii');
  buf.write('fmt ', 12, 'ascii');
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(1, 22);
  buf.writeUInt32LE(sampleRate, 24);
  buf.writeUInt32LE(byteRate, 28);
  buf.writeUInt16LE(2, 32);
  buf.writeUInt16LE(16, 34);
  buf.write('data', 36, 'ascii');
  buf.writeUInt32LE(dataSize, 40);
  return buf;
}

// Fake dhvani: each request gets a WAV of secondsPerChunk, and every request body is recorded.
function fakeFetch(secondsPerChunk) {
  const requests = [];
  const impl = async (url, opts) => {
    const body = JSON.parse(opts.body);
    requests.push({ url, body });
    const wav = makeWav(secondsPerChunk);
    return {
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'audio/wav' }),
      arrayBuffer: async () => wav.buffer.slice(wav.byteOffset, wav.byteOffset + wav.byteLength),
    };
  };
  return { impl, requests };
}

let dir;
let outDir;
let savedVoiceEnv;

beforeEach(async () => {
  dir = await mkdtemp(path.join(os.tmpdir(), 'voice-sample-test-'));
  outDir = path.join(dir, 'out');
  savedVoiceEnv = process.env.DHVANI_VOICE;
  delete process.env.DHVANI_VOICE;
});

afterEach(async () => {
  if (savedVoiceEnv === undefined) delete process.env.DHVANI_VOICE;
  else process.env.DHVANI_VOICE = savedVoiceEnv;
  await rm(dir, { recursive: true, force: true });
});

function job(scenes, overrides = {}) {
  return {
    schema_version: 1,
    voice_profile: null,
    scenes,
    ...overrides,
  };
}

test('planSampleWindow: stops at the first part that reaches the target', () => {
  assert.deepEqual(planSampleWindow([25, 25, 25], 60), { ok: true, count: 3, seconds: 75, available: 75 });
  assert.deepEqual(planSampleWindow([30, 30], 60), { ok: true, count: 2, seconds: 60, available: 60 });
  assert.deepEqual(planSampleWindow([20, 20, 20, 20, 20], 60), { ok: true, count: 3, seconds: 60, available: 100 });
});

test('planSampleWindow: not ok when the parts fall short, using every part', () => {
  assert.deepEqual(planSampleWindow([10, 15], 60), { ok: false, count: 2, seconds: 25, available: 25 });
  assert.deepEqual(planSampleWindow([], 60), { ok: false, count: 0, seconds: 0, available: 0 });
});

test('planSampleWindow: default target is 60 seconds', () => {
  assert.equal(planSampleWindow([59]).ok, false);
  assert.equal(planSampleWindow([60]).ok, true);
});

test('planSampleWindow: rejects bad durations', () => {
  assert.throws(() => planSampleWindow('60'), /must be an array/);
  assert.throws(() => planSampleWindow([10, -1]), /invalid duration/);
  assert.throws(() => planSampleWindow([NaN]), /invalid duration/);
});

test('wavSeconds: reads duration from the header', () => {
  assert.equal(wavSeconds(makeWav(1.5)), 1.5);
  assert.equal(wavSeconds(makeWav(2, 24000)), 2);
});

test('wavSeconds: clamps a placeholder data size to the bytes present', () => {
  const wav = makeWav(2);
  wav.writeUInt32LE(0xffffffff, 40);
  assert.equal(wavSeconds(wav), 2);
});

test('wavSeconds: rejects non-WAV input', () => {
  assert.throws(() => wavSeconds(Buffer.from('not a wav file at all')), /RIFF\/WAVE/);
  assert.throws(() => wavSeconds('string'), /not a WAV buffer/);
});

test('narrationFor: title, full stop, then body', () => {
  assert.equal(narrationFor({ title: 'Intro', body: 'Hello world' }), 'Intro. Hello world');
  assert.equal(narrationFor({ title: 'Outro' }), 'Outro. ');
});

test('buildVoiceSample: narrates scenes in order and stops once the window is covered', async () => {
  const { impl, requests } = fakeFetch(25);
  const calls = [];
  const runFfmpeg = async (args) => {
    calls.push(args);
    await writeFile(args[args.length - 1], Buffer.from('wav'));
  };
  const scenes = [
    { title: 'One', body: 'First scene.' },
    { title: 'Two', body: 'Second scene.' },
    { title: 'Three', body: 'Third scene.' },
    { title: 'Four', body: 'Never reached.' },
  ];
  const result = await buildVoiceSample(job(scenes, { voice_profile: 'bm_george' }), {
    baseUrl: 'http://dhvani.test/',
    outDir,
    fetchImpl: impl,
    runFfmpeg,
  });

  assert.deepEqual(result, { file: path.join(outDir, 'voice-sample.wav'), seconds: 60 });
  assert.deepEqual(requests.map((r) => r.body.text), [
    'One. First scene.',
    'Two. Second scene.',
    'Three. Third scene.',
  ]);
  assert.equal(requests[0].url, 'http://dhvani.test/api/kokoro/speak');
  for (const r of requests) assert.deepEqual([r.body.voice, r.body.speed], ['bm_george', 1]);

  assert.equal(calls.length, 1);
  const args = calls[0];
  assert.equal(args.filter((a) => a === '-i').length, 3);
  const filter = args[args.indexOf('-filter_complex') + 1];
  assert.equal(filter, '[0:a][1:a][2:a]concat=n=3:v=0:a=1,atrim=end=60');
  assert.deepEqual(args.slice(args.indexOf('-ar'), args.indexOf('-ar') + 4), ['-ar', '22050', '-ac', '1']);
  assert.equal(args[args.length - 1], path.join(outDir, 'voice-sample.wav'));
});

test('buildVoiceSample: falls back to DHVANI_VOICE, then af_heart, when no voice is set', async () => {
  const scenes = [{ title: 'Only', body: 'Long enough.' }];

  const first = fakeFetch(60);
  await buildVoiceSample(job(scenes), {
    baseUrl: 'http://dhvani.test',
    outDir,
    fetchImpl: first.impl,
    runFfmpeg: async (args) => writeFile(args[args.length - 1], Buffer.from('wav')),
  });
  assert.equal(first.requests[0].body.voice, 'af_heart');

  process.env.DHVANI_VOICE = 'am_adam';
  const second = fakeFetch(60);
  await buildVoiceSample(job(scenes), {
    baseUrl: 'http://dhvani.test',
    outDir,
    fetchImpl: second.impl,
    runFfmpeg: async (args) => writeFile(args[args.length - 1], Buffer.from('wav')),
  });
  assert.equal(second.requests[0].body.voice, 'am_adam');
});

test('buildVoiceSample: removes the temporary parts directory', async () => {
  const { impl } = fakeFetch(70);
  await buildVoiceSample(job([{ title: 'Long', body: 'Enough narration.' }]), {
    baseUrl: 'http://dhvani.test',
    outDir,
    fetchImpl: impl,
    runFfmpeg: async (args) => {
      const partFiles = args.filter((a) => a.endsWith('.wav') && a !== args[args.length - 1]);
      assert.equal(partFiles.length, 1);
      await writeFile(args[args.length - 1], Buffer.from('wav'));
    },
  });
  const entries = await readdir(outDir);
  assert.deepEqual(entries, ['voice-sample.wav']);
});

test('buildVoiceSample: rejects narration shorter than 60 seconds without running ffmpeg', async () => {
  const { impl } = fakeFetch(20);
  let ran = false;
  await assert.rejects(
    buildVoiceSample(job([{ title: 'Short', body: 'Brief.' }]), {
      baseUrl: 'http://dhvani.test',
      outDir,
      fetchImpl: impl,
      runFfmpeg: async () => { ran = true; },
    }),
    /narration too short/,
  );
  assert.equal(ran, false);
});

test('buildVoiceSample: rejects an invalid voice choice and a job with no scenes', async () => {
  await assert.rejects(
    buildVoiceSample(job([{ title: 'X', body: 'Y' }], { voice_profile: 'Not A Voice' }), {
      baseUrl: 'http://dhvani.test',
      outDir,
      fetchImpl: fakeFetch(60).impl,
      runFfmpeg: async () => {},
    }),
    /invalid narration voice/,
  );
  await assert.rejects(
    buildVoiceSample(job([]), {
      baseUrl: 'http://dhvani.test',
      outDir,
      fetchImpl: fakeFetch(60).impl,
      runFfmpeg: async () => {},
    }),
    /no scenes/,
  );
});
