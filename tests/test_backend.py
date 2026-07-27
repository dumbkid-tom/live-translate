import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app
from backend.gemini_live import GeminiLiveBridge

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

def test_gemini_bridge_initial_setup():
    bridge = GeminiLiveBridge(target_language="Spanish", output_mode="audio", api_key="test-key")
    setup_msg = bridge.build_initial_setup_message()
    
    assert "AUDIO" in setup_msg["setup"]["generationConfig"]["responseModalities"]
    assert "TEXT" in setup_msg["setup"]["generationConfig"]["responseModalities"]
    assert "Spanish" in setup_msg["setup"]["systemInstruction"]["parts"][0]["text"]

def test_gemini_bridge_api_key_details():
    bridge = GeminiLiveBridge(
        target_language="French",
        output_mode="audio",
        api_key="AIzaSyTestApiKey12345"
    )
    ws_url, headers, model_name = bridge.get_connection_details()
    
    assert "generativelanguage.googleapis.com" in ws_url
    assert "key=AIzaSyTestApiKey12345" in ws_url
    assert headers.get("x-goog-api-key") == "AIzaSyTestApiKey12345"
    assert "Authorization" not in headers
    assert model_name.startswith("models/")

def test_gemini_bridge_custom_model_details():
    bridge = GeminiLiveBridge(
        target_language="German",
        output_mode="audio",
        api_key="AIzaSyTestApiKey12345",
        model="gemini-2.0-flash-exp"
    )
    ws_url, headers, model_name = bridge.get_connection_details()
    
    assert model_name == "models/gemini-2.0-flash-exp"

def test_gemini_bridge_realtime_audio_chunk():
    bridge = GeminiLiveBridge(target_language="English", output_mode="audio")
    dummy_b64 = "AAAA////"
    chunk = bridge.build_realtime_audio_chunk(dummy_b64)
    
    assert chunk["realtimeInput"]["mediaChunks"][0]["mimeType"] == "audio/pcm;rate=16000"
    assert chunk["realtimeInput"]["mediaChunks"][0]["data"] == dummy_b64
