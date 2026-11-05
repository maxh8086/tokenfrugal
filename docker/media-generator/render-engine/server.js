// POST /render: renders composition/index.html with the given props to an MP4 in OUTPUT_DIR.
import express from 'express';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { randomUUID } from 'node:crypto';
import { cp, mkdir, readFile, rename, rm, writeFile, stat } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { validateProps, propsToJs } from './lib/props.js';

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

const app = express();
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

async function renderJob(props) {
  const id = randomUUID();
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

    await execFileAsync(
      process.execPath,
      [HF_BIN, 'render', '--output', 'video.mp4'],
      { cwd: jobDir, timeout: RENDER_TIMEOUT_MS, maxBuffer: 16 * 1024 * 1024 },
    ).catch((err) => {
      const tail = `${err.stdout || ''}${err.stderr || ''}`.trim().slice(-600);
      throw Object.assign(new Error(`hyperframes render failed: ${tail}`), { status: 500 });
    });

    const outName = `${id}.mp4`;
    await mkdir(OUTPUT_DIR, { recursive: true });
    await rename(path.join(jobDir, 'video.mp4'), path.join(OUTPUT_DIR, outName))
      .catch(async () => {
        // rename fails across devices (tmpfs to a bind mount); fall back to copy.
        await cp(path.join(jobDir, 'video.mp4'), path.join(OUTPUT_DIR, outName));
      });
    const { size } = await stat(path.join(OUTPUT_DIR, outName));
    return {
      id,
      file: outName,
      url: `/output/${outName}`,
      bytes: size,
      seconds: Math.round((Date.now() - started) / 100) / 10,
    };
  } finally {
    await rm(jobDir, { recursive: true, force: true });
  }
}

app.post('/render', async (req, res) => {
  const checked = validateProps(req.body);
  if (!checked.ok) {
    return res.status(400).json({ error: checked.error });
  }
  try {
    const result = await enqueue(() => renderJob(checked.props));
    res.status(201).json({ ...result, props: checked.props });
  } catch (err) {
    res.status(err.status || 500).json({ error: err.message });
  }
});

app.use((_req, res) => res.status(404).json({ error: 'not found' }));

await mkdir(WORK_DIR, { recursive: true });
app.listen(PORT, () => {
  console.log(`render-engine listening on :${PORT}, output ${OUTPUT_DIR}`);
});
