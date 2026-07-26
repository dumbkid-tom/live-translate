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
    assert data["provider"] == "vertex_ai"
    assert data["model"] == "gemini-3.5-live-translate-preview"
    assert data["vertex_project"] == "winter-runway-506"
    assert data["vertex_location"] == "us-central1"
    assert "has_credentials" in data

def test_index_route():
    response = client.get("/")
    assert response.status_code == 200

def test_gemini_bridge_initial_setup():
    bridge = GeminiLiveBridge(target_language="Spanish", output_mode="audio", token_or_key="ya29.test")
    setup_msg = bridge.build_initial_setup_message()
    
    assert "AUDIO" in setup_msg["setup"]["generationConfig"]["responseModalities"]
    assert "TEXT" in setup_msg["setup"]["generationConfig"]["responseModalities"]
    assert "Spanish" in setup_msg["setup"]["systemInstruction"]["parts"][0]["text"]

def test_gemini_bridge_vertex_details():
    bridge = GeminiLiveBridge(
        target_language="Japanese",
        output_mode="text",
        token_or_key="ya29.test-token",
        project="winter-runway-506",
        location="us-central1"
    )
    ws_url, headers, model_name = bridge.get_connection_details()
    
    assert "us-central1-aiplatform.googleapis.com" in ws_url
    assert "access_token=ya29.test-token" in ws_url
    assert headers.get("Authorization") == "Bearer ya29.test-token"
    assert "projects/winter-runway-506/locations/us-central1/publishers/google/models/" in model_name

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

def test_gemini_bridge_realtime_audio_chunk():
    bridge = GeminiLiveBridge(target_language="English", output_mode="audio")
    dummy_b64 = "AAAA////"
    chunk = bridge.build_realtime_audio_chunk(dummy_b64)
    
    assert chunk["realtimeInput"]["mediaChunks"][0]["mimeType"] == "audio/pcm;rate=16000"
    assert chunk["realtimeInput"]["mediaChunks"][0]["data"] == dummy_b64
