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

## Quick start

1. Copy `.env.example` to `.env` and set `GEMINI_API_KEY` (or `GOOGLE_API_KEY`).
   Do not commit the resulting `.env`.
2. Start the server:

   ```bash
   python -m venv venv
   . venv/bin/activate
   pip install -r backend/requirements.txt
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

3. Open <http://localhost:8000>, grant microphone permission, choose the
   engine/languages/output mode, and press **Start Translation**. Use
   headphones for full-duplex audio to prevent speaker bleed and feedback.

Docker Compose runs the same stack:

```bash
docker compose up --build
```

Open <http://localhost:8000> after the container is healthy.

---

## Features

* **Continuous full-duplex translation** — audio is streamed as it is spoken,
  so partial target-language text and audio arrive before a source turn ends.
* **Two engines** — `Simultaneous (live-translate)` for live interpretation,
  and `Turn-based (legacy)` as a fallback for models that lack
  `translationConfig`.
* **Flexible languages** — target and optional source in names, two-letter
  codes, or BCP-47 values (`en-US`, `pt-BR`). Unknown values fall back to `en`.
* **Output modes** — `Live Audio + Text` plays 24 kHz PCM while showing text,
  or `Live Text Only` for transcript-only use.
* **Audio controls** — input device, playback volume, `Echo Target Language`,
  and browser echo cancellation, noise suppression, and AGC.
* **Transcript actions** — clear, export JSON history, or export Markdown.
* **Live Transcribe** — a speech-to-text pipeline (`translation_mode=transcribe`)
  for text-only transcription.

---

## Documentation

The full details have been moved into the `docs/` directory:

| Document | Purpose |
|---|---|
| [`docs/user-manual.md`](docs/user-manual.md) | Overview, start locally, interaction model, capabilities, and expected results |
| [`docs/technical-specs.md`](docs/technical-specs.md) | Architecture, token/setup protocol, audio pipeline, protocol parsing, file layout, deployment, and verification |
| [`docs/regeneration-prompt.md`](docs/regeneration-prompt.md) | Prompt to recreate the repository from scratch |

## Verification

```bash
pytest tests/ -v
node --test tests/js/protocol.test.js
python scripts/smoke_gemini.py       # requires a valid key and network
```
