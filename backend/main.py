import os
import time
import logging
from collections import defaultdict
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from backend.config import settings
from backend.gemini_live import TokenService, HAS_GENAI_SDK

logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Live Translate API (Gemini Live Ephemeral Tokens)", version="2.0.0")

allow_credentials = False if "*" in settings.allowed_origins else True

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory rate limiting per client IP for /api/token
ip_request_history = defaultdict(list)

def check_rate_limit(client_ip: str):
    now = time.time()
    cutoff = now - 60.0
    history = [t for t in ip_request_history[client_ip] if t > cutoff]
    if len(history) >= settings.token_rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {settings.token_rate_limit_per_minute} token requests per minute."
        )
    history.append(now)
    ip_request_history[client_ip] = history

class TokenRequest(BaseModel):
    target_language: Optional[str] = "English"
    mode: Optional[str] = "audio"
    model: Optional[str] = None
    source_language: Optional[str] = None
    silence_duration_ms: Optional[int] = Field(default=300, ge=100, le=2000)
    translation_mode: Optional[str] = None
    echo_target_language: Optional[bool] = False
    transcription_mode: Optional[str] = "verbatim"
    language_codes: Optional[list[str]] = None
    custom_vocabulary: Optional[list[str]] = None
    vad_disabled: Optional[bool] = False

    @field_validator("translation_mode")
    @classmethod
    def validate_translation_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_lower = str(v).strip().lower()
            if v_lower not in ("simultaneous", "turn_based"):
                raise ValueError("translation_mode must be 'simultaneous' or 'turn_based'")
            return v_lower
        return v

    @field_validator("transcription_mode")
    @classmethod
    def validate_transcription_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_lower = str(v).strip().lower()
            if v_lower not in ("verbatim", "smart"):
                raise ValueError("transcription_mode must be 'verbatim' or 'smart'")
            return v_lower
        return v

@app.get("/api/health")
async def health_check():
    has_api_key = bool(settings.gemini_api_key)
    return {
        "status": "healthy",
        "provider": "gemini_live_ephemeral",
        "endpoint": settings.get_live_ws_endpoint(),
        "model": settings.default_model,
        "has_api_key": has_api_key,
        "token_uses": settings.token_uses,
        "token_ttl_minutes": settings.token_ttl_minutes
    }

@app.post("/api/token")
async def create_token(request: Request, body: TokenRequest = TokenRequest()):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GEMINI_API_KEY environment variable is not set."
        )

    if not HAS_GENAI_SDK:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="google-genai SDK is not installed on the server."
        )

    try:
        service = TokenService()
        token_data = service.create(
            target_language=body.target_language,
            mode=body.mode,
            model=body.model,
            source_language=body.source_language,
            silence_duration_ms=body.silence_duration_ms or 300,
            translation_mode=body.translation_mode,
            echo_target_language=body.echo_target_language or False,
            transcription_mode=body.transcription_mode,
            language_codes=body.language_codes,
            custom_vocabulary=body.custom_vocabulary,
            vad_disabled=body.vad_disabled or False
        )
        return JSONResponse(content=token_data)
    except Exception as e:
        logger.exception("Failed to generate ephemeral token: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate ephemeral token: {str(e)}"
        )

# Mount static frontend directory
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Favicon assets (generated by scripts/make_favicon.py)
favicon_dir = os.path.join(static_dir, "favicon")
favicon_assets = {}
if os.path.isdir(favicon_dir):
    for fname in os.listdir(favicon_dir):
        fpath = os.path.join(favicon_dir, fname)
        if os.path.isfile(fpath):
            favicon_assets[fname] = fpath

    @app.get("/favicon.ico")
    async def favicon_ico():
        path = favicon_assets.get("favicon.ico")
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                return Response(content=f.read(), media_type="image/x-icon")
        # Fall back to serving the SVG source asset if present.
        path = favicon_assets.get("gemini-logo.svg")
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                return Response(content=f.read(), media_type="image/svg+xml")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

@app.get("/")
async def read_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return JSONResponse(content={"status": "Live Translate Service (Gemini Ephemeral Tokens) is active"})
