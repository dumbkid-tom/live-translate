# Technical Specification

## Root cause: turn-based versus simultaneous translation

The original behavior was turn-based because the general Live configuration
used automatic activity detection and a system prompt asking the model to
interpret. That configuration naturally waits for `silenceDurationMs` and a
`turnComplete` boundary before producing a complete response. Lowering the
silence threshold only shortens the wait; it does not change the model
contract, and it can fragment speech.

The implemented fix is to use the provider's translation-specific live model
and `translationConfig` for the simultaneous path. The target language is a
structured `targetLanguageCode`, not merely an instruction in a prompt. The
browser keeps sending `realtimeInput.audio` frames continuously, while the
model emits incremental `modelTurn`/`outputTranscription` content. This is why
the UI can translate while the speaker is still talking. Turn-based remains a
deliberate fallback rather than being treated as equivalent behavior.

## Components and data flow

```text
Browser UI
  ├─ POST /api/token ──> FastAPI TokenService ──> google-genai auth_tokens.create
  │                         │
  │                         └─ token + constrained setup + direct WSS URL
  └─ direct WSS with access_token ──> Gemini Live API
       ├─ setup
       ├─ realtimeInput.audio: base64 little-endian Int16, 16 kHz mono
       └─ serverContent: partial text, source transcript, 24 kHz PCM, events
```

`backend/config.py` loads `.env` and normalizes server, model, translation,
origin, and token settings. `backend/gemini_live.py` resolves language codes,
builds the two setup variants, and mints tokens. `backend/main.py` exposes
FastAPI endpoints, CORS, and in-memory per-IP rate limiting. Static files are
mounted at `/static`; `/` serves `frontend/index.html`.

## Token and setup protocol

The token endpoint accepts:

| Field | Meaning |
|---|---|
| `target_language` | Language name/code normalized to a primary or BCP-47 code |
| `source_language` | Optional source hint, primarily used by the fallback prompt |
| `mode` | `audio` or `text`; response modality remains audio at the provider |
| `model` | Optional model override |
| `translation_mode` | `simultaneous` or `turn_based` |
| `silence_duration_ms` | Fallback VAD setting; effective range 500–2000 ms |
| `echo_target_language` | Provider translation option for repeated target audio |
| `transcription_mode` | `verbatim` or `smart` (Live Transcribe speech-to-text) |
| `language_codes` | Optional BCP-47 codes (e.g. `["es-ES"]`); `[]` auto-detects |
| `custom_vocabulary` | Optional list of terms to bias recognition |
| `vad_disabled` | When true, disables automatic VAD (manual push-to-talk) |

For simultaneous mode, the setup sent after WebSocket open is structurally:

```json
{
  "setup": {
    "model": "models/gemini-3.5-live-translate-preview",
    "generationConfig": {
      "responseModalities": ["AUDIO"],
      "translationConfig": {
        "targetLanguageCode": "es",
        "echoTargetLanguage": false
      }
    },
    "inputAudioTranscription": {},
    "outputAudioTranscription": {}
  }
}
```

The client sends audio as:

```json
{
  "realtimeInput": {
    "audio": {
      "mimeType": "audio/pcm;rate=16000",
      "data": "<base64 little-endian Int16 PCM>"
    }
  }
}
```

For the fallback, setup uses the default Live model, `responseModalities`,
voice `Puck`, an interpreter `systemInstruction`,
`realtimeInputConfig.automaticActivityDetection`, and both transcription
configs. It sets `activityHandling` to `NO_INTERRUPTION`, high end-of-speech
sensitivity, 300 ms prefix padding, and the clamped silence duration.

## Live Transcribe (speech-to-text)

`translation_mode=transcribe` implements the [Gemini Live Transcribe API](https://ai.google.dev/gemini-api/docs/live-api/live-transcribe):
a dedicated speech-to-text pipeline that streams text transcriptions
(`response_modalities=["TEXT"]`) instead of spoken audio. It uses
`gemini-3.5-live-translate-preview` (override with `TRANSCRIPTION_MODEL`) and connects
over the transcribe live WebSocket (the `v1beta` generative-language endpoint,
override with `TRANSCRIBE_WS_VERSION`).

```json
{
  "setup": {
    "model": "models/gemini-3.5-live-translate-preview",
    "generationConfig": {
      "responseModalities": ["TEXT"]
    },
    "inputAudioTranscription": {
      "languageCodes": [],
      "customVocabulary": ["Gemini", "Kubernetes"],
      "mode": "smart"
    },
    "outputAudioTranscription": {}
  }
}
```

`inputAudioTranscription` carries the language hint (empty `languageCodes`
triggers automatic language detection), an optional `customVocabulary`, and a
`mode` of `verbatim` (default, raw transcript) or `smart` (cleaned, formatted).
With `vad_disabled=true` the server sends
`realtimeInputConfig.automaticActivityDetection.disabled=true` for manual
push-to-talk turn boundaries. The server emits `input_transcription` (finalized)
and `interim_input_transcription` (low-latency partial) text fields.

The backend creates tokens with `client.auth_tokens.create` using:

* `uses` (default 1),
* total expiration (default 30 minutes),
* new-session connection window (default 5 minutes), and
* `live_connect_constraints` when `LOCK_TOKEN_CONSTRAINTS=true`.

The returned WebSocket endpoint is the constrained
`BidiGenerateContentConstrained` endpoint with `?access_token=<token>`. A
single-use token cannot be reused after a failed or completed connection;
mint a new one. The API key remains server-side. The in-memory rate limiter
defaults to 10 token requests per IP per minute and is not a distributed
limiter, so production deployments should place a durable gateway limiter in
front of multiple replicas.

## Frontend audio pipeline

`AudioStreamer` requests mono microphone input with browser echo cancellation,
noise suppression, and AGC. It attempts an `AudioContext` at 16,000 Hz; if the
browser chooses another hardware rate, `resampleBuffer` performs linear
interpolation while preserving a fractional read index across worklet frames.
`capture.worklet.js` collects 2048 samples, transfers them to the main thread,
converts float samples to little-endian 16-bit PCM, base64 encodes them, and
passes them to `GeminiLiveClient.sendAudio`.

`AudioPlayer` uses a separate 24,000 Hz context. `playback.worklet.js` queues
decoded Float32 chunks, waits for roughly 1200 samples (about 50 ms) or three
chunks to reduce jitter, then emits mono/stereo output. An `interrupted` event
flushes the queue in turn-based mode. Volume is controlled by a gain node.

## Protocol parsing and state machine

`gemini-live-protocol.js` accepts JSON strings, `ArrayBuffer`/typed arrays,
and test `Buffer` values. It emits normalized events:

* `setup_complete` from `setupComplete`;
* `error` from `error`;
* `go_away` from `goAway`;
* `text` from `modelTurn.parts[].text` and `outputTranscription.text`;
* `audio` from `modelTurn.parts[].inlineData`;
* `source_text` from `inputAudioTranscription` or legacy `inputTranscription`;
* `interrupted` and `turn_complete` from `serverContent`.

`GeminiLiveClient` only sends audio after setup acknowledgement, rejects
connection setup after 10 seconds, handles Blob frames, warns near token
expiry, and closes the socket on stop. `app.js` starts token minting before
microphone capture, disables mutable controls while running, appends partial
text to the current transcript entry, and finalizes entries on a turn boundary
or stop. Simultaneous mode intentionally does not require `turnComplete` to
display content; the event is still parsed for compatibility.

Fallback behavior is explicit: invalid translation mode is rejected by the
request model; unknown language values normalize to English; missing optional
SDK/API-key configuration produces an HTTP 500; malformed WebSocket frames are
ignored by the parser; and the UI can select `turn_based` when the translation
model/configuration is unavailable. There is no automatic provider retry,
because a consumed ephemeral token must not be replayed.

## Directory and file structure

```text
backend/
  config.py             environment-backed Settings
  gemini_live.py        language/setup builders and TokenService
  main.py               FastAPI health/token/static endpoints
frontend/
  index.html             controls and split transcript UI
  js/app.js              UI lifecycle, settings, transcript/export logic
  js/gemini-live-client.js  direct WebSocket lifecycle
  js/gemini-live-protocol.js frame builders/parser
  js/audio-streamer.js   capture, resampling, PCM/base64 conversion
  js/audio-player.js     output queue and volume
  js/audio-processors/   capture and playback AudioWorklet processors
tests/
  test_backend.py, test_config.py, test_gemini_live.py
  js/protocol.test.js
scripts/
  smoke_gemini.py        token/handshake smoke check
  probe_live_translate.py provider probing utility
k8s/                     Deployment, Service, ConfigMap, Secret example
Dockerfile               Python 3.12 image and health check
docker-compose.yml       local container orchestration
```

## Deployment, operations, and verification

Configuration is documented in `.env.example`: `DEFAULT_MODEL`,
`TRANSLATE_MODEL`, `TRANSLATION_MODE`, `HOST`, `PORT`, token TTL/uses,
`LOCK_TOKEN_CONSTRAINTS`, `ALLOWED_ORIGINS`, and
`TOKEN_RATE_LIMIT_PER_MINUTE`. Kubernetes uses `k8s/configmap.yaml` for
non-secret values and `k8s/secret.example.yaml` for the key; the Deployment
has two replicas and `/api/health` liveness/readiness probes. Because token
rate history is process-local, use sticky or gateway-level controls for
production rate enforcement.

Run verification:

```bash
pytest tests/ -v
node --test tests/js/protocol.test.js
python scripts/smoke_gemini.py       # requires a valid key and network
```

The browser requires a secure origin for microphone access in production
(HTTPS, or localhost during development). Protect `/api/token` with suitable
origin policy, authentication, and ingress rate limiting before exposing it
publicly.
