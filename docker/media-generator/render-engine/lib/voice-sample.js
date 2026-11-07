// G4 voice sample: the first 60 seconds of the job's narration, spoken with the G3 voice (D55, D61).
// Parts are synthesized scene by scene through dhvani until their total length covers the target, then
// joined by ffmpeg and trimmed to the target. The WAV duration is read from the header, so no ffprobe is needed.

import { execFile } from 'node:child_process';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { promisify } from 'node:util';
import { synthesizeScene } from './dhvani.js';
import { checkVoiceChoice } from './voice-choice.js';

const execFileAsync = promisify(execFile);

export const SAMPLE_SECONDS = 60;
export const SAMPLE_RATE = 22050;

// Decides how many leading parts cover the target. Returns {ok, count, seconds, available}:
// count is the fewest leading parts whose total reaches target (all parts when it cannot), seconds is their
// total, and available is the total of every part given.
export function planSampleWindow(durations, target = SAMPLE_SECONDS) {
  if (!Array.isArray(durations)) throw new Error('planSampleWindow: durations must be an array');
  for (const d of durations) {
    if (typeof d !== 'number' || !Number.isFinite(d) || d < 0) {
      throw new Error(`planSampleWindow: invalid duration ${JSON.stringify(d)}`);
    }
  }
  const available = durations.reduce((sum, d) => sum + d, 0);
  let seconds = 0;
  for (let i = 0; i < durations.length; i += 1) {
    seconds += durations[i];
    if (seconds >= target) {
      return { ok: true, count: i + 1, seconds, available };
    }
  }
  return { ok: false, count: durations.length, seconds: available, available };
}

// Reads the duration of a PCM WAV from its header: byte count of the data chunk over the byte rate.
export function wavSeconds(buf) {
  if (!Buffer.isBuffer(buf) || buf.length < 12) throw new Error('wavSeconds: not a WAV buffer');
  if (buf.toString('ascii', 0, 4) !== 'RIFF' || buf.toString('ascii', 8, 12) !== 'WAVE') {
    throw new Error('wavSeconds: missing RIFF/WAVE header');
  }
  let byteRate = 0;
  let offset = 12;
  while (offset + 8 <= buf.length) {
    const id = buf.toString('ascii', offset, offset + 4);
    const size = buf.readUInt32LE(offset + 4);
    const body = offset + 8;
    if (id === 'fmt ') {
      if (body + 12 > buf.length) throw new Error('wavSeconds: truncated fmt chunk');
      byteRate = buf.readUInt32LE(body + 8);
    } else if (id === 'data') {
      if (!byteRate) throw new Error('wavSeconds: data chunk before fmt chunk');
      // A streamed header may carry a placeholder size: count what is actually there.
      const available = Math.min(size, buf.length - body);
      return available / byteRate;
    }
    offset = body + size + (size % 2);
  }
  throw new Error('wavSeconds: no data chunk');
}

// The text narrated for one scene: its title, a full stop, then its body.
export function narrationFor(scene) {
  return `${scene.title}. ${scene.body || ''}`;
}

// Joins the used parts into one WAV of at most SAMPLE_SECONDS, mono 22050 Hz.
function concatArgs(partFiles, outFile) {
  const inputs = [];
  const labels = [];
  partFiles.forEach((file, i) => {
    inputs.push('-i', file);
    labels.push(`[${i}:a]`);
  });
  const filter = `${labels.join('')}concat=n=${partFiles.length}:v=0:a=1,atrim=end=${SAMPLE_SECONDS}`;
  return [
    '-y',
    '-hide_banner',
    '-loglevel', 'error',
    ...inputs,
    '-filter_complex', filter,
    '-ar', String(SAMPLE_RATE),
    '-ac', '1',
    outFile,
  ];
}

function defaultRunFfmpeg(args) {
  const bin = process.env.FFMPEG_BIN || 'ffmpeg';
  return execFileAsync(bin, args);
}

// Builds outDir/voice-sample.wav from the job's narration. Returns {file, seconds}.
export async function buildVoiceSample(job, {
  baseUrl,
  outDir,
  fetchImpl,
  runFfmpeg = defaultRunFfmpeg,
} = {}) {
  if (!baseUrl) throw new Error('buildVoiceSample: baseUrl is required');
  if (!outDir) throw new Error('buildVoiceSample: outDir is required');

  const choice = checkVoiceChoice(job);
  if (!choice.ok) throw new Error(choice.error);
  const voice = choice.voice ?? (process.env.DHVANI_VOICE || 'af_heart');

  const scenes = job && Array.isArray(job.scenes) ? job.scenes : [];
  if (scenes.length === 0) throw new Error('buildVoiceSample: job has no scenes to narrate');

  const parts = [];
  const durations = [];
  let window = planSampleWindow(durations, SAMPLE_SECONDS);
  for (const scene of scenes) {
    const buffers = await synthesizeScene(narrationFor(scene), {
      baseUrl,
      voice,
      speed: 1,
      fetchImpl,
    });
    for (const buf of buffers) {
      parts.push(buf);
      durations.push(wavSeconds(buf));
    }
    window = planSampleWindow(durations, SAMPLE_SECONDS);
    if (window.ok) break;
  }
  if (!window.ok) {
    throw new Error(
      `narration too short for a voice sample: ${window.available.toFixed(1)} s available, ${SAMPLE_SECONDS} s needed`,
    );
  }

  await mkdir(outDir, { recursive: true });
  const partsDir = await mkdtemp(path.join(outDir, 'voice-sample-parts-'));
  const outFile = path.join(outDir, 'voice-sample.wav');
  try {
    const partFiles = [];
    for (let i = 0; i < window.count; i += 1) {
      const file = path.join(partsDir, `part-${String(i).padStart(4, '0')}.wav`);
      await writeFile(file, parts[i]);
      partFiles.push(file);
    }
    await runFfmpeg(concatArgs(partFiles, outFile));
  } finally {
    await rm(partsDir, { recursive: true, force: true });
  }
  return { file: outFile, seconds: SAMPLE_SECONDS };
}
