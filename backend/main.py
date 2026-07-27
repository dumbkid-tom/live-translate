import os
import json
import asyncio
import logging
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import websockets

from backend.config import settings
from backend.gemini_live import GeminiLiveBridge, HAS_GENAI_SDK
if HAS_GENAI_SDK:
    from google.genai import types

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
    mode: str = Query("audio")
):
    await websocket.accept()

    if not settings.gemini_api_key:
        await websocket.send_json({
            "type": "error",
            "message": "GEMINI_API_KEY environment variable is not set."
        })
        await websocket.close(code=1008)
        return

    bridge = GeminiLiveBridge(
        target_language=target_language,
        output_mode=mode
    )

    if HAS_GENAI_SDK:
        try:
            client = bridge.get_genai_client()
            config = bridge.build_live_connect_config()
            model_name = bridge.model

            logger.info("Connecting to Gemini Live API via google-genai SDK (model=%s)", model_name)
            async with client.aio.live.connect(model=model_name, config=config) as session:
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
                                pcm_bytes = base64.b64decode(msg["data"])
                                blob = types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
                                await session.send_realtime_input(audio=blob)
                            elif msg_type == "text" and "text" in msg:
                                await session.send_realtime_input(text=msg["text"])
                            elif msg_type == "stop":
                                logger.info("Received stop request from client.")
                                break
                    except WebSocketDisconnect:
                        logger.info("Client WebSocket disconnected.")
                    except Exception as e:
                        sanitized_err = str(e).split("?")[0]
                        logger.error("Error reading client WS (%s): %s", type(e).__name__, sanitized_err)

                async def gemini_to_client():
                    try:
                        while True:
                            async for response in session.receive():
                                server_content = response.server_content
                                if server_content is None:
                                    continue

                                if server_content.interrupted:
                                    await websocket.send_json({"type": "interrupted"})

                                if server_content.model_turn:
                                    for part in server_content.model_turn.parts:
                                        if part.text:
                                            await websocket.send_json({
                                                "type": "text",
                                                "text": part.text
                                            })
                                        if part.inline_data:
                                            inline_data = part.inline_data
                                            mime_type = inline_data.mime_type or ""
                                            raw_data = inline_data.data
                                            if isinstance(raw_data, bytes):
                                                audio_b64 = base64.b64encode(raw_data).decode("utf-8")
                                            else:
                                                audio_b64 = str(raw_data)

                                            if mime_type.startswith("audio/"):
                                                await websocket.send_json({
                                                    "type": "audio",
                                                    "data": audio_b64,
                                                    "mimeType": mime_type
                                                })

                                if server_content.output_transcription and server_content.output_transcription.text:
                                    await websocket.send_json({
                                        "type": "text",
                                        "text": server_content.output_transcription.text
                                    })

                                if server_content.turn_complete:
                                    await websocket.send_json({"type": "turn_complete"})

                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        sanitized_err = str(e).split("?")[0]
                        logger.error("Error reading Gemini API Session (%s): %s", type(e).__name__, sanitized_err)

                await asyncio.gather(client_to_gemini(), gemini_to_client(), return_exceptions=True)
                return

        except Exception as sdk_err:
            sanitized_err = str(sdk_err).split("?")[0]
            logger.warning("SDK connect failed (%s): %s. Falling back to WSS.", type(sdk_err).__name__, sanitized_err)

    try:
        ws_url, headers, model_name = bridge.get_connection_details()
        logger.info("Connecting to Gemini API WSS endpoint (model=%s)", model_name)

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
                    sanitized_err = str(e).split("?")[0]
                    logger.error("Error reading client WS (%s): %s", type(e).__name__, sanitized_err)

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
                    sanitized_err = str(e).split("?")[0]
                    logger.error("Error reading Gemini API WSS (%s): %s", type(e).__name__, sanitized_err)

            await asyncio.gather(client_to_gemini(), gemini_to_client(), return_exceptions=True)

    except ValueError as ve:
        sanitized_err = str(ve).split("?")[0]
        logger.error("API key validation error (%s): %s", type(ve).__name__, sanitized_err)
        try:
            await websocket.send_json({"type": "error", "message": sanitized_err})
            await websocket.close(code=1008)
        except Exception:
            pass
    except Exception as e:
        sanitized_err = str(e).split("?")[0]
        logger.error("WebSocket translation exception (%s): %s", type(e).__name__, sanitized_err)
        try:
            await websocket.send_json({"type": "error", "message": f"Connection error: {sanitized_err}"})
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
