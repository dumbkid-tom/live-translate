import os
import json
import logging
from backend.config import settings

logger = logging.getLogger("gemini_live")
logger.setLevel(logging.INFO)

class GeminiLiveBridge:
    def __init__(
        self,
        target_language: str = "English",
        output_mode: str = "audio",
        api_key: str = None,
        model: str = None
    ):
        self.target_language = target_language
        self.output_mode = output_mode.lower()
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.default_model

    def get_connection_details(self):
        """
        Retrieves WebSocket URL, headers, and model resource path for Gemini API.
        """
        base_url = settings.get_generative_language_ws_endpoint()
        ws_url = f"{base_url}?key={self.api_key}"
        headers = {"x-goog-api-key": self.api_key}

        model_name = self.model
        if not model_name.startswith("models/"):
            model_name = f"models/{self.model}"

        logger.info(f"Connecting to Gemini API WSS Endpoint (Model: {model_name})")
        return ws_url, headers, model_name

    def build_initial_setup_message(self, model_name: str = None):
        modalities = ["AUDIO", "TEXT"] if self.output_mode == "audio" else ["TEXT"]
        target_model = model_name or self.model
        if not target_model.startswith("models/"):
            target_model = f"models/{target_model}"

        prompt = (
            f"You are a real-time live interpreter. Translate all audio input directly and immediately into {self.target_language}. "
            f"Always output the translated text transcript in {self.target_language}. "
            f"If audio modality is requested, speak the translation clearly in {self.target_language} with natural intonation. "
            f"Do not include commentary or extra conversational filler; output strictly the accurate translation."
        )

        setup_msg = {
            "setup": {
                "model": target_model,
                "generationConfig": {
                    "responseModalities": modalities,
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": "Puck"
                            }
                        }
                    }
                },
                "systemInstruction": {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            }
        }
        return setup_msg

    def build_realtime_audio_chunk(self, pcm_b64: str):
        return {
            "realtimeInput": {
                "mediaChunks": [
                    {
                        "mimeType": "audio/pcm;rate=16000",
                        "data": pcm_b64
                    }
                ]
            }
        }
