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

        self.default_model: str = os.getenv("DEFAULT_MODEL", "gemini-3.5-live-translate-preview")
        self.vertex_project: str = os.getenv("VERTEX_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "winter-runway-506"))
        self.vertex_location: str = os.getenv("VERTEX_LOCATION", "us-central1")
        self.google_application_credentials: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", os.getenv("VERTEX_API_KEY", ""))
        self.access_token: str = os.getenv("VERTEX_ACCESS_TOKEN", "")
        
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))

    def get_vertex_ws_endpoint(self, location: str = None) -> str:
        loc = location or self.vertex_location or "us-central1"
        return f"wss://{loc}-aiplatform.googleapis.com/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent"

settings = Settings()
