// POST /render: renders composition/index.html with the given props to an MP4 in OUTPUT_DIR.
// Optional narration (Piper TTS) and music (deterministic ffmpeg bed) are muxed into the film.
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
import { checkScenes, toTimeline, applyCraftPolicy } from './lib/craft-check.js';
import { planNarration, narrationArgs, musicArgs, muxArgs, audioMode } from './lib/audio-plan.js';
import { writeLog, tailLines } from './lib/log.js';

const execFileAsync = promisify(execFile);
const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

const PORT = Number(process.env.PORT || 3000);
const OUTPUT_DIR = process.env.OUTPUT_DIR || '/output';
const WORK_DIR = process.env.WORK_DIR || path.join(os.tmpdir(), 'hf-jobs');
const TEMPLATE_DIR = path.join(here, 'composition');
const GSAP_FILE = require.resolve('gsap/dist/gsap.min.js');
const HF_BIN = path.join(path.dirname(require.resolve('hyperframes/package.json')), 'bin', 'hyperframes.mjs');
const RENDER_TIMEOUT_MS = Number(process.env.RENDER_TIMEOUT_MS || 600_000);
const PIPER_BIN = process.env.PIPER_BIN || '/opt/voice/bin/piper';
const PIPER_MODEL = process.env.PIPER_MODEL || '/opt/voices/en_US-lessac-medium.onnx';
const FFMPEG_BIN = process.env.FFMPEG_BIN || 'ffmpeg';
const FFPROBE_BIN = process.env.FFPROBE_BIN || 'ffprobe';
const LOG_TAIL_LINES = 40;

const LOGGED_ROUTES = new Set(['GET /health', 'POST /render']);

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

// Writes narration (one Piper clip per scene, placed at its start time) and music into jobDir.
// Returns { mode, narration?, music? }. Throws a stage 'audio' error (400 with findings) when a clip is too long.
async function buildAudio(props, audioScenes, jobDir) {
  const mode = audioMode({ narration: props.narration, music: props.music });
  const audio = { mode };
  if (mode === 'none') return audio;

  if (props.narration) {
    const clips = [];
    for (let i = 0; i < audioScenes.length; i++) {
      const scene = props.scenes[i];
      const wav = path.join(jobDir, `s${i}.wav`);
      await run(PIPER_BIN, ['--model', PIPER_MODEL, '--output_file', wav], {
        input: `${scene.text}. ${scene.sub || ''}`,
      });
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

async function renderJob(props, audioScenes, log) {
  const id = randomUUID();
  log.id = id;
  const jobDir = path.join(WORK_DIR, id);
  const started = Date.now();
  await mkdir(jobDir, { recursive: true });
  try {
    await cp(TEMPLATE_DIR, jobDir, { recursive: true });
    // HyperFrames reads the length from the static HTML, so write it there per job.
    const htmlPath = path.join(jobDir, 'index.html');
    const html = await readFile(htmlPath, 'utf8');
    await writeFile(htmlPath, html.replace('data-duration="3"', `data-duration="${props.duration}"`));
    await writeFile(path.join(jobDir, 'props.js'), propsToJs(props));
    await cp(GSAP_FILE, path.join(jobDir, 'gsap.min.js'));

    // Audio is built before the render, so a narration that is too long fails without starting Chromium.
    const audio = await atStage('audio', () => buildAudio(props, audioScenes, jobDir));

    await atStage('render', () => execFileAsync(
      process.execPath,
      [HF_BIN, 'render', '--output', 'video.mp4', '--fps', String(props.fps)],
      { cwd: jobDir, timeout: RENDER_TIMEOUT_MS, maxBuffer: 16 * 1024 * 1024 },
    ).catch((err) => {
      const tail = `${err.stdout || ''}${err.stderr || ''}`.trim().slice(-600);
      throw stageError(500, 'render', `hyperframes render failed: ${tail}`, {
        stderrTail: tailLines(err.stderr, LOG_TAIL_LINES),
      });
    }));

    let video = path.join(jobDir, 'video.mp4');
    if (audio.mode !== 'none') {
      const muxed = path.join(jobDir, 'muxed.mp4');
      await atStage('audio', () => run(FFMPEG_BIN, muxArgs({
        videoFile: video,
        narrationFile: audio.narration,
        musicFile: audio.music,
        mode: audio.mode,
        out: muxed,
      })));
      video = muxed;
    }

    const outName = `${id}.mp4`;
    await atStage('move', async () => {
      await mkdir(OUTPUT_DIR, { recursive: true });
      await rename(video, path.join(OUTPUT_DIR, outName))
        .catch(async () => {
          // rename fails across devices (tmpfs to a bind mount); fall back to copy.
          await cp(video, path.join(OUTPUT_DIR, outName));
        });
    });
    const { size } = await stat(path.join(OUTPUT_DIR, outName));
    return {
      id,
      file: outName,
      url: `/output/${outName}`,
      bytes: size,
      seconds: Math.round((Date.now() - started) / 100) / 10,
      audio: audio.mode,
    };
  } finally {
    await rm(jobDir, { recursive: true, force: true });
  }
}

app.post('/render', async (req, res) => {
  const log = req.renderLog;
  const checked = validateProps(req.body);
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
    const result = await enqueue(() => renderJob(checked.props, audioScenes, log));
    res.status(201).json({
      ...result,
      props: echoProps(req.body, checked.props),
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
