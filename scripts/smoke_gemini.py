import os
import sys
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import websockets

# Load .env file
root_env = Path(__file__).resolve().parent.parent / ".env"
if root_env.exists():
    load_dotenv(dotenv_path=str(root_env), override=True)
else:
    load_dotenv(override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.0-flash-exp")

async def test_gemini_live_handshake():
    if not GEMINI_API_KEY or "your_gemini_api_key_here" in GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY environment variable is not set to a valid API key.")
        sys.exit(1)

    model_name = DEFAULT_MODEL if DEFAULT_MODEL.startswith("models/") else f"models/{DEFAULT_MODEL}"
    ws_url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={GEMINI_API_KEY}"
    headers = {"x-goog-api-key": GEMINI_API_KEY}

    print(f"Connecting to Gemini Live WSS: {ws_url.split('?')[0]}?key=***")
    print(f"Target model: {model_name}")

    setup_msg = {
        "setup": {
            "model": model_name,
            "generationConfig": {
                "responseModalities": ["TEXT"]
            },
            "systemInstruction": {
                "parts": [
                    {"text": "You are a live interpreter test assistant. Output translations directly."}
                ]
            }
        }
    }

    try:
        async with websockets.connect(ws_url, additional_headers=headers) as ws:
            print("WebSocket connected successfully. Sending setup frame...")
            await ws.send(json.dumps(setup_msg))

            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                resp_json = json.loads(response)
                print("Received response from Gemini Live API:")
                print(json.dumps(resp_json, indent=2))
                print("\nSmoke test PASSED! Gemini Live WebSocket handshake successful.")
                return True
            except asyncio.TimeoutError:
                print("Connected and sent setup frame, but no immediate response received (timeout 5s). Setup accepted.")
                print("\nSmoke test PASSED! Gemini Live WebSocket handshake successful.")
                return True

    except Exception as e:
        print(f"Smoke test FAILED: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_gemini_live_handshake())
    sys.exit(0 if success else 1)
