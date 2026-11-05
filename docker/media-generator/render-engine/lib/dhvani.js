// Narration through the dhvani service (Kokoro over HTTP, docker/dhvani/ui/server.py).
// Kokoro accepts at most 1000 characters per request, so each scene is split into chunks below MAX_CHUNK.

export const MAX_CHUNK = 900;

// Splits text at sentence ends, packing sentences greedily up to max characters. A sentence longer than max is
// cut at the last whitespace before max, or hard-cut at max when there is none.
export function splitForKokoro(text, max = MAX_CHUNK) {
  const trimmed = String(text ?? '').trim();
  if (!trimmed) throw new Error('splitForKokoro: text is empty');
  if (trimmed.length <= max) return [trimmed];

  const chunks = [];
  let current = '';
  const flush = () => {
    if (current) chunks.push(current);
    current = '';
  };

  for (const sentence of trimmed.split(/(?<=[.!?])\s+/)) {
    if (sentence.length > max) {
      flush();
      const pieces = hardSplit(sentence, max);
      chunks.push(...pieces.slice(0, -1));
      current = pieces[pieces.length - 1];
      continue;
    }
    if (current && current.length + 1 + sentence.length <= max) {
      current += ` ${sentence}`;
    } else {
      flush();
      current = sentence;
    }
  }
  flush();
  return chunks;
}

// Cuts an over-long sentence into pieces of at most max characters, preferring a cut at whitespace.
function hardSplit(sentence, max) {
  const pieces = [];
  let rest = sentence.trim();
  while (rest.length > max) {
    const window = rest.slice(0, max + 1);
    let cut = Math.max(window.lastIndexOf(' '), window.lastIndexOf('\n'), window.lastIndexOf('\t'));
    if (cut <= 0) cut = max;
    pieces.push(rest.slice(0, cut).trim());
    rest = rest.slice(cut).trim();
  }
  if (rest) pieces.push(rest);
  return pieces.filter(Boolean);
}

// Synthesizes one scene. Returns one WAV Buffer per chunk, in order.
export async function synthesizeScene(text, {
  baseUrl,
  voice,
  speed = 1,
  fetchImpl = fetch,
  timeoutMs = 120000,
} = {}) {
  if (!baseUrl) throw new Error('synthesizeScene: baseUrl is required');
  const endpoint = `${String(baseUrl).replace(/\/$/, '')}/api/kokoro/speak`;
  const buffers = [];
  for (const chunk of splitForKokoro(text)) {
    const res = await fetchImpl(endpoint, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text: chunk, voice, speed }),
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) {
      let detail = '';
      try {
        const body = await res.json();
        if (body && body.error) detail = `: ${body.error}`;
      } catch {
        // The body is not JSON; the status alone is reported.
      }
      throw new Error(`dhvani returned HTTP ${res.status}${detail}`);
    }
    const type = (res.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
    if (type !== 'audio/wav' && type !== 'audio/x-wav') {
      throw new Error(`dhvani returned content-type "${type || 'none'}", expected audio/wav`);
    }
    buffers.push(Buffer.from(await res.arrayBuffer()));
  }
  return buffers;
}
