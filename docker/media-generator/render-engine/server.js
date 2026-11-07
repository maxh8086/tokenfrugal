// POST /render: renders composition/index.html with the given props to an MP4 in OUTPUT_DIR.
// Optional narration (dhvani/Kokoro over HTTP) and music (deterministic ffmpeg bed) are muxed into the film.
// POST /render and GET /health each append one JSON line to RENDER_LOG (lib/log.js).
import express from 'express';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { randomUUID } from 'node:crypto';
import { cp, mkdir, readFile, rename, rm, writeFile, stat } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { validateProps, propsToJs, echoProps } from './lib/props.js';
import { checkScenes, toTimeline, applyCraftPolicy, CRAFT_RULES } from './lib/craft-check.js';
import { planNarration, narrationArgs, musicArgs, muxArgs, audioMode } from './lib/audio-plan.js';
import { colourArgs } from './lib/colour.js';
import { writeLog, tailLines } from './lib/log.js';
import { synthesizeChunk, splitForKokoro } from './lib/dhvani.js';
import {
  sha256Hex, stepKey, readCacheEntry, writeCacheEntry, writeNarrationClip, writeNarrationScript,
} from './lib/project-store.js';
import { planSegments, concatListText, segmentIsValid, coversDuration } from './lib/segments.js';
import {
  parseMotionBlurSamples, parseResolution, framesFor, segmentTimeoutMs, fitsBudget, settingsKey,
} from './lib/render-options.js';
import { gateJob } from './lib/job-gate.js';
import { buildPreview, checkG4Approval, PreviewRefused } from './lib/preview.js';
import { planParts, totalSeconds, PART_MAX_SECONDS } from './lib/job-parts.js';
import { jobOutputRel, jobOutputUrl, jobContactSheetRel, jobContactSheetUrl, JOB_PRESETS } from './lib/job-output.js';
import { buildContactSheetArgs, contactSheetFps } from './lib/contact-sheet.js';
import { loadRegistry } from './lib/template-registry.js';
import { parseRenderTemplate } from './lib/render-template.js';
import { preflightFailure } from './lib/gate-preflight.js';
import { measureHardware } from './lib/hardware-floor.js';
import { freeBytesAt } from './lib/disk-gate.js';
import { checkFlashes } from './lib/flash-check.js';
import { flashFailure } from './lib/flash-preflight.js';

// Gated job renders land in OUTPUT_DIR/<job_id>/<preset>.mp4 (lib/job-output.js). The preset is the job's destination.
const JOB_PRESET = JOB_PRESETS[0];

const execFileAsync = promisify(execFile);
const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

const PORT = Number(process.env.PORT || 3000);
const OUTPUT_DIR = process.env.OUTPUT_DIR || '/output';
const ARTIFACT_DIR = process.env.ARTIFACT_DIR || '';     // root for gate artifacts named by a job.json
const APPROVALS_PATH = process.env.APPROVALS_PATH || ''; // approvals folder (one G<n>.json per gate) written by bin/approve.js; a .json path is the legacy single file
const WORK_DIR = process.env.WORK_DIR || path.join(os.tmpdir(), 'hf-jobs');
const TEMPLATE_DIR = path.join(here, 'composition');
// The shorts destination (D60) renders its own 1080x1920 composition, not a resized copy of the landscape one.
const SHORTS_TEMPLATE_DIR = path.join(here, 'templates', 'scene-vertical');
const GATES_ENFORCE = process.env.GATES_ENFORCE === '1';
// Template registry (templates/index.json), loaded once on the first render that names a template.
let templateRegistryPromise = null;
function getTemplateRegistry() {
  if (!templateRegistryPromise) {
    templateRegistryPromise = loadRegistry(here).catch((err) => {
      templateRegistryPromise = null;
      throw err;
    });
  }
  return templateRegistryPromise;
}
const GSAP_FILE = require.resolve('gsap/dist/gsap.min.js');
const HF_BIN = path.join(path.dirname(require.resolve('hyperframes/package.json')), 'bin', 'hyperframes.mjs');
const RENDER_TIMEOUT_MS = Number(process.env.RENDER_TIMEOUT_MS || 600_000);
const DHVANI_URL = process.env.DHVANI_URL || 'http://dhvani:8080';
const DHVANI_VOICE = process.env.DHVANI_VOICE || 'af_heart';
// Project folder (D52): the narration record and the narrate step cache live here. Defaults to .project under
// OUTPUT_DIR (the MEDIA_OUTPUT_DIR mount). Dot-folders are not served by express.static. Set PROJECT_DIR= (empty) to turn it off.
const PROJECT_DIR = process.env.PROJECT_DIR ?? path.join(OUTPUT_DIR, '.project');
const NARRATE_STEP = 'narrate';
const NARRATE_STEP_VERSION = 1;
const NARRATE_SPEED = 1;
const FFMPEG_BIN = process.env.FFMPEG_BIN || 'ffmpeg';
const FFPROBE_BIN = process.env.FFPROBE_BIN || 'ffprobe';
const LOG_TAIL_LINES = 40;
const SEGMENTS_FPS_OK = [24, 25, 30, 60]; // fps values HyperFrames accepts for segmented MP4
const JOB_ID_RE = /^[A-Za-z0-9_-]{1,64}$/;
// Per-job render budget (D54). A segmented job whose projected time exceeds this fails with stage "budget" and keeps its segments.
const JOB_BUDGET_MS = Number(process.env.RENDER_JOB_BUDGET_MS || 1_800_000);

const LOGGED_ROUTES = new Set(['GET /health', 'POST /render', 'POST /preview']);

const app = express();

// Logs each POST /render and GET /health request once, when its response ends (or the connection closes).
// Registered before express.json so that a body that fails to parse is logged too.
app.use((req, res, next) => {
  const route = `${req.method} ${req.path.length > 1 ? req.path.replace(/\/+$/, '') : req.path}`;
  if (!LOGGED_ROUTES.has(route)) return next();
  const started = Date.now();
  const entry = { id: null, stage: null, error: null, stderr_tail: null };
  req.renderLog = entry;
  let written = false;
  const write = () => {
    if (written) return;
    written = true;
    writeLog({
      id: entry.id,
      route,
      status: res.statusCode,
      ok: res.statusCode < 400,
      stage: entry.stage,
      ms: Date.now() - started,
      error: entry.error,
      stderr_tail: entry.stderr_tail,
    });
  };
  res.on('finish', write);
  res.on('close', write);
  next();
});

app.use(express.json({ limit: '16kb' }));
app.use('/output', express.static(OUTPUT_DIR));

app.get('/health', (_req, res) => res.json({ ok: true }));

// One render at a time: each render starts headless Chromium, which is heavy.
let queue = Promise.resolve();
function enqueue(task) {
  const run = queue.then(task, task);
  queue = run.catch(() => {});
  return run;
}

// Error with an HTTP status, the pipeline stage that failed, and optional extra fields for the response.
function stageError(status, stage, message, extra = {}) {
  return Object.assign(new Error(message), { status, stage }, extra);
}

// Runs an external program and resolves with its output. On failure the error carries stderr.
function run(cmd, args, { input, timeout = RENDER_TIMEOUT_MS } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { stdio: [input === undefined ? 'ignore' : 'pipe', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => { stdout += d; });
    child.stderr.on('data', (d) => { stderr += d; });
    const timer = setTimeout(() => child.kill('SIGKILL'), timeout);
    child.on('error', (err) => {
      clearTimeout(timer);
      reject(Object.assign(err, { stderr }));
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        reject(Object.assign(new Error(`${path.basename(cmd)} exited with code ${code}`), { stderr }));
      }
    });
    if (input !== undefined) {
      child.stdin.on('error', () => {}); // EPIPE if the program exits before reading its input
      child.stdin.end(input);
    }
  });
}

// Runs fn and maps an unexpected failure to a stage error (500) carrying the stderr tail.
// Errors that already name a stage pass through unchanged.
async function atStage(stage, fn) {
  try {
    return await fn();
  } catch (err) {
    if (err.stage) throw err;
    throw stageError(500, stage, `${stage} failed: ${err.message}`, {
      stderrTail: tailLines(err.stderr, LOG_TAIL_LINES),
    });
  }
}

async function probeSeconds(file) {
  const { stdout } = await run(FFPROBE_BIN, [
    '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', file,
  ]);
  const seconds = Number(stdout.trim());
  if (!Number.isFinite(seconds) || seconds <= 0) {
    throw new Error(`could not read the duration of ${path.basename(file)}`);
  }
  return seconds;
}

// Synthesizes one scene through dhvani into jobDir/s{i}.wav. Kokoro takes at most 1000 characters per request,
// so a long scene comes back in several chunks, which are joined with ffmpeg. Returns the file path.
// One chunk through dhvani. With PROJECT_DIR set, a chunk already in cache/narrate/<key>/ is reused, and a new
// one is stored there. The key covers the chunk text, voice and speed, so the same text is never synthesized twice.
// voice is the job's narration voice (props.narration_voice); null falls back to DHVANI_VOICE.
async function synthesizeChunkCached(chunk, voice) {
  const v = voice ?? DHVANI_VOICE;
  const opts = { baseUrl: DHVANI_URL, voice: v, speed: NARRATE_SPEED };
  if (!PROJECT_DIR) return { wav: await callDhvani(chunk, opts), key: null, cached: false };
  const key = stepKey({
    inputs: [sha256Hex(chunk)],
    stepVersion: NARRATE_STEP_VERSION,
    parameters: { voice: v, speed: NARRATE_SPEED },
  });
  const hit = await readCacheEntry(PROJECT_DIR, NARRATE_STEP, key);
  if (hit) return { wav: await readFile(path.join(hit.dir, 'chunk.wav')), key, cached: true };
  const wav = await callDhvani(chunk, opts);
  await writeCacheEntry(PROJECT_DIR, NARRATE_STEP, key, { 'chunk.wav': wav }, {
    step: NARRATE_STEP,
    stepVersion: NARRATE_STEP_VERSION,
    key,
    voice: v,
    speed: NARRATE_SPEED,
    chars: chunk.length,
    createdAt: new Date().toISOString(),
  });
  return { wav, key, cached: false };
}

// Only the dhvani request is mapped to a 502 'audio' error; cache or disk failures keep their own stage.
async function callDhvani(chunk, opts) {
  try {
    return await synthesizeChunk(chunk, opts);
  } catch (err) {
    throw stageError(502, 'audio', 'dhvani narration failed', { detail: err.message });
  }
}

async function narrateScene(text, jobDir, i, voice) {
  const jobId = path.basename(jobDir);
  const chunks = splitForKokoro(text);
  const results = [];
  for (const chunk of chunks) results.push(await synthesizeChunkCached(chunk, voice));
  const wav = path.join(jobDir, `s${i}.wav`);
  const parts = [];
  for (let k = 0; k < results.length; k++) {
    const part = path.join(jobDir, `s${i}_${k}.wav`);
    await writeFile(part, results[k].wav);
    parts.push(part);
    if (PROJECT_DIR) {
      await writeNarrationClip(PROJECT_DIR, `${jobId}_s${i}_${k}`, results[k].wav, {
        jobId,
        scene: i,
        chunk: k,
        text: chunks[k],
        voice: voice ?? DHVANI_VOICE,
        speed: NARRATE_SPEED,
        stepKey: results[k].key,
        cacheHit: results[k].cached,
        bytes: results[k].wav.length,
        createdAt: new Date().toISOString(),
      });
    }
  }
  if (parts.length === 1) {
    await rename(parts[0], wav);
    return wav;
  }
  const inputs = parts.flatMap((part) => ['-i', part]);
  await run(FFMPEG_BIN, [
    '-y', ...inputs,
    '-filter_complex', `concat=n=${parts.length}:v=0:a=1`,
    '-ar', '22050', '-ac', '1', wav,
  ]);
  return wav;
}

// Writes narration (one dhvani clip per scene, placed at its start time) and music into jobDir.
// Returns { mode, narration?, music? }. Throws a stage 'audio' error (400 with findings) when a clip is too long.
async function buildAudio(props, audioScenes, jobDir) {
  const mode = audioMode({ narration: props.narration, music: props.music });
  const audio = { mode };
  if (mode === 'none') return audio;

  if (props.narration) {
    if (PROJECT_DIR) {
      const script = props.scenes
        .map((scene, i) => `## Scene ${i}\n\n${scene.text}. ${scene.sub || ''}`)
        .join('\n\n');
      await writeNarrationScript(PROJECT_DIR, path.basename(jobDir), script);
    }
    const clips = [];
    for (let i = 0; i < audioScenes.length; i++) {
      const scene = props.scenes[i];
      const wav = await narrateScene(`${scene.text}. ${scene.sub || ''}`, jobDir, i, props.narration_voice);
      clips.push({ file: wav, startSeconds: audioScenes[i].start });
    }
    const durations = [];
    for (const clip of clips) {
      durations.push(await probeSeconds(clip.file));
    }
    const check = planNarration(audioScenes, durations);
    if (!check.ok) {
      throw stageError(400, 'audio', 'narration check failed', { findings: check.findings });
    }
    audio.narration = path.join(jobDir, 'narration.wav');
    await run(FFMPEG_BIN, narrationArgs({ clips, totalSeconds: props.duration, out: audio.narration }));
  }

  if (props.music) {
    audio.music = path.join(jobDir, 'music.wav');
    await run(FFMPEG_BIN, musicArgs({ totalSeconds: props.duration, out: audio.music }));
  }
  return audio;
}

// Runs hyperframes render in jobDir with extra args. Failures are render stage errors carrying the output tail.
function renderHyperframes(jobDir, args, timeoutMs = RENDER_TIMEOUT_MS) {
  return execFileAsync(
    process.execPath,
    [HF_BIN, 'render', ...args],
    { cwd: jobDir, timeout: timeoutMs, maxBuffer: 16 * 1024 * 1024 },
  ).catch((err) => {
    const tail = `${err.stdout || ''}${err.stderr || ''}`.trim().slice(-600);
    throw stageError(500, 'render', `hyperframes render failed: ${tail}`, {
      stderrTail: tailLines(err.stderr, LOG_TAIL_LINES),
    });
  });
}

// Review sheet for a finished job film (D41): one PNG of 16 frames spread over the whole film, beside the film.
// Best effort: a failure is logged and returns null, so the film itself still counts as rendered.
async function makeContactSheet(videoPath, jobId, seconds, log) {
  const sheetPath = path.join(OUTPUT_DIR, jobContactSheetRel(jobId));
  try {
    await run(FFMPEG_BIN, buildContactSheetArgs({
      input: videoPath,
      output: sheetPath,
      fps: contactSheetFps(seconds),
    }));
    return jobContactSheetUrl(jobId);
  } catch (err) {
    log.contact_sheet_error = err.message;
    return null;
  }
}

// Hardware floor and disk gate before a render starts. Does nothing unless GATES_ENFORCE is "1".
async function runPreflight(props) {
  if (!GATES_ENFORCE) return;
  const hardware = await measureHardware(WORK_DIR);
  const freeBytes = await freeBytesAt(WORK_DIR);
  const frames = framesFor(props.duration, props.fps);
  const failure = preflightFailure({ enforce: true, hardware, freeBytes, frames });
  if (failure) throw stageError(failure.status, failure.stage, failure.message, { findings: failure.findings });
}

// WCAG 2.3.1 check on the finished MP4 (D49). Frames are decoded to 160x90 RGBA (57600 bytes per frame), so a
// 60 s film at 30 fps holds about 104 MB in memory. The check measures mean luminance per frame.
// Assumed frame size: 160x90 RGBA. Not yet run against a real MP4: the extraction path is unverified until a render runs with GATES_ENFORCE=1.
async function flashCheckVideo(videoPath, fps, jobDir) {
  const W = 160;
  const H = 90;
  const raw = path.join(jobDir, 'flash-check.rgba');
  await run(FFMPEG_BIN, ['-y', '-i', videoPath, '-vf', `scale=${W}:${H}`, '-f', 'rawvideo', '-pix_fmt', 'rgba', raw]);
  const buf = await readFile(raw);
  await rm(raw, { force: true });
  const size = W * H * 4;
  const frames = [];
  for (let o = 0; o + size <= buf.length; o += size) frames.push({ rgba: buf.subarray(o, o + size) });
  return checkFlashes(frames, fps);
}

// With a jobId the work folder is WORK_DIR/<jobId> and survives a failed render, so a retry reuses its segments.
async function renderJob(props, audioScenes, log, jobId, opts = {}) {
  const { blurSamples = 32, resolution = '1080p', preset = null, templateDir = TEMPLATE_DIR, templateParams = null, compositionFile = 'index.html', audioFile = null } = opts;
  const id = jobId ?? randomUUID();
  log.id = id;
  const jobDir = path.join(WORK_DIR, id);
  const started = Date.now();
  let ok = false;
  await mkdir(jobDir, { recursive: true });
  try {
    await runPreflight(props);
    await cp(templateDir, jobDir, { recursive: true });
    // HyperFrames renders index.html; a template may name its composition file in its manifest (D50).
    if (compositionFile !== 'index.html') {
      await cp(path.join(jobDir, compositionFile), path.join(jobDir, 'index.html'));
    }
    // HyperFrames reads the length from the static HTML, so write it there per job.
    const htmlPath = path.join(jobDir, 'index.html');
    const html = await readFile(htmlPath, 'utf8');
    let page = html.replace(/data-duration="[0-9.]+"/, `data-duration="${props.duration}"`);
    // Motion blur is on in the template at 32 samples; 0 switches it off and any other value sets the sample count.
    if (blurSamples === 0) page = page.replace('data-motion-blur="on"', 'data-motion-blur="off"');
    else page = page.replace('data-motion-blur-samples="32"', `data-motion-blur-samples="${blurSamples}"`);
    await writeFile(htmlPath, page);
    await writeFile(path.join(jobDir, 'props.js'), propsToJs(props));
    // Template parameters (D50): the composition reads window.__templateParams from this file.
    if (templateParams) {
      await writeFile(path.join(jobDir, 'template-params.js'), `window.__templateParams = ${JSON.stringify(templateParams)};\n`);
    }
    await cp(GSAP_FILE, path.join(jobDir, 'gsap.min.js'));

    // Audio is built before the render, so a narration that is too long fails without starting Chromium.
    // A preview (audioFile) muxes the given G4 voice sample instead of narrating the scenes again.
    const audio = audioFile
      ? { mode: 'narration', narration: audioFile }
      : await atStage('audio', () => buildAudio(props, audioScenes, jobDir));

    let video = path.join(jobDir, 'video.mp4');
    let segmentsReused = 0;
    // Segments are used only when the scene spans cover the whole film; a gap would make the joined MP4 shorter than the film.
    const spans = planSegments(audioScenes, props.duration);
    if (SEGMENTS_FPS_OK.includes(props.fps) && coversDuration(spans, props.duration)) {
      // One MP4 per scene span; finished segments are kept, so a retry with the same jobId skips them.
      const segDir = path.join(jobDir, 'segments');
      await mkdir(segDir, { recursive: true });
      // Segments made with other motion-blur or resolution settings must not be joined into this film.
      const key = settingsKey({ blurSamples, resolution });
      const keyFile = path.join(segDir, 'settings.key');
      if ((await readFile(keyFile, 'utf8').catch(() => null)) !== key) {
        await rm(segDir, { recursive: true, force: true });
        await mkdir(segDir, { recursive: true });
        await writeFile(keyFile, key);
      }
      const totalFrames = framesFor(props.duration, props.fps);
      let doneFrames = 0;
      let elapsedMs = 0;
      let measuredFps = null; // frames per second measured on the segments this request rendered
      const files = [];
      for (const { index, start, end } of spans) {
        const seg = path.join(segDir, `seg-${index}.mp4`);
        files.push(seg);
        const frames = framesFor(end - start, props.fps);
        if (segmentIsValid(await stat(seg).catch(() => null))) {
          segmentsReused++;
          doneFrames += frames;
          continue;
        }
        if (!fitsBudget({ elapsedMs, remainingFrames: totalFrames - doneFrames, measuredFps, budgetMs: JOB_BUDGET_MS })) {
          throw stageError(409, 'budget',
            `projected render time is over the ${Math.round(JOB_BUDGET_MS / 1000)} s job budget. Re-POST the same job_id with a lower motion_blur_samples, or motion_blur_samples 0 to turn motion blur off. Finished segments are kept.`);
        }
        const tmp = path.join(segDir, `seg-${index}.tmp.mp4`);
        const t0 = Date.now();
        await atStage('render', () => renderHyperframes(jobDir, [
          '--output', tmp, '--fps', String(props.fps), '--start', String(start), '--end', String(end),
        ], segmentTimeoutMs(frames, measuredFps, RENDER_TIMEOUT_MS)));
        const took = Date.now() - t0;
        elapsedMs += took;
        measuredFps = frames / (took / 1000);
        doneFrames += frames;
        await rename(tmp, seg);
      }
      const list = path.join(segDir, 'list.txt');
      await writeFile(list, concatListText(files));
      await atStage('render', () => run(FFMPEG_BIN, [
        '-y', '-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', video,
      ]));
    } else {
      await atStage('render', () => renderHyperframes(jobDir, ['--output', 'video.mp4', '--fps', String(props.fps)]));
    }
    if (audio.mode !== 'none') {
      const muxed = path.join(jobDir, 'muxed.mp4');
      await atStage('audio', () => run(FFMPEG_BIN, muxArgs({
        videoFile: video,
        narrationFile: audio.narration,
        musicFile: audio.music,
        mode: audio.mode,
        out: muxed,
        totalSeconds: props.duration,
      })));
      video = muxed;
    }
    // Every output is re-encoded once with the D51 colour tags, with or without audio.
    const tagged = path.join(jobDir, 'tagged.mp4');
    await atStage('colour', () => run(FFMPEG_BIN, colourArgs({ input: video, out: tagged })));
    video = tagged;

    if (GATES_ENFORCE) {
      const flash = await atStage('flash', () => flashCheckVideo(video, props.fps, jobDir));
      const flashBlock = flashFailure({ enforce: true, findings: flash.pass ? [] : [flash] });
      if (flashBlock) throw stageError(flashBlock.status, flashBlock.stage, flashBlock.message, { findings: flashBlock.findings });
    }

    const outRel = preset ? jobOutputRel(id, preset) : `${id}.mp4`;
    const outPath = path.join(OUTPUT_DIR, outRel);
    await atStage('move', async () => {
      await mkdir(path.dirname(outPath), { recursive: true });
      await rename(video, outPath)
        .catch(async () => {
          // rename fails across devices (tmpfs to a bind mount); fall back to copy.
          await cp(video, outPath);
        });
    });
    const { size } = await stat(outPath);
    const contactSheet = preset ? await makeContactSheet(outPath, id, props.duration, log) : undefined;
    ok = true;
    return {
      id,
      file: outRel,
      url: preset ? jobOutputUrl(id, preset) : `/output/${outRel}`,
      bytes: size,
      seconds: Math.round((Date.now() - started) / 100) / 10,
      audio: audio.mode,
      job_id: id,
      segments_reused: segmentsReused,
      contact_sheet: contactSheet,
    };
  } finally {
    if (!jobId || ok) await rm(jobDir, { recursive: true, force: true });
  }
}

// A long job (over PART_MAX_SECONDS) is rendered as parts that each fit the props limits, then joined.
// Each part is a normal renderJob under <base>_p<k>; the joined film is OUTPUT_DIR/<base>.mp4.
// Parts that finished stay in OUTPUT_DIR if a later part fails, so a retry with the same job_id re-renders them.
async function renderParts(scenes, fps, log, jobId, opts) {
  const base = jobId ?? randomUUID();
  log.id = base;
  let groups;
  try {
    groups = planParts(scenes);
  } catch (err) {
    throw stageError(400, 'validate', err.message);
  }
  const partFiles = [];
  let segmentsReused = 0;
  let audioMode = 'none';
  const started = Date.now();
  for (let k = 0; k < groups.length; k++) {
    const [a, b] = groups[k];
    const checked = validateProps({ fps, scenes: scenes.slice(a, b) });
    if (!checked.ok) throw stageError(400, 'validate', checked.error);
    const timed = toTimeline(checked.props.scenes);
    // The last-scene rule applies to the film's final scene only. Each part is checked on its own timeline,
    // so a part's last scene is not the film's last scene unless this is the final part.
    const isFinalPart = k === groups.length - 1;
    const findings = checkScenes(timed).findings.filter(
      (f) => isFinalPart || f.rule !== CRAFT_RULES.LAST_SCENE,
    );
    if (applyCraftPolicy(checked.hasScenes, findings).reject) {
      throw stageError(400, 'craft', 'craft check failed', { findings });
    }
    const audioScenes = timed.map((s) => ({ id: s.id, start: s.start, seconds: s.duration }));
    const part = await renderJob(checked.props, audioScenes, { stage: null }, `${base}_p${k}`, opts);
    partFiles.push(path.join(OUTPUT_DIR, part.file));
    segmentsReused += part.segments_reused;
    audioMode = part.audio;
  }
  const joinDir = path.join(WORK_DIR, base);
  await mkdir(joinDir, { recursive: true });
  const list = path.join(joinDir, 'parts.txt');
  await writeFile(list, concatListText(partFiles));
  const outRel = jobOutputRel(base, JOB_PRESET);
  const outPath = path.join(OUTPUT_DIR, outRel);
  await atStage('move', async () => {
    await mkdir(path.dirname(outPath), { recursive: true });
    await run(FFMPEG_BIN, [
      '-y', '-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', outPath,
    ]);
  });
  await rm(joinDir, { recursive: true, force: true });
  for (const file of partFiles) await rm(file, { force: true });
  const { size } = await stat(outPath);
  const contactSheet = await makeContactSheet(outPath, base, totalSeconds(scenes), log);
  return {
    id: base,
    file: outRel,
    url: jobOutputUrl(base, JOB_PRESET),
    bytes: size,
    seconds: Math.round((Date.now() - started) / 100) / 10,
    audio: audioMode,
    job_id: base,
    segments_reused: segmentsReused,
    parts: groups.length,
    contact_sheet: contactSheet,
  };
}

app.post('/render', async (req, res) => {
  const log = req.renderLog;
  // job_id is not a render prop: it is removed from the body before validation and echo.
  let body = req.body;
  let jobId;
  if (body && typeof body === 'object' && 'job_id' in body) {
    ({ job_id: jobId, ...body } = body);
  }
  if (jobId != null && !(typeof jobId === 'string' && JOB_ID_RE.test(jobId))) {
    log.stage = 'validate';
    log.error = 'bad job_id';
    return res.status(400).json({ error: 'bad job_id' });
  }
  // motion_blur_samples and resolution are render options (D54), not props: removed before validation and echo.
  let blurRaw;
  let resRaw;
  if (body && typeof body === 'object' && ('motion_blur_samples' in body || 'resolution' in body)) {
    ({ motion_blur_samples: blurRaw, resolution: resRaw, ...body } = body);
  }
  const blur = parseMotionBlurSamples(blurRaw);
  const res1080 = parseResolution(resRaw);
  if (!blur.ok || !res1080.ok) {
    const error = !blur.ok ? blur.error : res1080.error;
    log.stage = 'validate';
    log.error = error;
    return res.status(400).json({ error });
  }
  // Optional template (D50, handoff item 1): removed before props validation. Absent means composition/index.html.
  // A job.json body (schema_version present) keeps its own `template` name for the job schema (D9); it is not the opt-in object.
  let templateRaw;
  if (body && typeof body === 'object' && 'template' in body && !('schema_version' in body)) {
    ({ template: templateRaw, ...body } = body);
  }
  let tpl = { ok: true, entry: null, parameters: {} };
  if (templateRaw !== undefined) {
    let registry;
    try {
      registry = await getTemplateRegistry();
    } catch (err) {
      log.stage = 'validate';
      log.error = `template registry failed to load: ${err.message}`;
      return res.status(500).json({ error: log.error });
    }
    tpl = parseRenderTemplate(templateRaw, registry, JOB_PRESET);
    if (!tpl.ok) {
      log.stage = 'validate';
      log.error = tpl.error;
      return res.status(400).json({ error: tpl.error });
    }
  }
  // A job.json body (schema_version present) takes the gated path: it is validated, every gate before the
  // full render must be approved against its artifact, then it becomes a props body (D9, D39).
  let gatedJob = false;
  let gatedDestination = null;
  if (body && typeof body === 'object' && 'schema_version' in body) {
    if (templateRaw !== undefined) {
      log.stage = 'validate';
      log.error = 'template is not supported on a job.json body yet';
      return res.status(400).json({ error: log.error });
    }
    const gated = await gateJob(body, { artifactRoot: ARTIFACT_DIR, approvalsPath: APPROVALS_PATH });
    if (!gated.ok) {
      log.stage = 'gate';
      log.error = gated.payload.error;
      return res.status(gated.status).json(gated.payload);
    }
    body = gated.body;
    gatedJob = true;
    gatedDestination = gated.destination;
  }
  if (gatedJob && totalSeconds(body.scenes) > PART_MAX_SECONDS) {
    try {
      const result = await enqueue(() => renderParts(body.scenes, body.fps, log, jobId ?? undefined, {
        blurSamples: blur.value,
        resolution: res1080.value,
      }));
      return res.status(201).json({
        ...result,
        motion_blur_samples: blur.value,
        props: body,
        warnings: [],
      });
    } catch (err) {
      log.stage = err.stage || null;
      log.error = err.message;
      log.stderr_tail = err.stderrTail || null;
      const out = { error: err.message };
      if (err.findings) {
        out.stage = err.stage;
        out.findings = err.findings;
      }
      return res.status(err.status || 500).json(out);
    }
  }
  const checked = validateProps(body);
  if (!checked.ok) {
    log.stage = 'validate';
    log.error = checked.error;
    return res.status(400).json({ error: checked.error });
  }

  const timed = toTimeline(checked.props.scenes);
  const craft = checkScenes(timed);
  const policy = applyCraftPolicy(checked.hasScenes, craft.findings);
  if (policy.reject) {
    log.stage = 'craft';
    log.error = 'craft check failed';
    return res.status(400).json({ error: 'craft check failed', findings: craft.findings });
  }

  const audioScenes = timed.map((s) => ({ id: s.id, start: s.start, seconds: s.duration }));
  try {
    const result = await enqueue(() => renderJob(checked.props, audioScenes, log, jobId ?? undefined, {
      blurSamples: blur.value,
      resolution: res1080.value,
      preset: gatedJob ? gatedDestination : null,
      templateDir: tpl.entry ? tpl.entry.dir : (gatedDestination === 'shorts' ? SHORTS_TEMPLATE_DIR : TEMPLATE_DIR),
      templateParams: tpl.entry ? tpl.parameters : null,
      compositionFile: tpl.entry ? tpl.entry.manifest.composition : 'index.html',
    }));
    res.status(201).json({
      ...result,
      template: tpl.entry ? { id: tpl.entry.manifest.id, version: tpl.entry.version } : null,
      motion_blur_samples: blur.value,
      props: echoProps(body, checked.props),
      warnings: policy.warnings,
    });
  } catch (err) {
    log.stage = err.stage || null;
    log.error = err.message;
    log.stderr_tail = err.stderrTail || null;
    const body = { error: err.message };
    if (err.findings) {
      body.stage = err.stage;
      body.findings = err.findings;
    }
    res.status(err.status || 500).json(body);
  }
});

// G6 preview (D59, D64). Renders the first 60 s of a job.json body through renderJob with the G4 voice sample as
// its audio. The approval check runs after the sample is built and before any render: G1 to G3 and G4 must be
// approved, and G4 against the SHA-256 of the sample. The render writes to OUTPUT_DIR/<job_id>/preview/preview.mp4.
async function renderPreviewFilm(props, { audioFile, jobId, log }) {
  const checked = validateProps(props);
  if (!checked.ok) throw stageError(400, 'validate', checked.error);
  const timed = toTimeline(checked.props.scenes);
  const craft = checkScenes(timed);
  const policy = applyCraftPolicy(checked.hasScenes, craft.findings);
  if (policy.reject) throw stageError(400, 'craft', 'craft check failed', { findings: craft.findings });
  const audioScenes = timed.map((s) => ({ id: s.id, start: s.start, seconds: s.duration }));
  // Runs inside the queue slot the preview route already holds (POST /preview), so it is not enqueued again.
  const result = await renderJob(checked.props, audioScenes, log, `${jobId}-preview`, {
    blurSamples: parseMotionBlurSamples(undefined).value,
    resolution: parseResolution(undefined).value,
    audioFile,
  });
  return { file: path.join(OUTPUT_DIR, result.file) };
}

app.post('/preview', async (req, res) => {
  const log = req.renderLog;
  let body = req.body;
  let jobId;
  if (body && typeof body === 'object' && 'job_id' in body) {
    ({ job_id: jobId, ...body } = body);
  }
  if (typeof jobId !== 'string' || !JOB_ID_RE.test(jobId)) {
    log.stage = 'validate';
    log.error = 'bad job_id';
    return res.status(400).json({ error: 'bad job_id' });
  }
  if (!body || typeof body !== 'object' || !('schema_version' in body)) {
    log.stage = 'validate';
    log.error = 'a preview needs a job.json body';
    return res.status(400).json({ error: 'a preview needs a job.json body (schema_version)' });
  }
  if (!ARTIFACT_DIR || !APPROVALS_PATH) {
    log.stage = 'gate';
    log.error = 'previews need ARTIFACT_DIR and APPROVALS_PATH set';
    return res.status(503).json({ error: log.error });
  }
  try {
    const result = await enqueue(() => buildPreview(body, {
      baseUrl: DHVANI_URL,
      outDir: path.join(OUTPUT_DIR, jobId, 'preview'),
      checkApproval: (sample) => checkG4Approval(body, { artifactRoot: ARTIFACT_DIR, approvalsPath: APPROVALS_PATH, sample }),
      render: (props, opts) => renderPreviewFilm(props, { ...opts, jobId, log }),
    }));
    res.status(201).json({
      job_id: jobId,
      seconds: result.seconds,
      url: `/output/${jobId}/preview/${path.basename(result.file)}`,
    });
  } catch (err) {
    if (err instanceof PreviewRefused) {
      log.stage = 'gate';
      log.error = err.payload.error;
      return res.status(err.status).json(err.payload);
    }
    log.stage = err.stage || null;
    log.error = err.message;
    log.stderr_tail = err.stderrTail || null;
    const out = { error: err.message };
    if (err.findings) {
      out.stage = err.stage;
      out.findings = err.findings;
    }
    res.status(err.status || 500).json(out);
  }
});

app.use((_req, res) => res.status(404).json({ error: 'not found' }));

// Malformed JSON and oversized bodies come from express.json; they are answered and logged as validation errors.
app.use((err, req, res, next) => {
  if (res.headersSent) return next(err);
  const status = err.status || err.statusCode || 500;
  if (req.renderLog) {
    if (status < 500) req.renderLog.stage = 'validate';
    req.renderLog.error = err.message;
  }
  res.status(status).json({ error: status < 500 ? err.message : 'internal error' });
});

await mkdir(WORK_DIR, { recursive: true });
app.listen(PORT, () => {
  console.log(`render-engine listening on :${PORT}, output ${OUTPUT_DIR}`);
});
