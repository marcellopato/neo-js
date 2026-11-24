# Specification — voice-accessibility-assistant

Work intent: feature

## Requirement REQ-1: Configurable Assistant Profile (`NEO_PROFILE`)

`agent.py` shall support a `NEO_PROFILE` environment variable with values `dev` (default, preserving current behavior) and `assistant`.

When `NEO_PROFILE=assistant`:
- Neo shall use a voice-first, natural-language `SYSTEM_PROMPT` in `pt-BR` optimized for audio playback: concise sentences, no markdown formatting (`*`, `#`, backticks), no emojis, summarize long content first and ask before reading full details.
- Neo shall ask clarifying questions naturally when an instruction is ambiguous (e.g., multiple email accounts configured) and wait for the user's spoken reply.
- **INV-1 (Safety invariant):** In `assistant` profile, `run_command` and `edit_file` shall NOT be registered in the model's tool list. Only explicit, safe assistant tools (email tools and read-only document reading) shall be exposed.

## Requirement REQ-2: Neural PT-BR Speech Synthesis (`tts_engine.py`)

`tts_engine.py` shall upgrade speech synthesis to use `edge-tts` (Microsoft neural voices, free, no API key) with a configurable voice via `NEO_TTS_VOICE` (default `pt-BR-FranciscaNeural`) and speaking rate via `NEO_TTS_RATE` (default `+0%`).

- Before synthesis, `tts_engine.py` shall strip residual markdown/formatting characters so spoken output sounds natural.
- If `edge-tts` fails (e.g., network/service error), `tts_engine.py` shall fall back gracefully to the existing `gTTS` engine without crashing the request.
- Generated audio files shall continue respecting `MAX_AUDIO_FILES` cleanup bounds.

## Requirement REQ-3: Multi-Account Email Tools (Gmail & Outlook)

A dedicated `email_tools.py` module shall expose safe, conversational email tools registered in `agent.py` when `NEO_PROFILE=assistant` (and optionally enabled via `NEO_EMAIL_ENABLED=true` in `dev`):

- `list_emails(account: str = "all", unread_only: bool = True, limit: int = 5)` — returns sender, subject, date, account label, and message ID.
- `search_emails(query: str, account: str = "all", limit: int = 5)` — searches by sender, subject, or keyword.
- `read_email(email_id: str, account: str)` — returns clean plain-text body (HTML stripped, truncated safely for voice summarization).
- `draft_email_reply(email_id: str, account: str, body: str)` / `send_email(account: str, to: str, subject: str, body: str, confirmed: bool = False)` — **INV-2 (Confirmation invariant):** `send_email` shall refuse to transmit and return a confirmation prompt unless `confirmed=True` after the user explicitly confirmed the recipient, subject, and spoken preview.

Supported account backends:
- **Gmail:** `imaplib` + `smtplib` using App Password (zero external SDK required).
- **Outlook:** Adapter supporting **Classic Outlook Desktop** on Windows (`win32com.client` / COM, reusing the already signed-in desktop session) and **Outlook / Microsoft 365** via IMAP/SMTP or Microsoft Graph Device Code OAuth.
- Account credentials shall be loaded from a gitignored local config (`email_accounts.json` or `.env`) and never logged or echoed in tool responses.

## Requirement REQ-4: Hands-Free Wake Word & Continuous Conversation on Windows (`voice_listener.py`)

A local Windows-compatible voice client (`voice_listener.py`) shall enable eyes-free, hands-free interaction with `agent.py`:

- **Wake Word:** Listens locally and offline using `Vosk` (`vosk-model-small-pt-0.3`, zero API cost) for configurable wake phrases (default: `"ei neo"`, `"oi neo"`).
- **Audio Feedback:** Plays distinct short audio cues (beeps) for: *listening started*, *processing*, and *error/timeout*, so the user never needs to look at the screen.
- **Natural-Language Capture:** After wake word detection, records microphone input until silence is detected (energy/VAD timeout), sends the audio to `agent.py` (`/transcribe` or native Gemini audio input), and plays the TTS response aloud.
- **Follow-Up Window (Conversational Turn):** When Neo finishes speaking a question or response, `voice_listener.py` shall automatically reopen the microphone for a configurable follow-up window (`NEO_FOLLOWUP_SECONDS`, default `8` seconds) so the user can answer directly without repeating `"Ei Neo"`. Silence returns the listener to wake-word standby.
- **Instant Interrupt:** Pressing `Esc` (or a configurable hotkey) shall immediately stop active TTS playback.

## Requirement REQ-5: Cross-Platform WhatsApp Voice Bridge (`bridge.js`)

`bridge.js` shall work reliably on Windows as well as Linux/macOS:

- Replace hardcoded `/tmp/neo-bridge-audio` with `path.join(os.tmpdir(), 'neo-bridge-audio')`.
- Make auto-healing restart instructions platform-aware (avoid hardcoding `./start.sh` on Windows).
- Preserve existing WhatsApp PTT transcription and TTS audio reply flow so the user can also converse with Neo by voice via WhatsApp when away from the PC.

## Requirement REQ-6: BYOK-First & Future Managed-Provider Seam

- All features (REQ-1 through REQ-5) shall run 100% free using the user's own `GEMINI_API_KEY` (and optional `GROK_API_KEY` fallback) with no paid third-party subscriptions required.
- LLM configuration in `agent.py` shall read provider credentials and optional custom base URL (`NEO_LLM_BASE_URL`) through a clean factory/config helper so future managed/paid plans can route through an authenticated gateway without changing voice, email, or WhatsApp clients.

## Requirement REQ-7: Layperson-Friendly Windows Installation & Visual Setup Wizard

Installation and initial configuration on Windows shall require **zero command-line knowledge** (usable directly by a non-technical user or quickly over AnyDesk):

- **One-Click Windows Installer (`scripts/Instalar-Neo.bat` + `scripts/install-windows.ps1`):**
  - Runs via double-click with clear Portuguese progress messages (no manual `git`, `pip`, or `npm` commands).
  - Automatically checks for Python 3.10+ (and Node.js 18+ if WhatsApp bridge is enabled) and installs missing runtimes via Windows native `winget` when available, or opens the official download link with clear instructions if `winget` is unavailable.
  - Automatically creates the virtual environment, installs dependencies, downloads/extracts the offline `Vosk` `pt-BR` wake-word model into `./models/vosk-pt/`, creates a Desktop shortcut (`Neo Assistente`), and registers silent auto-start at Windows login (`pythonw.exe`, no visible terminal window).
- **Accessible Visual Setup Wizard (`/setup` served by `agent.py`, opened in Edge `--app` mode):**
  - High-contrast dark theme with large typography (designed for low-vision/keratoconus readability) and optional spoken guidance.
  - **Step 1 (BYOK Key):** Direct link to Google AI Studio, paste field for `GEMINI_API_KEY`, and live **"Testar conexão"** button.
  - **Step 2 (Email Accounts):** One-click detection for Classic Outlook Desktop on Windows, plus simple guided forms for Gmail (App Password) and Outlook/Microsoft 365, each with a live **"Testar e-mail"** button. Saves credentials safely to `.env` / gitignored `email_accounts.json`.
  - **Step 3 (Voice & Mic Check):** Live **"Ouvir a voz do Neo"** and microphone test buttons.
  - **Step 4 (WhatsApp — Optional):** Displays the WhatsApp QR code visually in the browser (no ASCII terminal QR) or lets the user skip.
  - **Security invariant (`INV-3`):** `/setup` endpoints shall bind exclusively to `127.0.0.1` (localhost) and never expose stored secrets back in plaintext GET responses (return masked/configured status only).

## Acceptance criteria

- **AC-1 (Profile isolation — REQ-1):** Starting `agent.py` with `NEO_PROFILE=assistant` exposes email tools and excludes `run_command` and `edit_file` (verified by unit test inspecting registered tool names). Starting with `NEO_PROFILE=dev` (or unset) preserves existing tools.
- **AC-2 (Voice-friendly output — REQ-1, REQ-2):** `tts_engine.generate_audio("Olá *mundo* 🚀")` strips markdown/emoji artifacts, invokes `edge-tts` with `pt-BR-FranciscaNeural`, and falls back to `gTTS` when `edge-tts` raises an exception (verified by unit tests with mocks).
- **AC-3 (Multi-account email & send guard — REQ-3):** `email_tools.list_emails(account="all")` aggregates results across configured Gmail and Outlook mock adapters; `send_email(..., confirmed=False)` never calls the transport and returns a confirmation prompt; `send_email(..., confirmed=True)` invokes the transport once (verified by unit tests).
- **AC-4 (Wake word & follow-up state machine — REQ-4):** `voice_listener.py` state machine transitions `IDLE -> LISTENING -> PROCESSING -> SPEAKING -> FOLLOWUP -> IDLE` on silence, and `SPEAKING -> IDLE` immediately on interrupt signal (verified by unit tests without requiring physical microphone hardware).
- **AC-5 (Windows bridge portability — REQ-5):** `bridge.js` uses `os.tmpdir()` for temporary audio storage and passes `node --test` checks on path resolution.
- **AC-6 (BYOK, layperson setup & no secrets — REQ-6, REQ-7):** All unit tests pass with a dummy `GEMINI_API_KEY` and zero external paid services; `email_accounts.json` is listed in `.gitignore`; `/setup` API endpoints save config, validate connections, and return masked status without leaking plaintext keys; `scripts/Instalar-Neo.bat` + `scripts/install-windows.ps1` bootstrap runtimes, venv, Vosk model, Desktop shortcut, and silent startup; `README.md` documents the Voice Accessibility Assistant setup accurately.
