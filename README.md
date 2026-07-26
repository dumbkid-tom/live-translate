# 🌐 Vertex AI Live Translate Web Application

A low-latency, real-time speech and text translation web application powered by **GCP Vertex AI Gemini Live API** (`aiplatform.googleapis.com`) with GCP Project `winter-runway-506` and region `us-central1`.

---

## ✨ Key Features

- **GCP Vertex AI Gemini Integration**: Uses `aiplatform.googleapis.com` with support for GCP API Key (`GEMINI_API_KEY`), OAuth 2.0 Bearer tokens, and GCP Application Default Credentials (ADC).
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
[ FastAPI Proxy Server (GCP Auth Resolution) ] 
       │ 
       ▼ (Stateful WSS BidiGenerateContent)
[ GCP Vertex AI (wss://us-central1-aiplatform.googleapis.com) ]
```

---

## 🔑 Authentication Options for Vertex AI

The application automatically manages authentication in three ways (checked in priority order):

1. **GCP API Key (`GEMINI_API_KEY`)**:
   Provide a GCP API Key with Vertex AI / Gemini API permissions.
2. **OAuth 2.0 Access Token (`VERTEX_ACCESS_TOKEN`)**:
   OAuth token from `gcloud auth print-access-token`.
3. **Application Default Credentials (ADC) / Service Account Key**:
   When `GOOGLE_APPLICATION_CREDENTIALS` is set or local ADC (`gcloud auth application-default login`) is used.

Default Project: `winter-runway-506`  
Default Location: `us-central1`

---

## 🚀 Quickstart (Docker Compose)

### 1. Configure `.env`
```env
VERTEX_PROJECT=winter-runway-506
VERTEX_LOCATION=us-central1
GEMINI_API_KEY=your-gcp-api-key-here
```

### 2. Start Application
```bash
docker compose up -d --build
```
Access the application at `http://localhost:8000`.

---

## ☸️ Deploying to Kubernetes

Apply manifests:
```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

---

## 🧪 Running Tests

```bash
./venv/bin/pytest tests/ -v
```

---

## 📄 License
MIT
