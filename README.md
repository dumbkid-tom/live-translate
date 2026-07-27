# 🌐 Gemini Live Translate Web Application

A low-latency, real-time speech and text translation web application powered by **Google Gemini Live API** (`generativelanguage.googleapis.com`).

---

## ✨ Key Features

- **Gemini Live API Integration**: Direct WebSocket streaming connection to `generativelanguage.googleapis.com` via `GEMINI_API_KEY`.
- **Real-Time Speech-to-Speech & Speech-to-Text**: Stream microphone audio continuously with instant translated spoken audio and live transcript text.
- **Dual Output Modes**:
  - 🔊 **Live Audio + Text**: Hear real-time target language audio output while following along with live translated text.
  - 📝 **Live Text Only**: Silent translation streaming live translated text.
- **Multilingual Support**: Supports 15+ major global target languages (English, Chinese, Spanish, French, German, Japanese, Korean, Italian, Portuguese, Hindi, etc.).
- **Start / Stop Operation**: Simple toggle button to start microphone capture and safely close streaming sessions.
- **Transcript Export**: Save and download complete translation histories as `.json` or `.md` files at any time.
- **Containerized**: Includes `Dockerfile`, `docker-compose.yml`, and Kubernetes deployment manifests (`k8s/`).

---

## 🏗️ Architecture

```
[ Web Browser ] (Microphone 16kHz PCM) 
       │ 
       ▼ (WebSocket /ws/translate)
[ FastAPI Proxy Server ] 
       │ 
       ▼ (Stateful WSS BidiGenerateContent)
[ Google Gemini API (wss://generativelanguage.googleapis.com) ]
```

---

## 🔑 Authentication & Configuration

The application requires only a single environment variable:

- **`GEMINI_API_KEY`**: Your Google Gemini API key.

Default Model: `gemini-2.0-flash-exp`

---

## 🚀 Quickstart

### 1. Configure `.env`
Create or edit `.env`:
```env
GEMINI_API_KEY=your-gemini-api-key-here
DEFAULT_MODEL=gemini-2.0-flash-exp
```

### 2. Start Application via Docker Compose
```bash
docker compose up -d --build
```
Access the application at `http://localhost:8000`.

### 3. Or Run Locally with Python
```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

---

## ☸️ Deploying to Kubernetes

1. Create secret from example:
```bash
cp k8s/secret.example.yaml k8s/secret.yaml
# Edit k8s/secret.yaml to add your GEMINI_API_KEY
kubectl apply -f k8s/secret.yaml
```

2. Apply manifests:
```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

---

## 🧪 Testing & Verification

Run backend unit and route tests:
```bash
./venv/bin/pytest tests/ -v
```

Run live Gemini WebSocket handshake smoke test:
```bash
python scripts/smoke_gemini.py
```

---

## 📄 License
MIT
