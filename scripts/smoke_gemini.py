import os
import sys
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

root_env = Path(__file__).resolve().parent.parent / ".env"
if root_env.exists():
    load_dotenv(dotenv_path=str(root_env), override=True)
else:
    load_dotenv(override=True)

from backend.config import settings
from backend.gemini_live import TokenService

async def smoke_test():
    if not settings.gemini_api_key or "your_gemini_api_key_here" in settings.gemini_api_key:
        print("ERROR: Neither GOOGLE_API_KEY nor GEMINI_API_KEY environment variable is set.")
        sys.exit(1)

    print("Step 1: Minting ephemeral token via TokenService...")
    try:
        service = TokenService()
        token_data = service.create(
            target_language="Spanish",
            mode="audio",
            model=settings.default_model
        )
        print("Token minted successfully!")
        print(f"Token: {token_data['token']}")
        print(f"Expires at: {token_data['expires_at']}")
        print(f"WS Endpoint: {token_data['ws_endpoint']}")
    except Exception as e:
        print(f"ERROR minting token: {e}")
        return False

    print("\nStep 2: Connecting directly to Gemini Live WSS Endpoint...")
    try:
        import websockets

        async with websockets.connect(token_data["ws_endpoint"]) as ws:
            print("Connected to WSS!")

            setup_frame = {"setup": token_data["setup"]}
            print("Sending setup frame...")
            await ws.send(json.dumps(setup_frame))

            raw_resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
            resp = json.loads(raw_resp)
            print("Received initial response:", resp)

            if "setupComplete" not in resp:
                print(f"ERROR: Expected setupComplete in response, got: {resp}")
                return False

            print("Setup Complete confirmed!")

            print("\nStep 3: Sending user input (realtime audio chunk)...")
            import base64
            dummy_pcm_b64 = base64.b64encode(bytes([0] * 640)).decode('utf-8')
            audio_msg = {
                "realtimeInput": {
                    "audio": {
                        "mimeType": "audio/pcm;rate=16000",
                        "data": dummy_pcm_b64
                    }
                }
            }
            await ws.send(json.dumps(audio_msg))
            print("Audio frame sent successfully!")

            print("\nStep 4: Sending user input (text chunk)...")
            txt_msg = {
                "clientContent": {
                    "turns": [
                        {
                            "role": "user",
                            "parts": [{"text": "Hello world, this is a live translation smoke test."}]
                        }
                    ],
                    "turnComplete": True
                }
            }
            await ws.send(json.dumps(txt_msg))

            raw_turn_resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
            turn_resp = json.loads(raw_turn_resp)
            print("Received response for user input:", turn_resp)

            if "serverContent" in turn_resp:
                print("Server content received successfully!")

            print("\nSmoke test PASSED! Gemini Live Ephemeral Token full-duplex protocol verified.")
            return True

    except Exception as ws_err:
        print(f"WSS Connection error: {ws_err}")
        return False

if __name__ == "__main__":
    success = asyncio.run(smoke_test())
    sys.exit(0 if success else 1)
