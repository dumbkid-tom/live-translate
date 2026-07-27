const test = require('node:test');
const assert = require('node:assert');
const GeminiLiveProtocol = require('../../frontend/js/gemini-live-protocol.js');

test('parse setupComplete message', () => {
  const events = GeminiLiveProtocol.parseGeminiMessage({ setupComplete: {} });
  assert.strictEqual(events.length, 1);
  assert.strictEqual(events[0].type, 'setup_complete');
});

test('parse setupComplete message from JSON string', () => {
  const events = GeminiLiveProtocol.parseGeminiMessage('{\n  "setupComplete": {}\n}\n');
  assert.strictEqual(events.length, 1);
  assert.strictEqual(events[0].type, 'setup_complete');
});

test('parse setupComplete message from binary Buffer / ArrayBuffer', () => {
  const jsonStr = '{\n  "setupComplete": {}\n}\n';
  const buf = Buffer.from(jsonStr);
  const eventsBuf = GeminiLiveProtocol.parseGeminiMessage(buf);
  assert.strictEqual(eventsBuf.length, 1);
  assert.strictEqual(eventsBuf[0].type, 'setup_complete');

  const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  const eventsAb = GeminiLiveProtocol.parseGeminiMessage(ab);
  assert.strictEqual(eventsAb.length, 1);
  assert.strictEqual(eventsAb[0].type, 'setup_complete');
});

test('parse modelTurn text and audio', () => {
  const msg = {
    serverContent: {
      modelTurn: {
        parts: [
          { text: 'Hola mundo' },
          { inlineData: { mimeType: 'audio/pcm;rate=24000', data: 'ABC123Base64' } }
        ]
      }
    }
  };
  const events = GeminiLiveProtocol.parseGeminiMessage(msg);
  assert.strictEqual(events.length, 2);
  assert.strictEqual(events[0].type, 'text');
  assert.strictEqual(events[0].text, 'Hola mundo');
  assert.strictEqual(events[1].type, 'audio');
  assert.strictEqual(events[1].data, 'ABC123Base64');
});

test('parse inputAudioTranscription for source transcript', () => {
  const msg = {
    serverContent: {
      inputAudioTranscription: { text: 'Hello, how are you?' }
    }
  };
  const events = GeminiLiveProtocol.parseGeminiMessage(msg);
  assert.strictEqual(events.length, 1);
  assert.strictEqual(events[0].type, 'source_text');
  assert.strictEqual(events[0].text, 'Hello, how are you?');
});

test('parse interrupted and turnComplete', () => {
  const msg = {
    serverContent: {
      interrupted: true,
      turnComplete: true
    }
  };
  const events = GeminiLiveProtocol.parseGeminiMessage(msg);
  assert.strictEqual(events.length, 2);
  assert.strictEqual(events[0].type, 'interrupted');
  assert.strictEqual(events[1].type, 'turn_complete');
});

test('parse error message', () => {
  const events = GeminiLiveProtocol.parseGeminiMessage({ error: { code: 400, message: 'Invalid config' } });
  assert.strictEqual(events.length, 1);
  assert.strictEqual(events[0].type, 'error');
  assert.strictEqual(events[0].error.message, 'Invalid config');
});

test('buildAudioFrame structure', () => {
  const chunk = GeminiLiveProtocol.buildAudioFrame('PCM64DATA');
  assert.strictEqual(chunk.realtimeInput.audio.mimeType, 'audio/pcm;rate=16000');
  assert.strictEqual(chunk.realtimeInput.audio.data, 'PCM64DATA');
});

test('buildRealtimeAudioChunk structure', () => {
  const chunk = GeminiLiveProtocol.buildRealtimeAudioChunk('PCM64DATA');
  assert.strictEqual(chunk.realtimeInput.audio.mimeType, 'audio/pcm;rate=16000');
  assert.strictEqual(chunk.realtimeInput.audio.data, 'PCM64DATA');
});

test('buildTextFrame structure', () => {
  const chunk = GeminiLiveProtocol.buildTextFrame('Bonjour');
  assert.strictEqual(chunk.clientContent.turns[0].role, 'user');
  assert.strictEqual(chunk.clientContent.turns[0].parts[0].text, 'Bonjour');
  assert.strictEqual(chunk.clientContent.turnComplete, true);
});

test('buildRealtimeTextChunk structure', () => {
  const chunk = GeminiLiveProtocol.buildRealtimeTextChunk('Bonjour');
  assert.strictEqual(chunk.clientContent.turns[0].role, 'user');
  assert.strictEqual(chunk.clientContent.turns[0].parts[0].text, 'Bonjour');
  assert.strictEqual(chunk.clientContent.turnComplete, true);
});
