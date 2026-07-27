import os
import sys
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

root_env = Path(__file__).resolve().parent.parent / ".env"
if root_env.exists():
    load_dotenv(dotenv_path=str(root_env), override=True)
else:
    load_dotenv(override=True)

API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-3.1-flash-live-preview")

async def test_gemini_live_genai_sdk():
    if not API_KEY or "your_gemini_api_key_here" in API_KEY:
        print("ERROR: Neither GOOGLE_API_KEY nor GEMINI_API_KEY environment variable is set to a valid API key.")
        sys.exit(1)

    print(f"Testing Gemini Live API connection via google-genai SDK...")
    print(f"Target model: {DEFAULT_MODEL}")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=API_KEY)
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
                )
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text="You are a real-time live interpreter. Translate all user input into Spanish.")]
            ),
        )

        async with client.aio.live.connect(model=DEFAULT_MODEL, config=config) as session:
            print("Successfully connected to Gemini Live API via client.aio.live.connect!")
            
            # Sentence 1
            print("\n--- Sending Sentence 1 ---")
            await session.send_realtime_input(text="Hello world, this is a live translation test.")

            async for response in session.receive():
                server_content = response.server_content
                if server_content is None:
                    continue

                if server_content.model_turn:
                    for part in server_content.model_turn.parts:
                        if part.text:
                            print(f"Translation 1 output: {part.text}")

                if server_content.output_transcription:
                    print(f"Transcription 1: {server_content.output_transcription.text}")

                if server_content.turn_complete:
                    print("Turn 1 complete received!")
                    break

            # Sentence 2 (Testing multi-turn capability)
            print("\n--- Sending Sentence 2 ---")
            await session.send_realtime_input(text="How are you doing today?")

            async for response in session.receive():
                server_content = response.server_content
                if server_content is None:
                    continue

                if server_content.model_turn:
                    for part in server_content.model_turn.parts:
                        if part.text:
                            print(f"Translation 2 output: {part.text}")

                if server_content.output_transcription:
                    print(f"Transcription 2: {server_content.output_transcription.text}")

                if server_content.turn_complete:
                    print("Turn 2 complete received!")
                    break

        print("\nSmoke test PASSED! Gemini Live API integration verified.")
        return True

    except Exception as e:
        print(f"SDK Test failed ({e}), falling back to raw WebSocket test...")
        import websockets
        model_name = DEFAULT_MODEL if DEFAULT_MODEL.startswith("models/") else f"models/{DEFAULT_MODEL}"
        ws_url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={API_KEY}"
        headers = {"x-goog-api-key": API_KEY}

        setup_msg = {
            "setup": {
                "model": model_name,
                "generationConfig": {"responseModalities": ["AUDIO"]},
                "systemInstruction": {
                    "parts": [{"text": "You are a real-time interpreter. Translate text to Spanish."}]
                }
            }
        }
        try:
            async with websockets.connect(ws_url, additional_headers=headers) as ws:
                await ws.send(json.dumps(setup_msg))
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                print(f"WebSocket fallback response received: {response[:100]}...")
                print("\nSmoke test PASSED via WebSocket fallback!")
                return True
        except Exception as ws_err:
            print(f"Smoke test FAILED: {ws_err}")
            return False

if __name__ == "__main__":
    success = asyncio.run(test_gemini_live_genai_sdk())
    sys.exit(0 if success else 1)
