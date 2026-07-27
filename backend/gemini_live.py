import os
import json
import logging
from urllib.parse import quote_plus
from backend.config import settings

try:
    from google import genai
    from google.genai import types
    HAS_GENAI_SDK = True
except ImportError:
    HAS_GENAI_SDK = False

logger = logging.getLogger("gemini_live")
logger.setLevel(logging.INFO)

class GeminiLiveBridge:
    def __init__(
        self,
        target_language: str = "English",
        output_mode: str = "audio",
        model: str = None
    ):
        self.target_language = target_language
        self.output_mode = output_mode.lower()
        self.api_key = settings.gemini_api_key
        self.model = model or settings.default_model

    def get_genai_client(self):
        if not HAS_GENAI_SDK:
            raise ImportError("google-genai SDK is not installed.")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        return genai.Client(api_key=self.api_key)

    def build_live_connect_config(self):
        if not HAS_GENAI_SDK:
            raise ImportError("google-genai SDK is not installed.")

        modalities = ["AUDIO"] if self.output_mode == "audio" else ["AUDIO"]
        prompt = (
            f"You are a real-time simultaneous live interpreter. "
            f"Continuously translate all incoming speech immediately into {self.target_language} without waiting for the speaker to pause or stop. "
            f"Always output the translated text transcript in {self.target_language}. "
            f"When speaking the translation, speak clearly in {self.target_language} with natural intonation. "
            f"Do not include commentary or extra conversational filler; output strictly the accurate translation."
        )

        return types.LiveConnectConfig(
            response_modalities=modalities,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=prompt)]
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=25600,
                sliding_window=types.SlidingWindow(target_tokens=12800),
            ),
        )

    def get_connection_details(self):
        """
        Retrieves WebSocket URL, headers, and model resource path for Gemini API.
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        base_url = settings.get_generative_language_ws_endpoint()
        encoded_key = quote_plus(self.api_key)
        ws_url = f"{base_url}?key={encoded_key}"
        headers = {"x-goog-api-key": self.api_key}

        model_name = self.model
        if not model_name.startswith("models/"):
            model_name = f"models/{self.model}"

        logger.info(f"Connecting to Gemini API WSS Endpoint (Model: {model_name})")
        return ws_url, headers, model_name

    def build_initial_setup_message(self, model_name: str = None):
        modalities = ["AUDIO"]
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
                "audio": {
                    "mimeType": "audio/pcm;rate=16000",
                    "data": pcm_b64
                }
            }
        }
