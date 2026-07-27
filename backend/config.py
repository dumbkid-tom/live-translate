import os
from pathlib import Path
from dotenv import load_dotenv

class Settings:
    def __init__(self, env_file: str = None):
        if env_file:
            load_dotenv(dotenv_path=env_file, override=True)
        else:
            root_env = Path(__file__).resolve().parent.parent / ".env"
            if root_env.exists():
                load_dotenv(dotenv_path=str(root_env), override=True)
            else:
                load_dotenv(override=True)

        self.default_model: str = os.getenv("DEFAULT_MODEL", "gemini-3.1-flash-live-preview")
        self.gemini_api_key: str = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))

    def get_generative_language_ws_endpoint(self) -> str:
        return "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"

settings = Settings()
