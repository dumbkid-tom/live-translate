# Regeneration Prompt

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
