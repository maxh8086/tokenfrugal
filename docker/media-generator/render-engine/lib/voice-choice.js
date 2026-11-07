// Narration voice choice (D55). The G3 choice is named "narration voice" in the job schema and in
// errors. A job may name one Kokoro voice (for example af_heart or bm_george) through voice_profile.
// Absent or null means the service default voice. Pure: no I/O.

const VOICE_PATTERN = /^[a-z]{2}_[a-z0-9]+$/;

// Returns {ok: true, voice} with voice null for the service default, or {ok: false, error}.
export function checkVoiceChoice(job) {
  const value = job ? job.voice_profile : undefined;
  if (value === undefined || value === null) {
    return { ok: true, voice: null };
  }
  if (typeof value === 'string' && VOICE_PATTERN.test(value)) {
    return { ok: true, voice: value };
  }
  return {
    ok: false,
    error: `invalid narration voice ${JSON.stringify(value)}: use a voice name like af_heart, or omit it for the default`,
  };
}
