# Live Translate — Agent Notes

Speech-to-speech live translation using Google Gemini Live (full-duplex
WebSocket) with short-lived ephemeral auth tokens.

## Runtime model

- Transcribe/translate model: **`gemini-3.5-live-translate-preview`**
  - Replaces the transcription-only `gemini-3.5-transcribe-live` (commit
    `d151b93`). Unlike `-transcribe-live`, this model supports the AUDIO
    response modality required by the simultaneous-translation path, and it
    also handles the transcription path over a real WebSocket.
  - `DEFAULT_MODEL` (`gemini-3.1-flash-live-preview`) is only used for the
    non-simultaneous / turn-based fallback path; do not confuse it with the
    translate model.
- The model string is **not hardcoded** in the frontend — the browser reads
  `model` from the token setup payload returned by the backend. So changing
  the backend default is the only code change needed for a new model.

## Config

- `backend/config.py`:
  - `DEFAULT_MODEL` (env `DEFAULT_MODEL`) — turn-based fallback model.
  - `TRANSLATE_MODEL` (env `TRANSLATE_MODEL`) — simultaneous translate model.
- `.env` is gitignored — never commit the API key. `TRANSLATE_MODEL` is NOT set
  in `.env`; the SDK default is used.

## SDK / environment (important)

- `requirements.txt` pins `google-genai>=1.20.0`. The project's own venv
  (`venv/`) has the correct version.
- **Tests run on the pyenv system Python**, NOT the repo venv. If tests fail
  with `AttributeError: ... has no attribute 'TranslationConfig'` (or similar
  missing Live/ephemeral-token types), the pyenv Python is missing the SDK.
  Fix: `pip install --upgrade "google-genai>=1.20.0"` in the active pyenv env.
  `google-genai 0.8.0` predates Live Connect / ephemeral tokens entirely.
- JS has **no test infra** (`node_modules`/`jest` not installed, no
  `package.json`). JS files are validated with `node --check`.

## Manual smoke check

```bash
GEMINI_API_KEY="$GEMINI_API_KEY" python3 -c "
import backend.gemini_live as g
r = g.TokenService().create(target_language='Spanish', translation_mode='simultaneous')
print(r['model'], r['setup']['model'], r['token'][:24])
"
```

## Favicon
- `frontend/favicon/gemini-logo.svg` is the source asset (Gemini-brand rounded-
gem mark, cyan→blue gradient, matching the header logo).
- `scripts/make_favicon.py` renders the SVG to `favicon.ico` (32x32) and
  `favicon-{32,128}.png` via `cairosvg`. Run it after editing the SVG:
  ```bash
  python3 scripts/make_favicon.py
  ```
- `backend/main.py` serves a dedicated `/favicon.ico` route from
  `frontend/favicon/` (PNG first, SVG fallback), so the browser no longer
  hits a 404 and fetches the wrong/default icon. `index.html` links it
  explicitly (`<link rel="icon" href="/favicon.ico">`). No runtime
  dependency on `cairosvg` — it is only a build-time tool.
## Tests

- Python: `python3 -m pytest tests/` (19 tests; all passing once SDK fixed). The `test_transcription.py` file errors on collection because the installed `google-genai` lacks `AudioTranscriptionConfigMode` — that is a pre-existing SDK-version mismatch, not a failing test.
- JS: `tests/js/protocol.test.js` — needs `npm install`/`jest` to run.
