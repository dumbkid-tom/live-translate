# Live Translate Web Application Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete, containerized Live Translate web application powered by the Gemini Multimodal Live API (`gemini-3.5-live-translate-preview`) with real-time speech/text translation, dual output modes (Audio-to-Audio and Audio-to-Text), real-time transcripts, export capability, Docker Compose support, and Kubernetes manifests.

**Architecture:** A FastAPI backend acts as a low-latency stateful WebSocket proxy between browser audio clients and the Gemini Multimodal Live API (`wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent`). The browser captures mic audio via Web Audio API, resamples to 16kHz 16-bit PCM, and streams to FastAPI, which forwards to Gemini. Gemini returns translated text/audio frames, which FastAPI streams back to the browser for real-time visual UI rendering and audio playback.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, WebSockets, `google-genai` / `websockets`, HTML5 Web Audio API, CSS3 Glassmorphism, Docker, Docker Compose, Kubernetes.

## Global Constraints

- Python version floor: Python 3.12
- Gemini Live Model ID: `gemini-3.5-live-translate-preview` (with fallback support for `gemini-2.0-flash-exp`)
- Gemini API Key passed via environment variable `GEMINI_API_KEY`
- Audio format: 16kHz, 16-bit mono PCM stream
- No authentication required

---

### Task 1: Backend Foundation & Configuration

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/config.py`
- Create: `backend/requirements.txt`
- Create: `backend/main.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: Environment variables (`GEMINI_API_KEY`, `DEFAULT_MODEL`, `PORT`, `HOST`)
- Produces: `config.Settings` instance and base FastAPI app instance serving static files and API health check.

- [ ] **Step 1: Write backend requirements and config module**

Create `backend/requirements.txt`:
```txt
fastapi>=0.110.0
uvicorn>=0.28.0
websockets>=12.0
python-dotenv>=1.0.0
google-genai>=0.1.1
pydantic>=2.6.0
pytest>=8.0.0
httpx>=0.27.0
```

Create `backend/config.py`:
```python
import os
from pydantic import BaseModel

class Settings(BaseModel):
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    default_model: str = os.getenv("DEFAULT_MODEL", "gemini-3.5-live-translate-preview")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    ws_endpoint: str = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"

settings = Settings()
```

- [ ] **Step 2: Create failing test for config and health endpoint**

Create `tests/test_config.py`:
```python
import sys
import os
sys.path.insert(0, os.path.abspath("."))

from backend.config import settings

def test_settings_default():
    assert settings.default_model == "gemini-3.5-live-translate-preview"
    assert settings.port == 8000
```

- [ ] **Step 3: Run test to verify config**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 4: Create base FastAPI application in `backend/main.py`**

```python
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from backend.config import settings

app = FastAPI(title="Live Translate API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "model": settings.default_model,
        "has_api_key": bool(settings.gemini_api_key)
    }

# Static file mounting for frontend
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def read_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return JSONResponse(content={"message": "Live Translate API is running. Frontend static directory ready."})
```

---

### Task 2: Gemini Multimodal Live API WebSocket Handler & Proxy Client

**Files:**
- Create: `backend/gemini_live.py`
- Modify: `backend/main.py`
- Test: `tests/test_websocket.py`

**Interfaces:**
- Consumes: Browser WebSocket connection (`/ws/translate?target_language=es&mode=audio`) streaming audio PCM base64/bytes.
- Produces: Bi-directional proxy communication with Gemini Live WSS API, forwarding transcribed text and PCM audio back to frontend.

- [ ] **Step 1: Write `backend/gemini_live.py` WebSocket proxy logic**

```python
import json
import asyncio
import logging
import websockets
from backend.config import settings

logger = logging.getLogger("gemini_live")
logging.basicConfig(level=logging.INFO)

class GeminiLiveBridge:
    def __init__(self, target_language: str = "English", output_mode: str = "audio", api_key: str = None):
        self.target_language = target_language
        self.output_mode = output_mode # 'audio' or 'text'
        self.api_key = api_key or settings.gemini_api_key
        self.model = settings.default_model
        self.ws_url = f"{settings.ws_endpoint}?key={self.api_key}"

    def build_initial_setup_message(self):
        modalities = ["AUDIO", "TEXT"] if self.output_mode == "audio" else ["TEXT"]
        prompt = (
            f"You are a real-time live translator. Translate all input speech directly into {self.target_language}. "
            f"Provide continuous, low-latency translation. Keep tone natural and preserve intonation where possible."
        )
        setup_msg = {
            "setup": {
                "model": f"models/{self.model}",
                "generationConfig": {
                    "responseModalities": modalities,
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": "Puck"
                            }
                        }
                    }
                },
                "systemInstruction": {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            }
        }
        return setup_msg

    def build_realtime_audio_chunk(self, pcm_b64: str):
        return {
            "realtimeInput": {
                "mediaChunks": [
                    {
                        "mimeType": "audio/pcm;rate=16000",
                        "data": pcm_b64
                    }
                ]
            }
        }
```

- [ ] **Step 2: Add WebSocket endpoint to `backend/main.py`**

```python
from fastapi import WebSocket, WebSocketDisconnect
from backend.gemini_live import GeminiLiveBridge
import websockets
import json
import asyncio

@app.websocket("/ws/translate")
async def websocket_translate(websocket: WebSocket, target_language: str = "English", mode: str = "audio"):
    await websocket.accept()
    bridge = GeminiLiveBridge(target_language=target_language, output_mode=mode)
    
    if not bridge.api_key:
        await websocket.send_json({"type": "error", "message": "GEMINI_API_KEY environment variable is not set."})
        await websocket.close(code=1008)
        return

    try:
        async with websockets.connect(bridge.ws_url) as gemini_ws:
            # Send setup frame
            setup_payload = bridge.build_initial_setup_message()
            await gemini_ws.send(json.dumps(setup_payload))
            
            # Send ready status to client
            await websocket.send_json({"type": "connected", "target_language": target_language, "mode": mode})

            async def client_to_gemini():
                try:
                    while True:
                        data = await websocket.receive_text()
                        msg = json.loads(data)
                        if msg.get("type") == "audio_chunk" and "data" in msg:
                            audio_frame = bridge.build_realtime_audio_chunk(msg["data"])
                            await gemini_ws.send(json.dumps(audio_frame))
                        elif msg.get("type") == "stop":
                            break
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.error(f"Error client_to_gemini: {e}")

            async def gemini_to_client():
                try:
                    async for raw_response in gemini_ws:
                        resp = json.loads(raw_response)
                        server_content = resp.get("serverContent", {})
                        model_turn = server_content.get("modelTurn", {})
                        parts = model_turn.get("parts", [])
                        
                        for part in parts:
                            if "text" in part:
                                await websocket.send_json({
                                    "type": "text",
                                    "text": part["text"]
                                })
                            if "inlineData" in part and part["inlineData"].get("mimeType", "").startswith("audio/"):
                                await websocket.send_json({
                                    "type": "audio",
                                    "data": part["inlineData"]["data"],
                                    "mimeType": part["inlineData"]["mimeType"]
                                })
                except Exception as e:
                    logger.error(f"Error gemini_to_client: {e}")

            await asyncio.gather(client_to_gemini(), gemini_to_client(), return_exceptions=True)

    except Exception as e:
        await websocket.send_json({"type": "error", "message": f"Gemini WSS Connection failed: {str(e)}"})
        await websocket.close()
```

---

### Task 3: Modern Responsive Web Frontend

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/css/style.css`
- Create: `frontend/js/audio-recorder.js`
- Create: `frontend/js/audio-player.js`
- Create: `frontend/js/app.js`

**Interfaces:**
- Consumes: Web Audio API mic stream, server `/ws/translate` WebSocket.
- Produces: Real-time visual transcript stream, canvas audio equalizer, PCM audio playback, and `.json`/`.md` file download exports.

- [ ] **Step 1: Build `frontend/index.html` with clean responsive structure & SEO metadata**
- [ ] **Step 2: Build `frontend/css/style.css` with dark mode, glassmorphism, animations, and micro-interactions**
- [ ] **Step 3: Build `frontend/js/audio-recorder.js` for Web Audio API audio capture & 16kHz PCM encoding**
- [ ] **Step 4: Build `frontend/js/audio-player.js` for seamless PCM chunk queuing & playback**
- [ ] **Step 5: Build `frontend/js/app.js` for state management, UI events, transcript streaming, and file download export**

---

### Task 4: Unit & Integration Tests

**Files:**
- Create: `tests/test_backend.py`

**Interfaces:**
- Consumes: FastAPI test client & mock WebSocket connection.
- Produces: Test coverage report verifying API route health, bridge setup, and frame formatters.

- [ ] **Step 1: Write unit tests in `tests/test_backend.py`**
- [ ] **Step 2: Run pytest to ensure all tests pass**

---

### Task 5: Containerization & Orchestration Setup

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `docker-compose.yml`
- Create: `k8s/deployment.yaml`
- Create: `k8s/service.yaml`
- Create: `k8s/configmap.yaml`
- Create: `.env.example`

- [ ] **Step 1: Create `Dockerfile` with multi-stage Python 3.12 image**
- [ ] **Step 2: Create `docker-compose.yml`**
- [ ] **Step 3: Create Kubernetes deployment & service manifests**
- [ ] **Step 4: Build Docker image and test startup using Docker**

---

### Task 6: Documentation & End-to-End Verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md` with complete documentation for running locally, Docker Compose, Kubernetes, and API usage**
- [ ] **Step 2: Run complete verification checks**
