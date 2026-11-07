import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  buildSnapshotArgs,
  buildStills,
  checkStillsApproval,
  sceneStartTimes,
} from '../lib/stills.js';
import { PreviewRefused } from '../lib/preview.js';
import { hashArtifact, recordApproval } from '../lib/approvals.js';

let dir;
let outDir;

beforeEach(async () => {
  dir = await mkdtemp(path.join(os.tmpdir(), 'stills-test-'));
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

// Three 25 s scenes: the stills cover the whole job (75 s), not a 60 s window.
const SCENES = [
  { title: 'One', body: 'First scene', seconds: 25 },
  { title: 'Two', body: 'Second scene', seconds: 25 },
  { title: 'Three', body: 'Third scene', seconds: 25 },
];

// Fake snapshot: writes one PNG-named file per time into a folder under dir, in time order.
// `count` overrides how many files it returns, to test a mismatch.
function fakeSnapshot({ count } = {}) {
  const calls = [];
  const snapshot = async ({ times, outDir: target, props }) => {
    calls.push({ times, outDir: target, props });
    const snapDir = path.join(dir, 'snap');
    await mkdir(snapDir, { recursive: true });
    const n = count ?? times.length;
    const files = [];
    for (let i = 0; i < n; i += 1) {
      const file = path.join(snapDir, `frame-${i}.png`);
      await writeFile(file, `frame ${i}`);
      files.push(file);
    }
    return { files };
  };
  return { snapshot, calls };
}

test('sceneStartTimes: cumulative author-set starts, 0-based index', () => {
  assert.deepEqual(sceneStartTimes([{ seconds: 4 }, { seconds: 8 }, { seconds: 3 }]), [
    { index: 0, start: 0 },
    { index: 1, start: 4 },
    { index: 2, start: 12 },
  ]);
});

test('sceneStartTimes: rejects a non-array and a scene without positive finite seconds', () => {
  assert.throws(() => sceneStartTimes('scenes'), /must be an array/);
  assert.throws(() => sceneStartTimes([{ seconds: 0 }]), /seconds/);
  assert.throws(() => sceneStartTimes([{ seconds: 4 }, { seconds: Infinity }]), /seconds/);
  assert.throws(() => sceneStartTimes([null]), /seconds/);
});

test('buildSnapshotArgs: the hyperframes snapshot argument list, with a time of 0 nudged to 0.05', () => {
  assert.deepEqual(
    buildSnapshotArgs({ projectDir: '/proj', outDir: '/out', times: [0, 4, 12] }),
    ['snapshot', '--at', '0.05,4,12', '--no-end', '-o', '/out', '/proj'],
  );
  assert.deepEqual(
    buildSnapshotArgs({ projectDir: 'p', outDir: 'o', times: [1.5, 25] }),
    ['snapshot', '--at', '1.5,25', '--no-end', '-o', 'o', 'p'],
  );
});

// Artifact fixtures: G1 to G4 files under an artifact root, with the named gates approved against their files.
async function approvalFixture({ approve = ['G1', 'G2', 'G3', 'G4'] } = {}) {
  const root = path.join(dir, 'artifacts');
  const approvalsPath = path.join(dir, 'approvals');
  await mkdir(root, { recursive: true });
  const gate_artifacts = {};
  for (const g of ['G1', 'G2', 'G3', 'G4']) {
    gate_artifacts[g] = `${g.toLowerCase()}.txt`;
    await writeFile(path.join(root, gate_artifacts[g]), `content for ${g}`);
  }
  for (const g of approve) {
    const full = path.join(root, gate_artifacts[g]);
    await recordApproval(approvalsPath, {
      gate: g, artifact: full, sha256: await hashArtifact(full), approvedBy: 'tester',
    });
  }
  return { job: { gate_artifacts }, root, approvalsPath };
}

test('checkStillsApproval: passes when G1 to G4 are approved against their current files', async () => {
  const fx = await approvalFixture();
  const result = await checkStillsApproval(fx.job, { artifactRoot: fx.root, approvalsPath: fx.approvalsPath });
  assert.deepEqual(result, { ok: true });
});

test('checkStillsApproval: refuses and names every unapproved gate', async () => {
  const fx = await approvalFixture({ approve: ['G1', 'G3'] });
  const result = await checkStillsApproval(fx.job, { artifactRoot: fx.root, approvalsPath: fx.approvalsPath });
  assert.equal(result.ok, false);
  assert.equal(result.status, 403);
  assert.equal(result.payload.error, 'gates not approved');
  assert.deepEqual(result.payload.gates, ['G2', 'G4']);
});

test('checkStillsApproval: a changed artifact voids its approval', async () => {
  const fx = await approvalFixture();
  await writeFile(path.join(fx.root, 'g2.txt'), 'edited after approval');
  const result = await checkStillsApproval(fx.job, { artifactRoot: fx.root, approvalsPath: fx.approvalsPath });
  assert.equal(result.ok, false);
  assert.equal(result.status, 403);
  assert.deepEqual(result.payload.gates, ['G2']);
});

test('checkStillsApproval: 503 when ARTIFACT_DIR or APPROVALS_PATH is missing', async () => {
  const fx = await approvalFixture();
  const noPath = await checkStillsApproval(fx.job, { artifactRoot: fx.root, approvalsPath: '' });
  assert.equal(noPath.status, 503);
  const noRoot = await checkStillsApproval(fx.job, { artifactRoot: '', approvalsPath: fx.approvalsPath });
  assert.equal(noRoot.status, 503);
});

test('checkStillsApproval: 400 when gate_artifacts lacks one of G1 to G4', async () => {
  const fx = await approvalFixture();
  const partial = { ...fx.job.gate_artifacts };
  delete partial.G3;
  const result = await checkStillsApproval(
    { gate_artifacts: partial },
    { artifactRoot: fx.root, approvalsPath: fx.approvalsPath },
  );
  assert.equal(result.ok, false);
  assert.equal(result.status, 400);
  assert.match(result.payload.error, /missing G3/);
});

test('buildStills: snapshots at each scene start over all scenes and names the stills scene-NN.png in time order', async () => {
  const { snapshot, calls } = fakeSnapshot();
  const seen = [];
  const theJob = job(SCENES);
  const result = await buildStills(theJob, {
    outDir,
    checkApproval: async (j) => {
      seen.push(j);
      return { ok: true };
    },
    snapshot,
  });

  assert.equal(result.count, 3);
  assert.deepEqual(result.files, [1, 2, 3].map((i) => path.join(outDir, `scene-0${i}.png`)));
  assert.deepEqual(
    await Promise.all(result.files.map((f) => readFile(f, 'utf8'))),
    ['frame 0', 'frame 1', 'frame 2'],
  );

  assert.equal(seen.length, 1);
  assert.deepEqual(seen[0], theJob);
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].times, [0, 25, 50]);
  assert.equal(calls[0].props.fps, 30);
  assert.equal(calls[0].props.scenes.length, 3);
});

test('buildStills: a job shorter than 60 seconds is not refused (no preview window)', async () => {
  const { snapshot, calls } = fakeSnapshot();
  const result = await buildStills(job([{ title: 'Short', body: 'A short job', seconds: 20 }]), {
    outDir,
    checkApproval: async () => ({ ok: true }),
    snapshot,
  });
  assert.equal(result.count, 1);
  assert.deepEqual(calls[0].times, [0]);
});

test('buildStills: uses two-digit names past nine scenes', async () => {
  const scenes = Array.from({ length: 10 }, (_, i) => ({ title: `S${i + 1}`, body: 'Body', seconds: 10 }));
  const { snapshot, calls } = fakeSnapshot();
  const result = await buildStills(job(scenes), {
    outDir,
    checkApproval: async () => ({ ok: true }),
    snapshot,
  });
  assert.equal(result.count, 10);
  assert.equal(path.basename(result.files[0]), 'scene-01.png');
  assert.equal(path.basename(result.files[9]), 'scene-10.png');
  assert.equal(calls[0].times.length, 10);
});

test('buildStills: a refused approval throws before snapshot and writes no stills', async () => {
  const { snapshot, calls } = fakeSnapshot();
  await assert.rejects(
    buildStills(job(SCENES), {
      outDir,
      checkApproval: async () => ({ ok: false, status: 403, payload: { error: 'gates not approved', gates: ['G2'] } }),
      snapshot,
    }),
    (err) => err instanceof PreviewRefused
      && err.status === 403
      && err.payload.error === 'gates not approved'
      && err.payload.gates.length === 1
      && err.payload.gates[0] === 'G2',
  );
  assert.equal(calls.length, 0);
  await assert.rejects(stat(path.join(outDir, 'scene-01.png')));
});

test('buildStills: an invalid job is refused before the approval check or snapshot', async () => {
  const { snapshot, calls } = fakeSnapshot();
  let checked = 0;
  await assert.rejects(
    buildStills(job(SCENES, { schema_version: 2 }), {
      outDir,
      checkApproval: async () => {
        checked += 1;
        return { ok: true };
      },
      snapshot,
    }),
    (err) => err instanceof PreviewRefused && err.status === 400 && err.payload.error === 'invalid job',
  );
  assert.equal(checked, 0);
  assert.equal(calls.length, 0);
});

test('buildStills: a format that is not rendered yet is refused at its own size', async () => {
  const { snapshot, calls } = fakeSnapshot();
  await assert.rejects(
    buildStills(job(SCENES, { format: 'youtube-short' }), {
      outDir,
      checkApproval: async () => ({ ok: true }),
      snapshot,
    }),
    (err) => err instanceof PreviewRefused && err.status === 400 && /YouTube Short \(1080x1920/.test(err.payload.error),
  );
  assert.equal(calls.length, 0);
});

test('buildStills: rejects when snapshot returns a different number of files than scenes', async () => {
  const { snapshot } = fakeSnapshot({ count: 2 });
  await assert.rejects(
    buildStills(job(SCENES), {
      outDir,
      checkApproval: async () => ({ ok: true }),
      snapshot,
    }),
    /2 files.*3 scenes/,
  );
});
