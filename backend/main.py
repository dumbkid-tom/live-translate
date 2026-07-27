import os
import json
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import websockets

from backend.config import settings
from backend.gemini_live import GeminiLiveBridge

logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Live Translate API (Gemini API)", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    has_api_key = bool(settings.gemini_api_key)
    return {
        "status": "healthy",
        "provider": "gemini_api",
        "endpoint": "https://generativelanguage.googleapis.com",
        "model": settings.default_model,
        "has_api_key": has_api_key
    }

@app.websocket("/ws/translate")
async def websocket_translate(
    websocket: WebSocket,
    target_language: str = Query("English"),
    mode: str = Query("audio"),
    api_key: str = Query(None)
):
    await websocket.accept()

    bridge = GeminiLiveBridge(
        target_language=target_language,
        output_mode=mode,
        api_key=api_key
    )

    try:
        ws_url, headers, model_name = bridge.get_connection_details()
        logger.info(f"Connecting to Gemini API WSS Endpoint: {ws_url}")

        connect_kwargs = {}
        if headers:
            connect_kwargs["additional_headers"] = headers

        async with websockets.connect(ws_url, **connect_kwargs) as gemini_ws:
            # Send setup frame to Gemini API
            setup_payload = bridge.build_initial_setup_message(model_name=model_name)
            await gemini_ws.send(json.dumps(setup_payload))

            # Send session started confirmation to frontend client
            await websocket.send_json({
                "type": "connected",
                "target_language": target_language,
                "mode": mode,
                "model": model_name,
                "provider": "gemini_api"
            })

            async def client_to_gemini():
                try:
                    while True:
                        msg_text = await websocket.receive_text()
                        msg = json.loads(msg_text)
                        msg_type = msg.get("type")

                        if msg_type == "audio_chunk" and "data" in msg:
                            audio_frame = bridge.build_realtime_audio_chunk(msg["data"])
                            await gemini_ws.send(json.dumps(audio_frame))
                        elif msg_type == "stop":
                            logger.info("Received stop request from client.")
                            break
                except WebSocketDisconnect:
                    logger.info("Client WebSocket disconnected.")
                except Exception as e:
                    logger.error(f"Error reading client WS: {e}")

            async def gemini_to_client():
                try:
                    async for raw_response in gemini_ws:
                        resp = json.loads(raw_response)
                        server_content = resp.get("serverContent", {})
                        model_turn = server_content.get("modelTurn", {})
                        parts = model_turn.get("parts", [])

                        for part in parts:
                            if "text" in part and part["text"]:
                                await websocket.send_json({
                                    "type": "text",
                                    "text": part["text"]
                                })
                            if "inlineData" in part:
                                inline_data = part["inlineData"]
                                mime_type = inline_data.get("mimeType", "")
                                if mime_type.startswith("audio/"):
                                    await websocket.send_json({
                                        "type": "audio",
                                        "data": inline_data.get("data", ""),
                                        "mimeType": mime_type
                                    })
                        
                        if server_content.get("turnComplete"):
                            await websocket.send_json({"type": "turn_complete"})

                except Exception as e:
                    logger.error(f"Error reading Gemini API WSS: {e}")

            await asyncio.gather(client_to_gemini(), gemini_to_client(), return_exceptions=True)

    except Exception as e:
        logger.error(f"WebSocket translation exception: {e}")
        try:
            await websocket.send_json({"type": "error", "message": f"Connection error: {str(e)}"})
            await websocket.close()
        except Exception:
            pass

# Mount static frontend directory
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def read_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return JSONResponse(content={"status": "Live Translate Service (Gemini API) is active"})
