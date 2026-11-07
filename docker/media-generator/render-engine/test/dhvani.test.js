import { test } from 'node:test';
import assert from 'node:assert/strict';
import { splitForKokoro, synthesizeChunk, synthesizeScene } from '../lib/dhvani.js';

const WAV_BYTES = new Uint8Array([82, 73, 70, 70]);

function wavResponse() {
  return new Response(WAV_BYTES, { status: 200, headers: { 'content-type': 'audio/wav' } });
}

test('splitForKokoro keeps short text as one chunk', () => {
  assert.deepEqual(splitForKokoro('  Hello there. This is short.  '), ['Hello there. This is short.']);
});

test('splitForKokoro packs a 2500-character text into chunks of at most 900 and keeps word order', () => {
  const sentences = [];
  for (let i = 0; sentences.join(' ').length < 2500; i++) {
    sentences.push(`Sentence ${i} tells a short story about the film.`);
  }
  const text = sentences.join(' ');
  const chunks = splitForKokoro(text);
  assert.ok(chunks.length > 1);
  for (const chunk of chunks) {
    assert.ok(chunk.length <= 900, `chunk too long: ${chunk.length}`);
    assert.equal(chunk, chunk.trim());
    assert.ok(chunk.length > 0);
  }
  assert.deepEqual(chunks.join(' ').split(/\s+/), text.split(/\s+/));
});

test('splitForKokoro cuts a 1200-character word-run with no sentence end at a space', () => {
  const text = Array.from({ length: 120 }, (_, i) => (i === 119 ? 'abcdefghij' : 'abcdefghi')).join(' ');
  assert.equal(text.length, 1200);
  const chunks = splitForKokoro(text);
  assert.ok(chunks.length >= 2);
  for (const chunk of chunks) {
    assert.ok(chunk.length <= 900, `chunk too long: ${chunk.length}`);
    for (const word of chunk.split(' ')) {
      assert.ok(word === 'abcdefghi' || word === 'abcdefghij', `word split mid-way: ${word}`);
    }
  }
  assert.equal(chunks.join(' '), text);
});

test('splitForKokoro throws on empty text', () => {
  assert.throws(() => splitForKokoro(''), /empty/);
  assert.throws(() => splitForKokoro('   \n\t '), /empty/);
});

test('synthesizeScene returns one buffer per chunk and sends the right JSON body', async () => {
  const sentences = [];
  for (let i = 0; sentences.join(' ').length < 2000; i++) {
    sentences.push(`Line ${i} of the narration script goes here.`);
  }
  const text = sentences.join(' ');
  const expected = splitForKokoro(text);
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    return wavResponse();
  };

  const buffers = await synthesizeScene(text, {
    baseUrl: 'http://dhvani:8080/',
    voice: 'af_heart',
    speed: 1.1,
    fetchImpl,
  });

  assert.equal(buffers.length, expected.length);
  for (const buf of buffers) {
    assert.ok(Buffer.isBuffer(buf));
    assert.deepEqual([...buf], [82, 73, 70, 70]);
  }
  assert.equal(calls.length, expected.length);
  calls.forEach((call, i) => {
    assert.equal(call.url, 'http://dhvani:8080/api/kokoro/speak');
    assert.equal(call.init.method, 'POST');
    assert.deepEqual(JSON.parse(call.init.body), { text: expected[i], voice: 'af_heart', speed: 1.1 });
  });
});

test('synthesizeScene throws with the status when the response is not ok', async () => {
  const fetchImpl = async () => new Response(JSON.stringify({ error: 'engine down' }), {
    status: 500,
    headers: { 'content-type': 'application/json' },
  });
  await assert.rejects(
    synthesizeScene('A line.', { baseUrl: 'http://dhvani:8080', voice: 'af_heart', fetchImpl }),
    (err) => /500/.test(err.message) && /engine down/.test(err.message),
  );
});

test('synthesizeScene throws when the content-type is not audio/wav', async () => {
  const fetchImpl = async () => new Response('{}', {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
  await assert.rejects(
    synthesizeScene('A line.', { baseUrl: 'http://dhvani:8080', voice: 'af_heart', fetchImpl }),
    /audio\/wav/,
  );
});

test('synthesizeChunk returns one WAV buffer and sends the speed it is given', async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push(JSON.parse(init.body));
    return wavResponse();
  };
  const buf = await synthesizeChunk('One chunk.', {
    baseUrl: 'http://dhvani:8080',
    voice: 'af_heart',
    speed: 0.9,
    fetchImpl,
  });
  assert.ok(Buffer.isBuffer(buf));
  assert.deepEqual([...buf], [82, 73, 70, 70]);
  assert.deepEqual(calls, [{ text: 'One chunk.', voice: 'af_heart', speed: 0.9 }]);
});

test('synthesizeChunk refuses a missing baseUrl', async () => {
  await assert.rejects(synthesizeChunk('x', { voice: 'af_heart' }), /baseUrl is required/);
});
