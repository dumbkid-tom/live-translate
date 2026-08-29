# GCP Gemini API Key Support & Environment Variable Overrides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable GCP API key authentication (`GEMINI_API_KEY`) for Vertex AI Gemini API with project `winter-runway-506` and region `us-central1`, while ensuring `.env` files are loaded with `override=True` to overwrite existing environment variables.

**Architecture:** Update `backend/config.py` to reload `.env` using `override=True` and configure defaults (`GEMINI_API_KEY`, `winter-runway-506`, `us-central1`). Update `backend/gemini_live.py` to route API keys to Vertex AI WebSocket endpoints with `?key=` query parameters and `x-goog-api-key` headers while preserving OAuth 2.0 and ADC support. Update `backend/main.py` health endpoint and WS endpoint query params.

**Tech Stack:** Python 3.10+, FastAPI, `python-dotenv`, `google-auth`, `pytest`, `websockets`.

## Global Constraints

- GCP Project ID default: `winter-runway-506`
- GCP Region default: `us-central1`
- Environment variable name for API key: `GEMINI_API_KEY`
- `.env` loader setting: `dotenv.load_dotenv(..., override=True)`

---

### Task 1: Environment Configuration & Dotenv Override in `backend/config.py`

**Files:**
- Modify: `backend/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: Environment variables and `.env` file
- Produces: `settings.gemini_api_key`, `settings.vertex_project`, `settings.vertex_location`, `settings.reload()`

- [ ] **Step 1: Write failing unit tests for config defaults and .env override**

Create/update `tests/test_config.py`:

```python
import sys
import os
import tempfile
from pathlib import Path
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import Settings, settings

def test_settings_gcp_defaults():
    assert settings.vertex_project == "winter-runway-506"
    assert settings.vertex_location == "us-central1"

def test_settings_dotenv_override(tmp_path, monkeypatch):
    # Set pre-existing env vars
    monkeypatch.setenv("VERTEX_PROJECT", "old-project")
    monkeypatch.setenv("GEMINI_API_KEY", "old-key")

    # Create a temporary .env file with new values
    env_file = tmp_path / ".env"
    env_file.write_text("VERTEX_PROJECT=winter-runway-506\nGEMINI_API_KEY=AIzaSyNewTestKey\nVERTEX_LOCATION=us-central1\n")

    s = Settings(env_file=str(env_file))
    assert s.vertex_project == "winter-runway-506"
    assert s.gemini_api_key == "AIzaSyNewTestKey"
    assert s.vertex_location == "us-central1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_config.py -v`
Expected: FAIL due to missing `env_file` argument in `Settings` or missing `test_settings_dotenv_override` assertion failures.

- [ ] **Step 3: Update `backend/config.py` to support `override=True` and GCP defaults**

Update `backend/config.py`:

```python
import os
from pathlib import Path
from dotenv import load_dotenv

class Settings:
    def __init__(self, env_file: str = None):
        if env_file:
            load_dotenv(dotenv_path=env_file, override=True)
        else:
            root_env = Path(__file__).resolve().parent.parent / ".env"
            if root_env.exists():
                load_dotenv(dotenv_path=str(root_env), override=True)
            else:
                load_dotenv(override=True)

        self.default_model: str = os.getenv("DEFAULT_MODEL", "gemini-3.5-transcribe-live")
        self.vertex_project: str = os.getenv("VERTEX_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "winter-runway-506"))
        self.vertex_location: str = os.getenv("VERTEX_LOCATION", "us-central1")
        self.google_application_credentials: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", os.getenv("VERTEX_API_KEY", ""))
        self.access_token: str = os.getenv("VERTEX_ACCESS_TOKEN", "")
        
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))

    def get_vertex_ws_endpoint(self, location: str = None) -> str:
        loc = location or self.vertex_location or "us-central1"
        return f"wss://{loc}-aiplatform.googleapis.com/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent"

settings = Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/config.py tests/test_config.py
git commit -m "feat: support GEMINI_API_KEY and .env override in config"
```

---

### Task 2: Support GCP API Key Authentication in `backend/gemini_live.py`

**Files:**
- Modify: `backend/gemini_live.py`
- Test: `tests/test_backend.py`

**Interfaces:**
- Consumes: `token_or_key` or `api_key` param in `GeminiLiveBridge`
- Produces: `ws_url`, `headers`, `model_name` with `?key=` and `x-goog-api-key` support.

- [ ] **Step 1: Write failing unit tests for API key connection details**

Add tests to `tests/test_backend.py`:

```python
def test_gemini_bridge_api_key_details():
    bridge = GeminiLiveBridge(
        target_language="French",
        output_mode="audio",
        token_or_key="AIzaSyTestApiKey12345",
        project="winter-runway-506",
        location="us-central1"
    )
    ws_url, headers, model_name = bridge.get_connection_details()
    
    assert "us-central1-aiplatform.googleapis.com" in ws_url
    assert "key=AIzaSyTestApiKey12345" in ws_url
    assert headers.get("x-goog-api-key") == "AIzaSyTestApiKey12345"
    assert "Authorization" not in headers
    assert "projects/winter-runway-506/locations/us-central1/publishers/google/models/" in model_name

def test_gemini_bridge_oauth_details():
    bridge = GeminiLiveBridge(
        target_language="Spanish",
        output_mode="text",
        token_or_key="ya29.test-oauth-token",
        project="winter-runway-506",
        location="us-central1"
    )
    ws_url, headers, model_name = bridge.get_connection_details()
    
    assert "access_token=ya29.test-oauth-token" in ws_url
    assert headers.get("Authorization") == "Bearer ya29.test-oauth-token"
    assert "x-goog-api-key" not in headers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_backend.py::test_gemini_bridge_api_key_details -v`
Expected: FAIL because `AIza...` key was treated as OAuth access token previously or formatted with `access_token=`.

- [ ] **Step 3: Update `GeminiLiveBridge` in `backend/gemini_live.py`**

Update `backend/gemini_live.py`:

```python
class GeminiLiveBridge:
    def __init__(
        self,
        target_language: str = "English",
        output_mode: str = "audio",
        token_or_key: str = None,
        project: str = None,
        location: str = None,
        model: str = None
    ):
        self.target_language = target_language
        self.output_mode = output_mode.lower()
        self.token_or_key = token_or_key or settings.gemini_api_key or settings.access_token
        self.project = project or settings.vertex_project or "winter-runway-506"
        self.location = location or settings.vertex_location or "us-central1"
        self.model = model or settings.default_model

    def get_connection_details(self):
        """
        Retrieves WebSocket URL, headers, and model resource path using API key, OAuth token, or GCP ADC.
        """
        auth_type, auth_val, detected_project = self._resolve_auth()
        if detected_project and not self.project:
            self.project = detected_project

        loc = self.location or "us-central1"
        base_url = settings.get_vertex_ws_endpoint(loc)
        
        headers = {}
        if auth_type == "api_key":
            ws_url = f"{base_url}?key={auth_val}"
            headers["x-goog-api-key"] = auth_val
        elif auth_type == "oauth":
            ws_url = f"{base_url}?access_token={auth_val}"
            headers["Authorization"] = f"Bearer {auth_val}"
        else:
            ws_url = base_url

        model_name = self.model
        if self.project and not model_name.startswith("projects/"):
            model_name = f"projects/{self.project}/locations/{loc}/publishers/google/models/{self.model}"
        elif not model_name.startswith("models/") and not model_name.startswith("projects/"):
            model_name = f"models/{self.model}"

        logger.info(f"Connecting to Vertex AI WSS (Auth: {auth_type}, Project: {self.project}, Location: {loc}, Model: {model_name})")
        return ws_url, headers, model_name

    def _resolve_auth(self):
        val = self.token_or_key
        # 1. Check if token_or_key or GEMINI_API_KEY is provided
        if val:
            if val.startswith("ya29."):
                return "oauth", val, None
            else:
                return "api_key", val, None

        # 2. Attempt GCP ADC
        try:
            credentials, project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)
            logger.info("Successfully acquired Vertex AI OAuth access token via GCP ADC.")
            return "oauth", credentials.token, project
        except Exception as e:
            logger.warning(f"Could not acquire GCP ADC token: {e}")
            return "none", None, None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_backend.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/gemini_live.py tests/test_backend.py
git commit -m "feat: add GCP Gemini API key auth resolution to GeminiLiveBridge"
```

---

### Task 3: Update FastAPI Endpoints & Project Config Files

**Files:**
- Modify: `backend/main.py`
- Modify: `.env`, `.env.example`, `docker-compose.yml`, `k8s/configmap.yaml`, `README.md`
- Test: `tests/test_backend.py`

**Interfaces:**
- Consumes: `settings` and `GeminiLiveBridge`
- Produces: `/api/health` JSON response with `auth_type`, `vertex_project: winter-runway-506`, `vertex_location: us-central1`.

- [ ] **Step 1: Write failing test for updated `/api/health` endpoint**

Update `test_health_check_endpoint()` in `tests/test_backend.py`:

```python
def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["provider"] == "vertex_ai"
    assert data["model"] == "gemini-3.5-transcribe-live"
    assert data["vertex_project"] == "winter-runway-506"
    assert data["vertex_location"] == "us-central1"
    assert "has_credentials" in data
```

- [ ] **Step 2: Run test to verify it fails if defaults/keys are missing**

Run: `./venv/bin/pytest tests/test_backend.py::test_health_check_endpoint -v`

- [ ] **Step 3: Update `backend/main.py`**

Update `backend/main.py`:

```python
@app.get("/api/health")
async def health_check():
    has_creds = bool(settings.gemini_api_key or settings.access_token or settings.google_application_credentials)
    return {
        "status": "healthy",
        "provider": "vertex_ai",
        "model": settings.default_model,
        "vertex_project": settings.vertex_project,
        "vertex_location": settings.vertex_location,
        "has_credentials": has_creds
    }
```

- [ ] **Step 4: Update `.env`, `.env.example`, `docker-compose.yml`, `k8s/configmap.yaml`, `README.md`**

In `.env` and `.env.example`:
```env
# GCP Vertex AI / Gemini API Configuration
VERTEX_PROJECT=winter-runway-506
VERTEX_LOCATION=us-central1

# Option 1: GCP API Key with Gemini API permissions (Recommended)
GEMINI_API_KEY=

# Option 2: Path to GCP Service Account JSON key file
GOOGLE_APPLICATION_CREDENTIALS=

# Option 3: OAuth 2.0 Access Token
VERTEX_ACCESS_TOKEN=

# Model & Server Settings
DEFAULT_MODEL=gemini-3.5-transcribe-live
HOST=0.0.0.0
PORT=8000
```

In `docker-compose.yml`:
Add `- GEMINI_API_KEY=${GEMINI_API_KEY}` under `environment:`.

In `k8s/configmap.yaml`:
Set `VERTEX_PROJECT: "winter-runway-506"` and `VERTEX_LOCATION: "us-central1"`.

In `README.md`:
Document `GEMINI_API_KEY` usage with GCP project `winter-runway-506` and region `us-central1`.

- [ ] **Step 5: Run tests and verify full suite passes**

Run: `./venv/bin/pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/main.py .env .env.example docker-compose.yml k8s/configmap.yaml README.md tests/test_backend.py
git commit -m "feat: complete GCP Gemini API key integration, defaults and documentation"
```
