import pytest
from unittest.mock import MagicMock, patch
from backend.gemini_live import (
    build_interpreter_prompt,
    build_live_session_config,
    build_translation_setup,
    TokenService
)
from backend.config import settings

def test_build_interpreter_prompt_variations():
    p1 = build_interpreter_prompt("Spanish")
    assert "Spanish" in p1
    assert "from" not in p1

    p2 = build_interpreter_prompt("Japanese", "English")
    assert "Japanese" in p2
    assert "from English" in p2

def test_build_translation_setup():
    setup_data = build_translation_setup("Spanish", echo_target_language=True)
    setup = setup_data["setup"]
    assert setup["model"] == "models/gemini-3.5-live-translate-preview"
    assert setup["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert setup["generationConfig"]["translationConfig"]["targetLanguageCode"] == "es"
    assert setup["generationConfig"]["translationConfig"]["echoTargetLanguage"] is True
    assert setup["inputAudioTranscription"] == {}
    assert setup["outputAudioTranscription"] == {}

def test_build_live_session_config_structure():
    cfg = build_live_session_config("German", "audio", "gemini-3.1-flash-live-preview", "French", silence_duration_ms=600, translation_mode="turn_based")
    setup = cfg["setup"]
    assert setup["model"] == "models/gemini-3.1-flash-live-preview"
    assert setup["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert setup["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Puck"
    assert setup["realtimeInputConfig"]["activityHandling"] == "NO_INTERRUPTION"
    assert setup["realtimeInputConfig"]["automaticActivityDetection"]["silenceDurationMs"] == 600
    assert setup["inputAudioTranscription"] == {}
    assert setup["outputAudioTranscription"] == {}
    assert "German" in setup["systemInstruction"]["parts"][0]["text"]

def test_token_service_create(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "mock-key-456")
    mock_token = MagicMock()
    mock_token.name = "auth_tokens/test_token_999"

    mock_client = MagicMock()
    mock_client.auth_tokens.create.return_value = mock_token

    with patch("backend.gemini_live.genai.Client", return_value=mock_client):
        service = TokenService()
        resp = service.create("Italian", "audio", translation_mode="simultaneous")

        assert resp["token"] == "auth_tokens/test_token_999"
        assert "access_token=auth_tokens/test_token_999" in resp["ws_endpoint"]
        assert resp["setup"]["model"] == "models/gemini-3.5-live-translate-preview"
        assert resp["translation_mode"] == "simultaneous"
        assert resp["target_language_code"] == "it"
