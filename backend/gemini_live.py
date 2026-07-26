import os
import json
import asyncio
import logging
import google.auth
import google.auth.transport.requests
from backend.config import settings

logger = logging.getLogger("gemini_live")
logger.setLevel(logging.INFO)

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

    def build_initial_setup_message(self, model_name: str = None):
        modalities = ["AUDIO", "TEXT"] if self.output_mode == "audio" else ["TEXT"]
        target_model = model_name or self.model
        if not target_model.startswith("projects/") and not target_model.startswith("models/"):
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
