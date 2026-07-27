# Technical Specification: Gemini Live Ephemeral-Token Full-Duplex Architecture

**Date:** July 26, 2026  
**Status:** Approved & Implemented  
**Target Application:** `live-translate`

---

## 1. Executive Summary

`live-translate` has been upgraded from a server-proxied WebSocket translation model to a direct client-to-Gemini full-duplex architecture using Gemini Live Ephemeral Tokens (`BidiGenerateContentConstrained`).

The backend FastAPI service acts purely as a secure token minter (`POST /api/token`). Browsers receive an ephemeral token and connect directly via WebSocket to Google's Gemini Live API endpoint. Audio streaming uses AudioWorklet nodes (16kHz PCM capture and 24kHz PCM playback). The default simultaneous path uses the translation-specific model and structured `translationConfig.targetLanguageCode`; the legacy path retains VAD and an interpreter prompt for deployments where simultaneous translation is unavailable.

---

## 2. Architecture & Protocol Flow

### 2.1 Protocol Sequence Diagram

```
[ Web Browser ]              [ FastAPI Backend ]             [ Gemini Live API WSS ]
       │                              │                                 │
       │─── 1. POST /api/token ──────►│                                 │
       │    { target_lang, mode }     │─── auth_tokens.create() ───────►│
       │                              │◄── token: auth_tokens/xxx ──────┤
       │◄── 2. { token, ws_endpoint }─│                                 │
       │                                                                │
       │─── 3. wss://generativelanguage.googleapis.com/ws/... ─────────►│
       │       ?access_token=auth_tokens/xxx                            │
       │                                                                │
       │─── 4. send setup frame ───────────────────────────────────────►│
       │◄── 5. receive setupComplete ───────────────────────────────────┤
       │                                                                │
       │─── 6. stream 16kHz PCM audio (AudioWorklet) ──────────────────►│
       │◄── 7. stream 24kHz PCM audio & transcript text ────────────────┤
```

---

## 3. Security & Ephemeral Token Policy

Ephemeral tokens are created using `google-genai` SDK `client.auth_tokens.create`:

1. **Short Lifespan**: Total TTL of 30 minutes (`TOKEN_TTL_MINUTES`), session connection window of 5 minutes (`TOKEN_NEW_SESSION_TTL_MINUTES`).
2. **Usage Limit**: `uses = 1` enforces single-use connections per token.
3. **Constraint Lock**: `live_connect_constraints` locks the model (`gemini-3.1-flash-live-preview`), system instructions, and response modalities (`AUDIO`).
4. **Rate Limiting**: Backend limits client IP token generation to 10 requests/minute (`TOKEN_RATE_LIMIT_PER_MINUTE`). This limiter is process-local and should be supplemented by an ingress/gateway limiter when running multiple replicas.

---

## 4. Frontend Audio Pipeline

### 4.1 Audio Worklets

- **Capture Worklet (`capture.worklet.js`)**: Runs on `AudioContext` input thread, buffers 2048-sample frames, downsamples to 16,000 Hz, converts to 16-bit Int16 PCM, and posts base64 encoded audio frames.
- **Playback Worklet (`playback.worklet.js`)**: Manages 24,000 Hz PCM output queue with an approximately 50 ms startup threshold to reduce jitter. Supports instant queue flushing on `interrupted` signal.

### 4.2 Split Dual Transcript

- **Original Speech**: Renders source audio transcript chunks (`inputAudioTranscription`).
- **Live Translation**: Renders target language translation text (`modelTurn` text & `outputTranscription`).

---

## 5. Verification & Test Suite

1. **Backend Unit Tests**: `./venv/bin/pytest tests/ -v` (18 passed at implementation time)
2. **JS Protocol Unit Tests**: `node --test tests/js/protocol.test.js` (11 passed at implementation time)
3. **Live Gemini Handshake**: `python scripts/smoke_gemini.py` (Passed)
