// Smoke render (D50): every claimed template x preset renders a 2-second clip with HyperFrames and ffprobe
// confirms the size and length. It needs the HyperFrames package, gsap and ffprobe, so it is off by default:
// run it with TEMPLATE_SMOKE=1 inside the media-generator image.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cp, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createRequire } from 'node:module';
import { loadRegistry, KNOWN_PRESETS } from '../lib/template-registry.js';
import { presets } from '../lib/job-schema.js';

const execFileAsync = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SMOKE = process.env.TEMPLATE_SMOKE === '1';
const FFPROBE = process.env.FFPROBE_BIN || 'ffprobe';
const FFMPEG = process.env.FFMPEG_BIN || 'ffmpeg';
const CLIP_SECONDS = 2;

const registry = await loadRegistry(root);

for (const [id, entry] of registry.templates) {
  for (const preset of KNOWN_PRESETS) {
    const claims = entry.manifest.supported_presets.includes(preset);
    let skip = false;
    if (!claims) skip = `${id} does not claim ${preset}`;
    else if (!SMOKE) skip = 'set TEMPLATE_SMOKE=1 (needs HyperFrames, gsap and ffprobe)';

    test(`smoke render ${id} ${entry.version} x ${preset}`, { skip, timeout: 300000 }, async () => {
      const require = createRequire(import.meta.url);
      const hfBin = path.join(path.dirname(require.resolve('hyperframes/package.json')), 'bin', 'hyperframes.mjs');
      const gsapFile = require.resolve('gsap/dist/gsap.min.js');
      const { width, height, fps } = presets[preset];

      const dir = await mkdtemp(path.join(os.tmpdir(), 'tpl-smoke-'));
      try {
        // Set the frame size and length for this preset; the composition itself stays unchanged on disk.
        let html = await readFile(path.join(entry.dir, entry.manifest.composition), 'utf8');
        html = html
          .replace(/data-width="\d+"/, `data-width="${width}"`)
          .replace(/data-height="\d+"/, `data-height="${height}"`)
          .replace(/data-duration="[\d.]+"/, `data-duration="${CLIP_SECONDS}"`);
        await writeFile(path.join(dir, 'index.html'), html);
        await cp(gsapFile, path.join(dir, 'gsap.min.js'));
        // A template that takes a background gets a red one here, so the frame check below can read it back.
        const takesBackground = Boolean(entry.manifest.parameters?.properties?.background);
        if (takesBackground) {
          await writeFile(path.join(dir, 'template-params.js'),
            'window.__templateParams = {"background":"#ff0000","accent":"#00ff00"};\n');
        }

        await execFileAsync(process.execPath, [hfBin, 'render', '--output', 'video.mp4', '--fps', String(fps)], {
          cwd: dir,
          timeout: 280000,
          maxBuffer: 16 * 1024 * 1024,
        });

        const { stdout } = await execFileAsync(FFPROBE, [
          '-v', 'error', '-select_streams', 'v:0',
          '-show_entries', 'stream=width,height:format=duration', '-of', 'json',
          path.join(dir, 'video.mp4'),
        ]);
        const info = JSON.parse(stdout);
        assert.equal(info.streams[0].width, width);
        assert.equal(info.streams[0].height, height);
        assert.ok(Math.abs(Number(info.format.duration) - CLIP_SECONDS) < 0.25,
          `duration ${info.format.duration}s, expected about ${CLIP_SECONDS}s`);

        if (takesBackground) {
          // Average the top-left 40x40 corner of a frame: it should be the red background from template-params.js.
          const { stdout: px } = await execFileAsync(FFMPEG, [
            '-v', 'error', '-ss', '1', '-i', path.join(dir, 'video.mp4'), '-frames:v', '1',
            '-vf', 'crop=40:40:0:0,scale=1:1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-',
          ], { encoding: 'buffer', maxBuffer: 1024 * 1024 });
          const [r, g, b] = px;
          assert.ok(r > 230 && g < 25 && b < 25, `corner pixel rgb(${r},${g},${b}), expected red background`);
        }
      } finally {
        // Windows can hold a file for a moment after the render child exits; retry instead of failing the test.
        await rm(dir, { recursive: true, force: true, maxRetries: 10, retryDelay: 500 });
      }
    });
  }
}
