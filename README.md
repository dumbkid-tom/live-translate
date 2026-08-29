# Gemini Live Translate

Low-latency, continuous full-duplex speech translation in the browser. The
browser captures microphone audio, requests a short-lived Gemini Live
ephemeral token from the FastAPI service, then streams audio directly to
Gemini over WebSocket. Translated audio and text return on the same socket.

This repository contains the completed simultaneous-translation path and a
turn-based compatibility path. **Simultaneous** is the default and should be
used for continuous interpretation; **turn-based** remains available when a
model or deployment does not support `translationConfig`.

---

## 1. User Manual

### Overview

The application solves the latency and interaction problems of a conventional
“record one utterance, upload it, wait, translate it” pipeline. Audio is sent
as it is spoken, and Gemini can emit partial target-language text and PCM
audio before the source speaker has finished. The UI shows the original
speech and translation in two live transcript columns and can optionally play
the translated voice.

The backend never proxies microphone audio. It keeps `GEMINI_API_KEY` private,
creates a constrained ephemeral token, and returns the WebSocket setup needed
by the browser.

### Start locally

1. Copy `.env.example` to `.env` and set `GEMINI_API_KEY` (or
   `GOOGLE_API_KEY`). Do not commit the resulting `.env`.
2. Install Python dependencies and start the server:

   ```bash
   python -m venv venv
   . venv/bin/activate
   pip install -r backend/requirements.txt
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

3. Open <http://localhost:8000>, grant microphone permission, choose the
   engine/languages/output mode, and press **Start Translation**. Use
   headphones for full-duplex audio to prevent speaker bleed and feedback.

Docker Compose provides the same server:

```bash
docker compose up --build
```

Open <http://localhost:8000> after the container is healthy. Compose passes
the API key and default model from the shell or `.env`; other settings can be
added to the `environment` section when needed.

### Interaction model

The browser performs these steps on every start:

1. `POST /api/token` with the selected language and engine settings.
2. Receives an ephemeral token, direct Gemini WebSocket URL, and setup frame.
3. Opens the returned `wss://generativelanguage.googleapis.com/...` socket.
4. Sends the setup frame and waits for `{"setupComplete":{}}`.
5. Starts the microphone worklet and sends continuous base64 PCM frames.
6. Parses server frames into source transcript, translation text, audio,
   interruption, and turn-complete events.

Useful HTTP calls:

```bash
curl http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/token \
  -H 'Content-Type: application/json' \
  -d '{
    "target_language": "es",
    "source_language": "en",
    "mode": "audio",
    "translation_mode": "simultaneous",
    "echo_target_language": false
  }'
```

The token response is intended for immediate browser use and should not be
stored or logged. Tokens are single-use by default.

### Capabilities and configuration controls

* **Translation engine**
  * `Simultaneous (live-translate)`: uses the translation model and
    `generationConfig.translationConfig`; output can begin every few seconds
    without waiting for a VAD end-of-turn.
  * `Turn-based (legacy)`: uses the general Live model, an interpreter system
    prompt, and automatic activity detection. The silence slider controls when
    a turn is considered complete.
* **Languages**: choose a target language and optionally a source language.
  The backend accepts names, two-letter codes, and BCP-47-like values such as
  `en-US` or `pt-BR`. Unknown values safely fall back to `en`.
* **Output**: `Live Audio + Text` plays 24 kHz PCM while displaying text, or
  `Live Text Only` suppresses playback while retaining transcript output.
* **Audio hardware**: choose an input device, adjust playback volume, and
  enable `Echo Target Language` for simultaneous mode if the target should be
  repeated. Browser echo cancellation, noise suppression, and automatic gain
  control are enabled for capture.
* **Transcript actions**: clear the current view, export a JSON history, or
  export Markdown. Entries contain timestamp, target language, original text,
  and translation text.

Representative API request:

```json
{
  "target_language": "fr-FR",
  "source_language": "en-US",
  "mode": "text",
  "translation_mode": "simultaneous",
  "silence_duration_ms": 600,
  "echo_target_language": false
}
```

`silence_duration_ms` is meaningful for the turn-based fallback and is
clamped to 500–2000 ms in that path. The request schema accepts 100–2000 ms.

### Outputs and expected results

* `/api/health` returns service status, provider, endpoint, configured default
  model, API-key presence, and token policy metadata.
* `/api/token` returns `token`, `expires_at`, `model`, `ws_endpoint`, `setup`,
  `translation_mode`, and normalized `target_language_code`.
* The WebSocket returns setup acknowledgement, incremental transcript text,
  inline base64 PCM audio (`audio/pcm;rate=24000`), source transcription,
  interruption notifications, and optional `turnComplete` events.
* The UI changes from `Ready` to `Minting token…`, `Connecting Gemini WS…`,
  and `Live Translate` (or `Turn-based Translate`). A token warning is raised
  two minutes before expiry.
* A failed token request, missing API key/SDK, denied microphone permission,
  setup timeout, invalid setup, or socket close appears as a connection error.

---

## 2. Technical Specification

### Root cause: turn-based versus simultaneous translation

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

### Components and data flow

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

### Token and setup protocol

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

### Live Transcribe (speech-to-text)

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

### Frontend audio pipeline

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

### Protocol parsing and state machine

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

### Directory and file structure

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

### Deployment, operations, and verification

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

---

## 3. Regeneration Prompt

Use the following prompt to recreate the repository from scratch:

```text
You are rebuilding a repository named live-translate. Create a production-grade
single-page web application for continuous/simultaneous live speech translation
using Google's Gemini Live API and short-lived ephemeral auth tokens.

IDENTITY AND BEHAVIOR
The product is Gemini Live Translate. It must support continuous full-duplex
translation: microphone audio is streamed while the speaker talks, and partial
target-language text/audio may arrive before a source turn ends. The default
engine is simultaneous translation. Also implement a clearly labeled
turn_based compatibility engine because some deployments/models do not support
the translation-specific live configuration. Do not pretend that reducing VAD
silence makes a turn-based model simultaneous.

ARCHITECTURE
Use Python 3.12, FastAPI, Pydantic 2, python-dotenv, uvicorn, pytest, and the
google-genai SDK. The backend must never proxy audio. It owns GOOGLE_API_KEY or
GEMINI_API_KEY, calls client.auth_tokens.create with the v1alpha API, and
returns an ephemeral token plus the direct constrained Gemini WebSocket URL.
The browser opens that URL with ?access_token=<token>, sends setup, waits for
setupComplete, and then streams audio directly to Gemini.

Create this structure:
  backend/config.py: load .env; defaults DEFAULT_MODEL=gemini-3.1-flash-live-preview,
    TRANSLATE_MODEL=gemini-3.5-live-translate-preview,
    TRANSLATION_MODE=simultaneous, HOST=0.0.0.0, PORT=8000; token uses=1,
    TTL=30 minutes, new-session TTL=5 minutes, locked constraints=true,
    origins=*, rate limit=10/IP/minute. Accept GOOGLE_API_KEY then GEMINI_API_KEY.
  backend/gemini_live.py: language resolver accepting names, ISO-like primary
    codes, and BCP-47 values; simultaneous setup builder; turn-based setup
    builder; interpreter prompt; TokenService.
  backend/main.py: GET /api/health, POST /api/token, CORS, static /static,
    root index, Pydantic request validation, and in-memory IP token rate limit.
  frontend/index.html and css/style.css: settings for engine, target/source
    language, audio/text output, microphone, volume, echo target, and fallback
    VAD silence; start/stop action; visualizer; split source/translation
    transcript; clear and JSON/Markdown export.
  frontend/js/gemini-live-protocol.js: parse JSON/string/ArrayBuffer/Blob-derived
    frames and normalize setup_complete, error, go_away, text, audio,
    source_text, interrupted, and turn_complete. Build realtimeInput audio
    frames with mimeType audio/pcm;rate=16000 and client text frames.
  frontend/js/gemini-live-client.js: direct WebSocket lifecycle, setup timeout,
    only send after setupComplete, Blob handling, expiration warning, close/error.
  frontend/js/audio-streamer.js: getUserMedia mono with echoCancellation,
    noiseSuppression, autoGainControl; AudioContext target 16 kHz with fallback;
    AudioWorklet capture; resample other rates using linear interpolation and a
    fractional index; encode little-endian Int16 PCM base64.
  frontend/js/audio-player.js: 24 kHz AudioContext, playback worklet, ordered
    decoded Int16-to-Float32 queue, volume gain, clear/stop.
  frontend/js/audio-processors/capture.worklet.js: collect 2048 samples and
    transfer Float32 chunks. playback.worklet.js: queue chunks, start after
    about 1200 samples/three chunks, output silence when empty, clear instantly.
  tests/test_config.py, test_backend.py, test_gemini_live.py, and
    tests/js/protocol.test.js covering setup shapes, language normalization,
    token mocks, API validation, and all parser event types.
  Dockerfile, docker-compose.yml, .env.example, k8s/{deployment,service,configmap,
    secret.example}.yaml, scripts/smoke_gemini.py and probe_live_translate.py.

SIMULTANEOUS SETUP
For translation_mode=simultaneous use the translate model and send:
{
  "setup": {
    "model": "models/gemini-3.5-live-translate-preview",
    "generationConfig": {
      "responseModalities": ["AUDIO"],
      "translationConfig": {"targetLanguageCode": "es",
                             "echoTargetLanguage": false}
    },
    "inputAudioTranscription": {}, "outputAudioTranscription": {}
  }
}
Use the SDK LiveConnectConfig equivalent with TranslationConfig. Return the
same setup wrapper to the browser. Use BidiGenerateContentConstrained and lock
model/config using live_connect_constraints when configured.

TURN-BASED FALLBACK
Use the default model, AUDIO response modality, Puck voice, an interpreter
system instruction that asks for short translations, input/output transcription,
NO_INTERRUPTION activity handling, high end-of-speech sensitivity, 300 ms
prefix padding, and silenceDurationMs clamped to 500..2000. Keep the UI VAD
slider visible only for this engine. On interrupted, clear playback; on
turnComplete, finalize the current transcript entry.

PROTOCOL AND AUDIO CONTRACT
After setupComplete send repeated:
{"realtimeInput":{"audio":{"mimeType":"audio/pcm;rate=16000",
"data":"<base64 little-endian mono Int16>"}}}
Parse serverContent.modelTurn.parts text and inlineData (default output
audio/pcm;rate=24000), outputTranscription, inputAudioTranscription (also accept
inputTranscription), interrupted, and turnComplete. Simultaneous output must be
rendered incrementally and must not wait for turnComplete. Warn two minutes
before token expiry. Tokens are single-use and must not be blindly retried.

SECURITY AND OPERATIONS
Never expose the provider API key to JavaScript. Default token policy is one
use, 30-minute expiry, 5-minute connection window, locked constraints, and 10
requests/IP/minute. Explain that the in-memory limiter is insufficient alone
for multi-replica production. Add health probes, CORS configuration, Docker
healthcheck, Kubernetes resources, and HTTPS/microphone guidance.

DOCUMENTATION AND ACCEPTANCE
Write a comprehensive README with exactly three major sections: User Manual,
Technical Specification, and Regeneration Prompt. Document the root cause of
turn-based behavior, translationConfig and BCP-47 handling, ephemeral-token
constraints, WebSocket setup/frame structure, 16 kHz capture/24 kHz playback,
worklets, parser events, fallbacks, environment variables, local/Docker/K8s
operation, and tests. Verify with pytest, node --test tests/js/protocol.test.js,
and an optional live handshake smoke test.
```
