import os
from pathlib import Path
from dotenv import load_dotenv

class Settings:
    def __init__(self, env_file: str = None):
        if env_file:
            load_dotenv(dotenv_path=env_file, override=False)
        else:
            root_env = Path(__file__).resolve().parent.parent / ".env"
            if root_env.exists():
                load_dotenv(dotenv_path=str(root_env), override=False)
            else:
                load_dotenv(override=False)

        self.default_model: str = os.getenv("DEFAULT_MODEL", "gemini-3.1-flash-live-preview")
        # Simultaneous live audio translation (speech-to-speech): this model
        # supports the AUDIO response modality the WebSocket full-duplex flow
        # requires. Confirmed working for both the simultaneous-translate and
        # transcription paths over a real WebSocket.
        self.translate_model: str = os.getenv("TRANSLATE_MODEL", "gemini-3.5-live-translate-preview")
        self.transcribe_model: str = os.getenv("TRANSCRIPTION_MODEL", "gemini-3.5-live-translate-preview")
        self.translation_mode: str = os.getenv("TRANSLATION_MODE", "simultaneous").lower()
        if self.translation_mode not in ("simultaneous", "turn_based"):
            self.translation_mode = "simultaneous"

        # Live Transcribe (speech-to-text) settings, per the Live Transcribe API:
        # https://ai.google.dev/gemini-api/docs/live-api/live-transcribe
        self.transcription_mode: str = (
            os.getenv("TRANSCRIPTION_MODE", "verbatim").strip().lower()
        )
        if self.transcription_mode not in ("verbatim", "smart"):
            self.transcription_mode = "verbatim"
        self.custom_vocabulary: list[str] = [
            t.strip() for t in os.getenv("CUSTOM_VOCABULARY", "").split(",") if t.strip()
        ]
        self.transcription_language_codes: list[str] = [
            c.strip() for c in os.getenv("TRANSCRIPTION_LANGUAGE_CODES", "").split(",") if c.strip()
        ]
        self.transcription_vad_disabled: bool = (
            os.getenv("TRANSCRIPTION_VAD_DISABLED", "false").lower() in ("true", "1", "t", "yes")
        )
        # The transcribe live API serves over the v1beta generative-language WebSocket.
        # Overridable; see get_transcribe_ws_endpoint().
        self.transcribe_ws_version: str = os.getenv("TRANSCRIBE_WS_VERSION", "v1beta")
        self.gemini_api_key: str = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        
        self.token_uses: int = int(os.getenv("TOKEN_USES", "1"))
        self.token_ttl_minutes: int = int(os.getenv("TOKEN_TTL_MINUTES", "30"))
        self.token_new_session_ttl_minutes: int = int(os.getenv("TOKEN_NEW_SESSION_TTL_MINUTES", "5"))
        self.lock_token_constraints: bool = os.getenv("LOCK_TOKEN_CONSTRAINTS", "true").lower() in ("true", "1", "t", "yes")
        self.allowed_origins: list[str] = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",") if origin.strip()]
        self.token_rate_limit_per_minute: int = int(os.getenv("TOKEN_RATE_LIMIT_PER_MINUTE", "10"))

    def get_generative_language_ws_endpoint(self) -> str:
        return "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"

    def get_live_ws_endpoint(self) -> str:
        return "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained"

    def get_transcribe_ws_endpoint(self) -> str:
        version = self.transcribe_ws_version
        service = (
            "GenerativeService.BidiGenerateContentConstrained"
            if version == "v1beta"
            else "GenerativeService.BidiGenerateContent"
        )
        return f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.{version}.{service}"

settings = Settings()
