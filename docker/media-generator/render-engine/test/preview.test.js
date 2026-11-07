import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  PREVIEW_SECONDS,
  PreviewRefused,
  buildPreview,
  checkG4Approval,
  previewWindow,
  validatePreviewJob,
} from '../lib/preview.js';
import { hashArtifact, recordApproval } from '../lib/approvals.js';

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

// Fake dhvani: every request gets a WAV of secondsPerChunk. Requests are recorded so a test can count them.
function fakeFetch(secondsPerChunk) {
  const requests = [];
  const impl = async (url, opts) => {
    requests.push({ url, body: JSON.parse(opts.body) });
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

// Fake ffmpeg: the last argument is the output file, which gets a 60 s WAV so the sample hashes like a real one.
function fakeFfmpeg() {
  const calls = [];
  const run = async (args) => {
    calls.push(args);
    await writeFile(args[args.length - 1], makeWav(60));
  };
  return { run, calls };
}

let dir;
let outDir;

beforeEach(async () => {
  dir = await mkdtemp(path.join(os.tmpdir(), 'preview-test-'));
  outDir = path.join(dir, 'out');
});

afterEach(async () => {
  await rm(dir, { recursive: true, force: true });
});

function job(scenes, overrides = {}) {
  return {
    schema_version: 1,
    seed: 7,
    destinations: ['youtube'],
    template: 'explainer-basic',
    template_version: 1,
    voice_profile: null,
    scenes,
    gate_artifacts: {},
    ...overrides,
  };
}

// Three 25 s scenes: 75 s in all, so the preview cuts the third scene to 10 s.
const LONG_SCENES = [
  { title: 'One', body: 'First scene', seconds: 25 },
  { title: 'Two', body: 'Second scene', seconds: 25 },
  { title: 'Three', body: 'Third scene', seconds: 25 },
];

test('previewWindow: the preview is 60 seconds', () => {
  assert.equal(PREVIEW_SECONDS, 60);
});

test('previewWindow: whole scenes are kept while they fit, the crossing scene is cut', () => {
  const win = previewWindow(LONG_SCENES);
  assert.equal(win.ok, true);
  assert.equal(win.seconds, 60);
  assert.deepEqual(win.scenes.map((s) => s.seconds), [25, 25, 10]);
  assert.deepEqual(win.scenes.map((s) => s.title), ['One', 'Two', 'Three']);
});

test('previewWindow: scenes after the window are dropped', () => {
  const win = previewWindow([
    { title: 'A', body: '', seconds: 30 },
    { title: 'B', body: '', seconds: 30 },
    { title: 'C', body: '', seconds: 30 },
  ]);
  assert.equal(win.ok, true);
  assert.deepEqual(win.scenes.map((s) => s.seconds), [30, 30]);
});

test('previewWindow: a single long scene is cut to 60 seconds', () => {
  const win = previewWindow([{ title: 'Long', body: '', seconds: 75 }]);
  assert.equal(win.ok, true);
  assert.deepEqual(win.scenes.map((s) => s.seconds), [60]);
});

test('previewWindow: a job shorter than 60 seconds is refused', () => {
  const win = previewWindow([{ title: 'Short', body: '', seconds: 40 }]);
  assert.equal(win.ok, false);
  assert.match(win.error, /runs 40 seconds; a preview needs 60 seconds/);
});

test('previewWindow: a cut that leaves a clip under the props minimum is refused', () => {
  const win = previewWindow([
    { title: 'A', body: '', seconds: 59.5 },
    { title: 'B', body: '', seconds: 5 },
  ]);
  assert.equal(win.ok, false);
  assert.match(win.error, /cannot be cut on this scene boundary/);
});

test('previewWindow: rejects bad scene input', () => {
  assert.throws(() => previewWindow('scenes'), /must be an array/);
  assert.throws(() => previewWindow([{ title: 'X', seconds: 0 }]), /positive seconds/);
  assert.throws(() => previewWindow([null]), /positive seconds/);
});

test('validatePreviewJob: a long job maps to a 60 second props body at youtube fps', async () => {
  const result = await validatePreviewJob(job(LONG_SCENES));
  assert.equal(result.ok, true);
  assert.equal(result.props.fps, 30);
  assert.deepEqual(result.props.scenes.map((s) => s.seconds), [25, 25, 10]);
});

test('validatePreviewJob: refuses an invalid job before any synthesis', async () => {
  const result = await validatePreviewJob(job(LONG_SCENES, { schema_version: 2 }));
  assert.equal(result.ok, false);
  assert.equal(result.status, 400);
  assert.equal(result.payload.error, 'invalid job');
});

test('validatePreviewJob: refuses a format that is not rendered yet, at its own size', async () => {
  const result = await validatePreviewJob(job(LONG_SCENES, { format: 'youtube-short' }));
  assert.equal(result.ok, false);
  assert.equal(result.status, 400);
  assert.match(result.payload.error, /YouTube Short \(1080x1920/);
});

test('validatePreviewJob: refuses a job shorter than 60 seconds', async () => {
  const result = await validatePreviewJob(job([{ title: 'Short', body: 'A short job', seconds: 20 }]));
  assert.equal(result.ok, false);
  assert.equal(result.status, 400);
  assert.match(result.payload.error, /a preview needs 60 seconds/);
});

test('buildPreview: builds the sample, renders the window with it as audio, and writes preview.mp4', async () => {
  const dh = fakeFetch(30);
  const ff = fakeFfmpeg();
  const renders = [];
  const rendered = path.join(dir, 'render-output.mp4');
  await writeFile(rendered, 'fake mp4');
  const result = await buildPreview(job(LONG_SCENES), {
    baseUrl: 'http://dhvani.test',
    outDir,
    fetchImpl: dh.impl,
    runFfmpeg: ff.run,
    checkApproval: async () => ({ ok: true }),
    render: async (props, opts) => {
      renders.push({ props, opts });
      return { file: rendered };
    },
  });
  assert.deepEqual(result, { file: path.join(outDir, 'preview.mp4'), seconds: 60 });
  assert.equal(await readFile(path.join(outDir, 'preview.mp4'), 'utf8'), 'fake mp4');
  await assert.rejects(stat(rendered));
  assert.equal(renders.length, 1);
  assert.equal(renders[0].opts.seconds, 60);
  assert.equal(renders[0].opts.audioFile, path.join(outDir, 'voice-sample.wav'));
  assert.deepEqual(renders[0].props.scenes.map((s) => s.seconds), [25, 25, 10]);
  assert.equal(dh.requests.length >= 1, true);
});

test('buildPreview: a refused approval throws before any render and writes no preview', async () => {
  const dh = fakeFetch(30);
  const ff = fakeFfmpeg();
  let rendered = 0;
  await assert.rejects(
    buildPreview(job(LONG_SCENES), {
      baseUrl: 'http://dhvani.test',
      outDir,
      fetchImpl: dh.impl,
      runFfmpeg: ff.run,
      checkApproval: async () => ({ ok: false, status: 403, payload: { error: 'G4 is not approved' } }),
      render: async () => {
        rendered += 1;
        return { file: path.join(dir, 'never.mp4') };
      },
    }),
    (err) => err instanceof PreviewRefused && err.status === 403 && err.payload.error === 'G4 is not approved',
  );
  assert.equal(rendered, 0);
  await assert.rejects(stat(path.join(outDir, 'preview.mp4')));
});

test('buildPreview: a short job is refused before dhvani is called', async () => {
  const dh = fakeFetch(30);
  await assert.rejects(
    buildPreview(job([{ title: 'Short', body: 'A short job', seconds: 20 }]), {
      baseUrl: 'http://dhvani.test',
      outDir,
      fetchImpl: dh.impl,
      runFfmpeg: fakeFfmpeg().run,
      checkApproval: async () => ({ ok: true }),
      render: async () => ({ file: 'unused' }),
    }),
    (err) => err instanceof PreviewRefused && err.status === 400,
  );
  assert.equal(dh.requests.length, 0);
});

test('buildPreview: refuses to run without an approval check or a render', async () => {
  await assert.rejects(
    buildPreview(job(LONG_SCENES), { baseUrl: 'x', outDir, render: async () => ({}) }),
    /checkApproval is required/,
  );
  await assert.rejects(
    buildPreview(job(LONG_SCENES), { baseUrl: 'x', outDir, checkApproval: async () => ({ ok: true }) }),
    /render is required/,
  );
});

// Approval fixtures: G1 to G3 approved against their files, G4 approved against the sample's hash (or not).
async function approvalFixture({ approveG2 = true, g4Content = null } = {}) {
  const root = path.join(dir, 'artifacts');
  const approvalsPath = path.join(dir, 'approvals');
  await mkdir(root, { recursive: true });
  const gate_artifacts = {};
  for (const g of ['G1', 'G2', 'G3', 'G4']) {
    gate_artifacts[g] = `${g.toLowerCase()}.txt`;
    await writeFile(path.join(root, gate_artifacts[g]), `content for ${g}`);
  }
  const job = { gate_artifacts };
  for (const g of ['G1', 'G2', 'G3']) {
    if (g === 'G2' && !approveG2) continue;
    const full = path.join(root, gate_artifacts[g]);
    await recordApproval(approvalsPath, { gate: g, artifact: full, sha256: await hashArtifact(full), approvedBy: 'tester' });
  }
  const sample = path.join(dir, 'voice-sample.wav');
  await writeFile(sample, 'the G4 voice sample bytes');
  if (g4Content !== null) {
    const g4File = path.join(root, gate_artifacts.G4);
    await writeFile(g4File, g4Content);
    await recordApproval(approvalsPath, {
      gate: 'G4', artifact: g4File, sha256: await hashArtifact(g4File), approvedBy: 'tester',
    });
  }
  return { job, root, approvalsPath, sample: { file: sample } };
}

test('checkG4Approval: passes when G1 to G3 and G4 are approved against the sample hash', async () => {
  const fx = await approvalFixture({ g4Content: 'the G4 voice sample bytes' });
  const result = await checkG4Approval(fx.job, { artifactRoot: fx.root, approvalsPath: fx.approvalsPath, sample: fx.sample });
  assert.deepEqual(result, { ok: true });
});

test('checkG4Approval: refuses while G4 is not approved at all', async () => {
  const fx = await approvalFixture({});
  const result = await checkG4Approval(fx.job, { artifactRoot: fx.root, approvalsPath: fx.approvalsPath, sample: fx.sample });
  assert.equal(result.ok, false);
  assert.equal(result.status, 403);
  assert.equal(result.payload.error, 'G4 is not approved against the current voice sample');
});

test('checkG4Approval: refuses when the sample changed since G4 was approved', async () => {
  const fx = await approvalFixture({ g4Content: 'an older voice sample' });
  const result = await checkG4Approval(fx.job, { artifactRoot: fx.root, approvalsPath: fx.approvalsPath, sample: fx.sample });
  assert.equal(result.ok, false);
  assert.equal(result.status, 403);
  assert.equal(result.payload.gate, 'G4');
  assert.match(result.payload.sha256, /^[0-9a-f]{64}$/);
});

test('checkG4Approval: refuses and names the gate when an earlier gate is not approved', async () => {
  const fx = await approvalFixture({ approveG2: false, g4Content: 'the G4 voice sample bytes' });
  const result = await checkG4Approval(fx.job, { artifactRoot: fx.root, approvalsPath: fx.approvalsPath, sample: fx.sample });
  assert.equal(result.ok, false);
  assert.equal(result.status, 403);
  assert.equal(result.payload.error, 'gates not approved');
  assert.deepEqual(result.payload.gates, ['G2']);
});

test('checkG4Approval: refuses a G4 approval recorded under another path', async () => {
  const fx = await approvalFixture({ g4Content: 'the G4 voice sample bytes' });
  const elsewhere = path.join(dir, 'elsewhere.txt');
  await writeFile(elsewhere, 'the G4 voice sample bytes');
  await recordApproval(fx.approvalsPath, {
    gate: 'G4', artifact: elsewhere, sha256: await hashArtifact(elsewhere), approvedBy: 'tester',
  });
  const result = await checkG4Approval(fx.job, { artifactRoot: fx.root, approvalsPath: fx.approvalsPath, sample: fx.sample });
  // The per-gate store keeps the newest G4 record only, so the recorded path is the other one: no match.
  assert.equal(result.ok, false);
  assert.equal(result.status, 403);
});

test('checkG4Approval: refuses without ARTIFACT_DIR or APPROVALS_PATH, and a G4 path outside it', async () => {
  const fx = await approvalFixture({ g4Content: 'the G4 voice sample bytes' });
  const noPath = await checkG4Approval(fx.job, { artifactRoot: fx.root, approvalsPath: '', sample: fx.sample });
  assert.equal(noPath.status, 503);
  const noRoot = await checkG4Approval(fx.job, { artifactRoot: '', approvalsPath: fx.approvalsPath, sample: fx.sample });
  assert.equal(noRoot.status, 503);
  const escaping = { ...fx.job, gate_artifacts: { ...fx.job.gate_artifacts, G4: '../outside.txt' } };
  const outside = await checkG4Approval(escaping, { artifactRoot: fx.root, approvalsPath: fx.approvalsPath, sample: fx.sample });
  assert.equal(outside.status, 400);
  assert.match(outside.payload.error, /must stay inside ARTIFACT_DIR/);
});
