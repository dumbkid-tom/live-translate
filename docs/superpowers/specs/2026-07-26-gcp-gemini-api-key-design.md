# Design Document: GCP Gemini API Key Support & Environment Variable Overrides

## Executive Summary
This design specifies the implementation details for supporting GCP API Keys with Gemini API permissions in the Live Translate web application. The application will default to GCP project `winter-runway-506` and region `us-central1`, support authentication via `GEMINI_API_KEY`, and load `.env` settings with `override=True` so file configuration takes precedence over pre-existing environment variables.

---

## 1. Requirements & Goals

1. **GCP Gemini API Key Support**:
   - Support API keys generated from Google Cloud Platform (GCP) with Gemini API / Vertex AI permissions.
   - Pass API key to Vertex AI WebSocket endpoint via URL parameter `?key={GEMINI_API_KEY}` and header `x-goog-api-key: {GEMINI_API_KEY}`.

2. **Project & Region Defaults**:
   - GCP Project ID default: `winter-runway-506`
   - GCP Region default: `us-central1`

3. **Environment Variable Configuration**:
   - Primary API key variable: `GEMINI_API_KEY`
   - Fallback/Legacy token variable: `VERTEX_ACCESS_TOKEN`

4. **Dotenv Override**:
   - Automatically load `.env` file upon backend initialization.
   - Must use `override=True` so values in `.env` overwrite any pre-existing environment variables in the execution environment.

5. **Backward Compatibility**:
   - Support OAuth 2.0 Bearer tokens (`ya29...`) and GCP Application Default Credentials (ADC) when `GEMINI_API_KEY` is not present.

---

## 2. Architecture & Components

```
┌─────────────────────────────────────────────────────────┐
│                      Client Browser                     │
└────────────────────────────┬────────────────────────────┘
                             │ WebSocket /ws/translate
                             ▼
┌─────────────────────────────────────────────────────────┐
│                 FastAPI Proxy Backend                   │
│  - Loads .env (override=True)                           │
│  - Resolves Auth: GEMINI_API_KEY > OAuth Token > ADC   │
│  - Defaults: Project=winter-runway-506, Region=us-central1│
└────────────────────────────┬────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            │ API Key Auth                    │ OAuth 2.0 / ADC
            ▼                                 ▼
┌───────────────────────┐         ┌───────────────────────┐
│ Vertex AI WSS Endpoint│         │ Vertex AI WSS Endpoint│
│ ?key={GEMINI_API_KEY} │         │ ?access_token={token} │
│ x-goog-api-key Header │         │ Bearer Header         │
└───────────────────────┘         └───────────────────────┘
```

### Component Breakdown

1. **`backend/config.py` (`Settings` class)**:
   - Call `load_dotenv(dotenv_path, override=True)` on startup.
   - Properties:
     - `vertex_project`: `os.getenv("VERTEX_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "winter-runway-506"))`
     - `vertex_location`: `os.getenv("VERTEX_LOCATION", "us-central1")`
     - `gemini_api_key`: `os.getenv("GEMINI_API_KEY", os.getenv("VERTEX_API_KEY", ""))`
     - `access_token`: `os.getenv("VERTEX_ACCESS_TOKEN", "")`

2. **`backend/gemini_live.py` (`GeminiLiveBridge` class)**:
   - Add `api_key` attribute and update `_resolve_auth()` logic:
     - **Priority 1**: Explicit `api_key` or `GEMINI_API_KEY` (format: starts with `AIza` or specified as API key).
     - **Priority 2**: Explicit `access_token` or `VERTEX_ACCESS_TOKEN` (starts with `ya29.`).
     - **Priority 3**: GCP ADC (`google.auth.default()`).
   - `get_connection_details()` returns:
     - For API Key:
       - `ws_url`: `wss://{location}-aiplatform.googleapis.com/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent?key={api_key}`
       - `headers`: `{"x-goog-api-key": api_key}`
       - `model_name`: `projects/{project}/locations/{location}/publishers/google/models/{model}`
     - For OAuth/ADC:
       - `ws_url`: `wss://{location}-aiplatform.googleapis.com/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent?access_token={token}`
       - `headers`: `{"Authorization": f"Bearer {token}"}`

3. **`backend/main.py`**:
   - Update `/api/health` status response to detail auth mechanism (`api_key`, `oauth_token`, `adc`, `none`).
   - Support `api_key` parameter in `/ws/translate` query parameters.

---

## 3. Testing Strategy

- Unit tests in `tests/test_config.py`:
  - Verify `.env` file loading with `override=True`.
  - Verify defaults for `vertex_project` (`winter-runway-506`) and `vertex_location` (`us-central1`).
- Unit tests in `tests/test_backend.py`:
  - Test `GeminiLiveBridge` with GCP API key (`AIzaSy...`), verifying `?key=` query param and `x-goog-api-key` header.
  - Test `GeminiLiveBridge` with OAuth token (`ya29...`), verifying `?access_token=` query param and `Authorization` header.
  - Test `/api/health` response formatting.
