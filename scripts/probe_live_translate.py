import os
import sys
import json
import asyncio
import datetime
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

root_env = Path(__file__).resolve().parent.parent / ".env"
if root_env.exists():
    load_dotenv(dotenv_path=str(root_env), override=False)
else:
    load_dotenv(override=False)

from backend.config import settings

async def probe_live_translate():
    api_key = settings.gemini_api_key
    if not api_key or "your_gemini_api_key_here" in api_key:
        print("ERROR: Neither GOOGLE_API_KEY nor GEMINI_API_KEY environment variable is set.")
        sys.exit(1)

    print("Step 1: Testing ephemeral token creation for live-translate model via google-genai SDK...")
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version="v1alpha")
        )

        model_name = getattr(settings, "translate_model", "gemini-3.5-live-translate-preview")
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        # Build LiveConnectConfig with translation_config
        live_config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            translation_config=types.TranslationConfig(
                target_language_code="es",
                echo_target_language=False
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig()
        )

        now = datetime.datetime.now(datetime.timezone.utc)
        expire_time = now + datetime.timedelta(minutes=15)
        new_session_expire_time = now + datetime.timedelta(minutes=10)

        constraints = types.LiveConnectConstraints(
            model=model_name,
            config=live_config
        )

        print(f"Creating Auth Token for model={model_name} with translation_config...")
        auth_token = client.auth_tokens.create(
            config=types.CreateAuthTokenConfig(
                uses=1,
                expire_time=expire_time,
                new_session_expire_time=new_session_expire_time,
                live_connect_constraints=constraints
            )
        )
        print("Auth Token created successfully!")
        print(f"Token Name: {auth_token.name}")

        ws_endpoint = f"{settings.get_live_ws_endpoint()}?access_token={auth_token.name}"

        # Setup frame for simultaneous live translate setup
        setup_payload = {
            "setup": {
                "model": model_name,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "translationConfig": {
                        "targetLanguageCode": "es",
                        "echoTargetLanguage": False
                    }
                },
                "inputAudioTranscription": {},
                "outputAudioTranscription": {}
            }
        }

        print("\nStep 2: Connecting to Live Translate WebSocket endpoint using token...")
        import websockets

        async with websockets.connect(ws_endpoint) as ws:
            print("Connected to WSS!")
            print("Sending setup frame:", json.dumps(setup_payload, indent=2))
            await ws.send(json.dumps(setup_payload))

            raw_resp = await asyncio.wait_for(ws.recv(), timeout=10.0)
            resp = json.loads(raw_resp)
            print("Received initial response:", resp)

            if "setupComplete" in resp:
                print("Setup Complete confirmed!")
                print("\nProbe PASSED: live-translate model and translationConfig work as expected!")
                return True
            else:
                print(f"Unexpected response frame: {resp}")
                return False

    except Exception as e:
        print(f"Probe exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(probe_live_translate())
    sys.exit(0 if success else 1)
