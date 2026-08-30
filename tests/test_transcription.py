import pytest
from unittest.mock import MagicMock, patch
from backend.gemini_live import (
    build_transcription_setup,
    build_live_session_config,
    TokenService,
)
from backend.config import settings

TEXT = __import__("google.genai", fromlist=["types"]).types.Modality.TEXT
SMART = __import__("google.genai", fromlist=["types"]).types.AudioTranscriptionConfigMode.SMART


def test_build_transcription_setup_defaults():
    """Default transcription uses gemini-3.5-live-translate-preview with TEXT output."""
    setup = build_transcription_setup()["setup"]
    assert setup["model"] == "models/gemini-3.5-live-translate-preview"
    assert setup["generationConfig"]["responseModalities"] == ["TEXT"]
    assert setup["inputAudioTranscription"]["languageCodes"] == []
    assert setup["inputAudioTranscription"]["customVocabulary"] == []
    assert setup["inputAudioTranscription"]["mode"] == "verbatim"
    assert setup["outputAudioTranscription"] == {}


def test_build_transcription_setup_explicit_values():
    setup = build_transcription_setup(
        transcription_mode="smart",
        language_codes=["es-ES", "fr-FR"],
        custom_vocabulary=["Gemini", "Kubernetes"],
    )["setup"]
    assert setup["model"] == "models/gemini-3.5-live-translate-preview"
    assert setup["generationConfig"]["responseModalities"] == ["TEXT"]
    assert setup["inputAudioTranscription"]["languageCodes"] == ["es-ES", "fr-FR"]
    assert setup["inputAudioTranscription"]["customVocabulary"] == ["Gemini", "Kubernetes"]
    assert setup["inputAudioTranscription"]["mode"] == "smart"


def test_build_transcription_setup_with_model_prefix():
    setup = build_transcription_setup(model="models/gemini-3.5-live-translate-preview")["setup"]
    assert setup["model"] == "models/gemini-3.5-live-translate-preview"


def test_transcribe_mode_uses_transcribe_ws_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "fake-key")
    mock_token = MagicMock()
    mock_token.name = "auth_tokens/transcribe_ws"
    mock_client = MagicMock()
    mock_client.auth_tokens.create.return_value = mock_token

    with patch("backend.gemini_live.genai.Client", return_value=mock_client):
        resp = TokenService().create("Spanish", "audio", translation_mode="transcribe")

    assert resp["ws_endpoint"].startswith(
        "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta"
    )
    # The response's mode field mirrors tr_mode; the transcription_mode field
    # is the explicit indicator that this is a speech-to-text session.
    assert resp["translation_mode"] == "transcribe"
    assert resp["transcription_mode"] == "transcribe"
    assert resp["model"] == "models/gemini-3.5-live-translate-preview"


def test_transcribe_vad_disabled_sets_realtime_input_config(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "fake-key")
    mock_token = MagicMock()
    mock_token.name = "auth_tokens/vad_check"
    mock_client = MagicMock()
    mock_client.auth_tokens.create.return_value = mock_token

    with patch("backend.gemini_live.genai.Client", return_value=mock_client):
        resp = TokenService().create(
            "Spanish",
            "audio",
            translation_mode="transcribe",
            vad_disabled=True,
        )

        call = mock_client.auth_tokens.create.call_args
        config = call.kwargs["config"].live_connect_constraints.config
        assert config.realtime_input_config is not None
        assert config.realtime_input_config.automatic_activity_detection.disabled is True


def test_transcribe_mode_sdk_config_fields(monkeypatch):
    """End-to-end verification the SDK receives documented transcribe fields."""
    monkeypatch.setattr(settings, "gemini_api_key", "fake-key")
    mock_token = MagicMock()
    mock_token.name = "auth_tokens/full_check"
    mock_client = MagicMock()
    mock_client.auth_tokens.create.return_value = mock_token

    with patch("backend.gemini_live.genai.Client", return_value=mock_client):
        resp = TokenService().create(
            "Spanish",
            "audio",
            translation_mode="transcribe",
            transcription_mode="smart",
            language_codes=["es-ES"],
            custom_vocabulary=["Gemini"],
            vad_disabled=True,
        )

        call = mock_client.auth_tokens.create.call_args
        config = call.kwargs["config"].live_connect_constraints.config

        assert config.response_modalities == [TEXT]
        assert config.input_audio_transcription.language_codes == ["es-ES"]
        assert config.input_audio_transcription.custom_vocabulary == ["Gemini"]
        assert config.input_audio_transcription.mode == SMART
        assert config.realtime_input_config.automatic_activity_detection.disabled is True
