# User Manual

## Overview

The application solves the latency and interaction problems of a conventional
“record one utterance, upload it, wait, translate it” pipeline. Audio is sent
as it is spoken, and Gemini can emit partial target-language text and PCM
audio before the source speaker has finished. The UI shows the original
speech and translation in two live transcript columns and can optionally play
the translated voice.

The backend never proxies microphone audio. It keeps `GEMINI_API_KEY` private,
creates a constrained ephemeral token, and returns the WebSocket setup needed
by the browser.

## Start locally

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

## Interaction model

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

## Capabilities and configuration controls

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

## Outputs and expected results

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
