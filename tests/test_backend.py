import sys
import os
import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app
from backend.gemini_live import GeminiLiveBridge
from backend.config import settings

client = TestClient(app)

def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["provider"] == "gemini_api"
    assert data["endpoint"] == "https://generativelanguage.googleapis.com"
    assert "has_api_key" in data

def test_index_route():
    response = client.get("/")
    assert response.status_code == 200

def test_gemini_bridge_initial_setup(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    bridge = GeminiLiveBridge(target_language="Spanish", output_mode="audio")
    setup_msg = bridge.build_initial_setup_message()
    
    assert "AUDIO" in setup_msg["setup"]["generationConfig"]["responseModalities"]
    assert "Spanish" in setup_msg["setup"]["systemInstruction"]["parts"][0]["text"]

def test_gemini_bridge_api_key_details(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "AIzaSyTestApiKey12345")
    bridge = GeminiLiveBridge(
        target_language="French",
        output_mode="audio"
    )
    ws_url, headers, model_name = bridge.get_connection_details()
    
    assert "generativelanguage.googleapis.com" in ws_url
    assert "key=AIzaSyTestApiKey12345" in ws_url
    assert headers.get("x-goog-api-key") == "AIzaSyTestApiKey12345"
    assert "Authorization" not in headers
    assert model_name.startswith("models/")

def test_gemini_bridge_url_encoding(monkeypatch):
    key_with_special_chars = "AIzaSyTest+Key/123="
    monkeypatch.setattr(settings, "gemini_api_key", key_with_special_chars)
    bridge = GeminiLiveBridge(
        target_language="French",
        output_mode="audio"
    )
    ws_url, headers, model_name = bridge.get_connection_details()
    
    assert "key=AIzaSyTest%2BKey%2F123%3D" in ws_url
    assert headers.get("x-goog-api-key") == key_with_special_chars

def test_gemini_bridge_missing_api_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    bridge = GeminiLiveBridge(target_language="English")
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is not set"):
        bridge.get_connection_details()

def test_websocket_missing_api_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with client.websocket_connect("/ws/translate") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "error"
        assert data["message"] == "GEMINI_API_KEY environment variable is not set."
        with pytest.raises(WebSocketDisconnect) as exc_info:
            websocket.receive_json()
        assert exc_info.value.code == 1008

def test_gemini_bridge_custom_model_details(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "AIzaSyTestApiKey12345")
    bridge = GeminiLiveBridge(
        target_language="German",
        output_mode="audio",
        model="gemini-2.0-flash-exp"
    )
    ws_url, headers, model_name = bridge.get_connection_details()
    
    assert model_name == "models/gemini-2.0-flash-exp"

def test_gemini_bridge_realtime_audio_chunk():
    bridge = GeminiLiveBridge(target_language="English", output_mode="audio")
    dummy_b64 = "AAAA////"
    chunk = bridge.build_realtime_audio_chunk(dummy_b64)
    
    assert chunk["realtimeInput"]["audio"]["mimeType"] == "audio/pcm;rate=16000"
    assert chunk["realtimeInput"]["audio"]["data"] == dummy_b64

def test_gemini_bridge_genai_connect_config(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key-123")
    bridge = GeminiLiveBridge(target_language="Japanese", output_mode="audio")
    config = bridge.build_live_connect_config()
    
    assert config.response_modalities == ["AUDIO"]
    assert config.input_audio_transcription is not None
    assert config.output_audio_transcription is not None
    assert "Japanese" in config.system_instruction.parts[0].text
