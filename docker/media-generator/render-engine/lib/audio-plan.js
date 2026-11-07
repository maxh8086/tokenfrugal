// Narration and music planning for the render engine. Pure functions, no I/O: they check timings and build
// argv arrays for ffmpeg (run without a shell by the caller).

export const NARRATION_RULE = 'narration-too-long';

// Music bed: three sines, peak about -22 dBFS (10^(-22/20) = 0.0794), fade in 0.5 s, fade out 1 s. No randomness.
export const MUSIC = {
  sampleRate: 44100,
  fadeInSeconds: 0.5,
  fadeOutSeconds: 1,
  peakGain: 0.0794,
};

// D56: integrated loudness -16 LUFS, true peak -1.5 dBTP, loudness range 11.
export const LOUDNESS_FILTER = 'loudnorm=I=-16:TP=-1.5:LRA=11';

const round2 = (n) => Math.round(n * 100) / 100;

// scenes: [{id, start, seconds}]; durations: narration length in seconds per scene, same order.
// Returns { ok, findings }. A finding is raised when a narration clip is longer than its scene.
export function planNarration(scenes, durations) {
  if (!Array.isArray(scenes) || !Array.isArray(durations) || scenes.length !== durations.length) {
    throw new TypeError('planNarration needs one duration per scene');
  }
  const findings = [];
  scenes.forEach((scene, i) => {
    const narration = durations[i];
    if (narration > scene.seconds) {
      findings.push({
        scene: scene.id,
        rule: NARRATION_RULE,
        narrationSeconds: round2(narration),
        sceneSeconds: scene.seconds,
        message: `narration is ${round2(narration)}s, longer than the ${scene.seconds}s scene`,
      });
    }
  });
  return { ok: findings.length === 0, findings };
}

// clips: [{inputIndex, startSeconds}] (inputIndex is the ffmpeg input number of each wav).
// Returns a filter_complex string that delays each clip to its start time (adelay, ms) and mixes them.
// The output label is [narr]; apad keeps the track running to the length set by the caller.
export function narrationFilter(clips) {
  if (!Array.isArray(clips) || clips.length === 0) {
    throw new TypeError('narrationFilter needs at least one clip');
  }
  const parts = clips.map(
    (clip, k) => `[${clip.inputIndex}:a]adelay=${Math.round(clip.startSeconds * 1000)}:all=1[d${k}]`,
  );
  if (clips.length === 1) {
    parts.push('[d0]apad[narr]');
  } else {
    const inputs = clips.map((_, k) => `[d${k}]`).join('');
    parts.push(`${inputs}amix=inputs=${clips.length}:normalize=0:dropout_transition=0,apad[narr]`);
  }
  return parts.join(';');
}

// clips: [{file, startSeconds}]. argv for ffmpeg producing a stereo WAV of exactly totalSeconds.
export function narrationArgs({ clips, totalSeconds, out }) {
  const args = ['-y', '-nostdin'];
  for (const clip of clips) {
    args.push('-i', clip.file);
  }
  const filter = narrationFilter(clips.map((clip, k) => ({ inputIndex: k, startSeconds: clip.startSeconds })));
  args.push(
    '-filter_complex', filter,
    '-map', '[narr]',
    '-t', String(totalSeconds),
    '-ac', '2',
    '-ar', String(MUSIC.sampleRate),
    out,
  );
  return args;
}

// argv for the deterministic music bed: lavfi sines at 110, 165 and 220 Hz, scaled to about -22 dBFS,
// with a 0.5 s fade in and a 1 s fade out. The length is totalSeconds.
export function musicArgs({ totalSeconds, out }) {
  const T = Number(totalSeconds);
  const expr = `${MUSIC.peakGain}*(sin(2*PI*110*t)+sin(2*PI*165*t)+sin(2*PI*220*t))/3`;
  const source = `aevalsrc=${expr}:s=${MUSIC.sampleRate}:d=${T}`;
  const fadeOutStart = Math.max(0, T - MUSIC.fadeOutSeconds).toFixed(3);
  const af = `afade=t=in:st=0:d=${MUSIC.fadeInSeconds},afade=t=out:st=${fadeOutStart}:d=${MUSIC.fadeOutSeconds}`;
  return [
    '-y', '-nostdin',
    '-f', 'lavfi', '-i', source,
    '-af', af,
    '-ac', '2',
    '-ar', String(MUSIC.sampleRate),
    out,
  ];
}

// Which audio the film carries. Matches the "audio" field of the response.
export function audioMode({ narration, music }) {
  if (narration && music) return 'both';
  if (narration) return 'narration';
  if (music) return 'music';
  return 'none';
}

// argv for muxing the silent render with the narration and/or music WAV: video copied, audio AAC 192k stereo.
// The output length is set explicitly to totalSeconds (the film duration) with -t, not by the shorter stream.
// mode is 'narration', 'music' or 'both'.
export function muxArgs({ videoFile, narrationFile, musicFile, mode, out, totalSeconds }) {
  if (!Number.isFinite(totalSeconds) || totalSeconds <= 0) {
    throw new TypeError(`muxArgs needs a positive totalSeconds, got ${totalSeconds}`);
  }
  const args = ['-y', '-nostdin', '-i', videoFile];
  let audioMap;
  if (mode === 'both') {
    args.push('-i', narrationFile, '-i', musicFile);
    args.push(
      '-filter_complex', `[1:a][2:a]amix=inputs=2:normalize=0:dropout_transition=0,${LOUDNESS_FILTER}[aout]`,
    );
    audioMap = '[aout]';
  } else if (mode === 'narration') {
    args.push('-i', narrationFile);
    audioMap = '1:a:0';
  } else if (mode === 'music') {
    args.push('-i', musicFile);
    audioMap = '1:a:0';
  } else {
    throw new TypeError(`muxArgs needs mode narration, music or both, got ${mode}`);
  }
  args.push(
    '-map', '0:v:0',
    '-map', audioMap,
    ...(mode === 'both' ? [] : ['-af', LOUDNESS_FILTER]),
    '-c:v', 'copy',
    '-c:a', 'aac',
    '-b:a', '192k',
    '-ac', '2',
    '-t', String(totalSeconds),
    out,
  );
  return args;
}
