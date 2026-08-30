import logging
import datetime
from backend.config import settings

try:
    from google import genai
    from google.genai import types
    HAS_GENAI_SDK = True
except ImportError:
    HAS_GENAI_SDK = False

logger = logging.getLogger("gemini_live")
logger.setLevel(logging.INFO)

LANGUAGE_CODES = {
    "english": "en",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "chinese": "zh",
    "japanese": "ja",
    "korean": "ko",
    "portuguese": "pt",
    "italian": "it",
    "russian": "ru",
    "arabic": "ar",
    "hindi": "hi",
    "dutch": "nl",
    "polish": "pl",
    "turkish": "tr",
    "ukrainian": "uk",
    "vietnamese": "vi",
    "indonesian": "id",
    "thai": "th",
    "swedish": "sv",
    "en": "en",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "zh": "zh",
    "ja": "ja",
    "ko": "ko",
    "pt": "pt",
    "it": "it",
    "ru": "ru",
    "ar": "ar",
    "hi": "hi",
    "nl": "nl",
    "pl": "pl",
    "tr": "tr",
    "uk": "uk",
    "vi": "vi",
    "id": "id",
    "th": "th",
    "sv": "sv",
}

def resolve_language_code(value: str) -> str:
    if not value or not isinstance(value, str):
        return "en"
    val = str(value).strip().lower()
    if not val:
        return "en"
    if val in LANGUAGE_CODES:
        return LANGUAGE_CODES[val]

    normalized = val.replace("_", "-")
    parts = normalized.split("-")
    primary = parts[0]

    if primary in LANGUAGE_CODES:
        return normalized

    if len(primary) == 2 and primary.isalpha():
        return normalized

    return "en"

def build_interpreter_prompt(target_language: str = "English", source_language: str = None) -> str:
    cleaned_target = "".join(c for c in str(target_language)[:50] if c.isalnum() or c in " -_").strip() or "English"
    if source_language:
        cleaned_source = "".join(c for c in str(source_language)[:50] if c.isalnum() or c in " -_").strip()
        source_clause = f"from {cleaned_source} "
    else:
        source_clause = ""

    return (
        f"You are a real-time simultaneous live interpreter. "
        f"Continuously translate all incoming speech {source_clause}immediately into {cleaned_target} in short, real-time phrases (every 2-3 seconds of speech) without waiting for the speaker to pause or stop. "
        f"Always output the translated text transcript in {cleaned_target}. "
        f"When speaking the translation, speak clearly in {cleaned_target} with natural intonation. "
        f"Do not include commentary or extra conversational filler; output strictly the accurate translation."
    )

def build_translation_setup(
    target_language: str = "es",
    model: str = None,
    echo_target_language: bool = False
) -> dict:
    target_code = resolve_language_code(target_language)
    target_model = model or settings.translate_model
    if not target_model.startswith("models/"):
        target_model = f"models/{target_model}"

    return {
        "setup": {
            "model": target_model,
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "translationConfig": {
                    "targetLanguageCode": target_code,
                    "echoTargetLanguage": echo_target_language
                }
            },
            "inputAudioTranscription": {},
            "outputAudioTranscription": {}
        }
    }

def build_transcription_setup(
    source_language: str = None,
    model: str = None,
    transcription_mode: str = "verbatim",
    language_codes: list[str] = None,
    custom_vocabulary: list[str] = None,
    vad_disabled: bool = False,
) -> dict:
    """Build a Live Transcribe (speech-to-text) setup payload.

    Mirrors the documented Live Transcribe API
    (https://ai.google.dev/gemini-api/docs/live-api/live-transcribe):
    streaming ``response_modalities=["TEXT"]`` with ``input_audio_transcription``
    carrying language hints, an optional custom vocabulary, and a transcription
    ``mode`` (``verbatim`` or ``smart``).
    """
    target_model = model or settings.transcribe_model
    if not target_model.startswith("models/"):
        target_model = f"models/{target_model}"

    language_codes = list(language_codes) if language_codes else []
    custom_vocabulary = list(custom_vocabulary) if custom_vocabulary else []

    # An empty languageCodes list signals automatic language detection to the
    # model, so no special-casing is needed here.
    input_transcription = {
        "languageCodes": language_codes,
        "customVocabulary": custom_vocabulary,
        "mode": transcription_mode,
    }

    return {
        "setup": {
            "model": target_model,
            "generationConfig": {
                "responseModalities": ["TEXT"],
            },
            "inputAudioTranscription": input_transcription,
            "outputAudioTranscription": {},
        }
    }


def build_live_session_config(
    target_language: str = "English",
    mode: str = "audio",
    model: str = None,
    source_language: str = None,
    silence_duration_ms: int = 300,
    translation_mode: str = None,
    echo_target_language: bool = False,
    transcription_mode: str = "verbatim",
    language_codes: list[str] = None,
    custom_vocabulary: list[str] = None,
    vad_disabled: bool = False
) -> dict:
    tr_mode = translation_mode or settings.translation_mode
    if tr_mode == "simultaneous":
        target_model = model or settings.translate_model
        return build_translation_setup(
            target_language=target_language,
            model=target_model,
            echo_target_language=echo_target_language
        )

    if tr_mode == "transcribe":
        return build_transcription_setup(
            source_language=source_language,
            model=model,
            transcription_mode=transcription_mode,
            language_codes=language_codes,
            custom_vocabulary=custom_vocabulary,
            vad_disabled=vad_disabled
        )

    target_model = model or settings.default_model
    if not target_model.startswith("models/"):
        target_model = f"models/{target_model}"

    clamped_silence = max(500, min(2000, silence_duration_ms if silence_duration_ms is not None else 500))
    prompt = build_interpreter_prompt(target_language, source_language)

    setup_payload = {
        "setup": {
            "model": target_model,
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": "Puck"
                        }
                    }
                }
            },
            "systemInstruction": {
                "parts": [
                    {"text": prompt}
                ]
            },
            "realtimeInputConfig": {
                "activityHandling": "NO_INTERRUPTION",
                "automaticActivityDetection": {
                    "silenceDurationMs": clamped_silence,
                    "endOfSpeechSensitivity": "END_SENSITIVITY_HIGH",
                    "prefixPaddingMs": 300,
                    "turnCoverage": "TURN_INCLUDES_ONLY_ACTIVITY"
                }
            },
            "inputAudioTranscription": {},
            "outputAudioTranscription": {}
        }
    }
    return setup_payload

class TokenService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.gemini_api_key

    def create(
        self,
        target_language: str = "English",
        mode: str = "audio",
        model: str = None,
        source_language: str = None,
        silence_duration_ms: int = 300,
        translation_mode: str = None,
        echo_target_language: bool = False,
        transcription_mode: str = "verbatim",
        language_codes: list[str] = None,
        custom_vocabulary: list[str] = None,
        vad_disabled: bool = False
    ) -> dict:
        if not HAS_GENAI_SDK:
            raise ImportError("google-genai SDK is not installed.")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        tr_mode = translation_mode or settings.translation_mode
        target_code = resolve_language_code(target_language)

        client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(api_version="v1alpha")
        )

        if tr_mode == "simultaneous":
            target_model = model or settings.translate_model
            if not target_model.startswith("models/"):
                target_model = f"models/{target_model}"

            setup_wrapper = build_translation_setup(
                target_language=target_language,
                model=target_model,
                echo_target_language=echo_target_language
            )

            live_config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                translation_config=types.TranslationConfig(
                    target_language_code=target_code,
                    echo_target_language=echo_target_language
                ),
                input_audio_transcription=types.AudioTranscriptionConfig(),
                output_audio_transcription=types.AudioTranscriptionConfig()
            )
        elif tr_mode == "transcribe":
            target_model = model or settings.transcribe_model
            if not target_model.startswith("models/"):
                target_model = f"models/{target_model}"

            setup_wrapper = build_transcription_setup(
                source_language=source_language,
                model=target_model,
                transcription_mode=transcription_mode,
                language_codes=language_codes,
                custom_vocabulary=custom_vocabulary,
                vad_disabled=vad_disabled
            )

            # Live Transcribe streams text transcriptions, not spoken audio.
            live_config = types.LiveConnectConfig(
                response_modalities=["TEXT"],
                input_audio_transcription=types.AudioTranscriptionConfig(
                    language_codes=language_codes or [],
                    custom_vocabulary=custom_vocabulary or [],
                    mode=transcription_mode
                ),
                output_audio_transcription=types.AudioTranscriptionConfig(),
            )
            # Optional push-to-talk: disable server-side automatic VAD entirely.
            if vad_disabled:
                live_config.realtime_input_config = types.RealtimeInputConfig(
                    automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
                )
        else:
            target_model = model or settings.default_model
            if not target_model.startswith("models/"):
                target_model = f"models/{target_model}"

            clamped_silence = max(500, min(2000, silence_duration_ms if silence_duration_ms is not None else 500))

            setup_wrapper = build_live_session_config(
                target_language=target_language,
                mode=mode,
                model=target_model,
                source_language=source_language,
                silence_duration_ms=clamped_silence,
                translation_mode="turn_based"
            )

            prompt = build_interpreter_prompt(target_language, source_language)

            live_config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                    )
                ),
                system_instruction=types.Content(
                    parts=[types.Part.from_text(text=prompt)]
                ),
                realtime_input_config=types.RealtimeInputConfig(
                    activity_handling="NO_INTERRUPTION",
                    automatic_activity_detection=types.AutomaticActivityDetection(
                        silence_duration_ms=clamped_silence,
                        end_of_speech_sensitivity="END_SENSITIVITY_HIGH",
                        prefix_padding_ms=300
                    )
                ),
                input_audio_transcription=types.AudioTranscriptionConfig(),
                output_audio_transcription=types.AudioTranscriptionConfig()
            )

        now = datetime.datetime.now(datetime.timezone.utc)
        expire_time = now + datetime.timedelta(minutes=settings.token_ttl_minutes)
        new_session_expire_time = now + datetime.timedelta(minutes=settings.token_new_session_ttl_minutes)

        constraints = None
        if settings.lock_token_constraints:
            constraints = types.LiveConnectConstraints(
                model=target_model,
                config=live_config
            )

        config_kwargs = {
            "uses": settings.token_uses,
            "expire_time": expire_time,
            "new_session_expire_time": new_session_expire_time,
        }
        if constraints:
            config_kwargs["live_connect_constraints"] = constraints

        token_obj = client.auth_tokens.create(
            config=types.CreateAuthTokenConfig(**config_kwargs)
        )

        # Transcribe (speech-to-text) sessions connect over the transcribe live
        # WebSocket; translation and turn-based agent sessions use the constrained
        # endpoint.
        if tr_mode == "transcribe":
            ws_endpoint = f"{settings.get_transcribe_ws_endpoint()}?access_token={token_obj.name}"
        else:
            ws_endpoint = f"{settings.get_live_ws_endpoint()}?access_token={token_obj.name}"

        return {
            "token": token_obj.name,
            "expires_at": expire_time.isoformat(),
            "model": target_model,
            "ws_endpoint": ws_endpoint,
            "setup": setup_wrapper["setup"],
            "translation_mode": tr_mode,
            "transcription_mode": tr_mode if tr_mode == "transcribe" else None,
            "target_language_code": target_code
        }
