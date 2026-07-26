import sys
import os
import tempfile
from pathlib import Path
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import Settings, settings

def test_settings_default():
    assert settings.default_model == "gemini-3.5-live-translate-preview"
    assert settings.port == 8000
    assert "aiplatform.googleapis.com" in settings.get_vertex_ws_endpoint("us-central1")

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
