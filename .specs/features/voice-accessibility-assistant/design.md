# Design — voice-accessibility-assistant

## Decision

We adopt an incremental, profile-based architecture inside the existing Neo.JS repository rather than creating a fork or introducing heavy desktop frameworks.

### Key Architectural Choices

1. **Profile Switch in `agent.py` (`NEO_PROFILE=dev|assistant`):**
   - Keeps a single codebase and deployment path.
   - `assistant` profile swaps `SYSTEM_PROMPT` to a voice-first `pt-BR` persona and replaces shell tools (`run_command`, `edit_file`) with curated safe tools (`email_tools` + read-only `view_file`/`list_directory` scoped to safe user directories).
   - A small `get_llm_config()` helper encapsulates `GEMINI_API_KEY`, `GROK_API_KEY`, and optional `NEO_LLM_BASE_URL` so BYOK works out-of-the-box today and managed tiers can be added later without modifying clients.

2. **Neural TTS with Zero-Cost Fallback (`tts_engine.py`):**
   - Primary engine: `edge-tts` (`pt-BR-FranciscaNeural`) — neural quality, free, no API key, fast on Windows and Linux.
   - Fallback engine: existing `gTTS` — guarantees continuity if `edge-tts` is unreachable.
   - Text sanitizer removes markdown (`*`, `_`, `#`, `` ` ``) and emojis before synthesis.

3. **Adapter Pattern for Email (`email_tools.py`):**
   - `EmailAccountAdapter` base interface: `list_messages`, `search_messages`, `read_message`, `send_message`.
   - `ImapSmtpAdapter`: stdlib `imaplib` + `smtplib` (handles Gmail with App Password and any standard IMAP/SMTP broker email).
   - `OutlookComAdapter` (Windows-only, lazy import `win32com.client`): talks directly to Classic Outlook Desktop using the user's already-authenticated Windows profile.
   - `OutlookGraphAdapter` (optional, OAuth Device Code): handles Outlook.com / Microsoft 365 / New Outlook where Microsoft disabled basic IMAP passwords.
   - Multi-account registry (`EmailManager`) loads accounts from gitignored `email_accounts.json` (or env vars) and enforces the `confirmed=True` guard on `send_email`.

4. **Offline Wake Word + Gemini Native Audio (`voice_listener.py`):**
   - **Wake word:** `Vosk` (`vosk-model-small-pt-0.3`, ~31 MB) runs locally in CPU with zero API cost and no custom model training required for `"ei neo"` / `"oi neo"`.
   - **STT + NLU:** Recorded user speech (trimmed by simple RMS silence detection) is sent to `agent.py` (`/transcribe` or `/voice-chat`) which uses the user's BYOK `gemini-2.5-flash` key for high-accuracy Portuguese + insurance domain understanding.
   - **Continuous Conversation:** After playing TTS audio locally, `voice_listener.py` enters a short `FOLLOWUP` listening window (~8s) so natural back-and-forth ("Qual conta?" → "Lê o Gmail primeiro") works without repeating `"Ei Neo"`.
   - **Interruptibility:** Global `Esc` listener cancels playback immediately.
   - Pure state-machine logic is separated from hardware audio I/O so all transitions are deterministically unit-testable in CI/Linux.

5. **Layperson-Friendly Windows Installer & Visual Onboarding Wizard (`scripts/Instalar-Neo.bat`, `scripts/install-windows.ps1`, `/setup` UI):**
   - Replace `/tmp/neo-bridge-audio` in `bridge.js` with `path.join(os.tmpdir(), 'neo-bridge-audio')`.
   - Double-click `scripts/Instalar-Neo.bat` invokes `scripts/install-windows.ps1` (with `-ExecutionPolicy Bypass`), which uses Windows built-in `winget` to install Python/Node if missing, sets up `venv`, downloads the ~31 MB `Vosk` `pt-BR` model, creates a Desktop shortcut (`Neo Assistente`) and silent Startup launcher (`pythonw.exe`), and opens the local Setup Wizard in Edge app mode (`msedge --app=http://127.0.0.1:5000/setup`).
   - `agent.py` serves a lightweight, zero-build, single-file HTML/CSS/JS accessible Setup Wizard (`setup_ui.html`) on `127.0.0.1:5000/setup` with high-contrast dark UI and large fonts, backed by `/setup/status`, `/setup/save`, `/setup/test-llm`, and `/setup/test-email` endpoints (masked secret responses only, localhost-only).
   - Future packaging option (v2): wrap `scripts/install-windows.ps1` + bundled project into a single `Neo-Setup.exe` via Inno Setup so users download just one `.exe`.

### Known Trade-offs & Tensions

- `edge-tts` relies on Microsoft's public Edge TTS endpoint (unofficial free service); keeping `gTTS` as automatic fallback mitigates breakage risk.
- `Vosk` requires a one-time ~31 MB model download on first setup; the Windows installer script should download and cache it locally in `./models/vosk-pt/`.
- `agent.py` currently uses `google-generativeai` (v0.8+); we keep it untouched in this feature to avoid unnecessary migration churn.

## Path ownership

| Path | Owner / Role | Change Type |
|---|---|---|
| `agent.py` | Profile selection (`NEO_PROFILE`), safe tool registration, `get_llm_config()`, optional `/voice` helper | Modify |
| `tts_engine.py` | `edge-tts` primary synthesis, text sanitization, `gTTS` fallback | Modify |
| `email_tools.py` | Multi-account `EmailManager`, `ImapSmtpAdapter`, `OutlookComAdapter`, `OutlookGraphAdapter`, send confirmation guard | Create |
| `voice_listener.py` | Wake-word loop (`Vosk`), conversational state machine, audio cues, `Esc` interrupt | Create |
| `bridge.js` | Cross-platform `os.tmpdir()` fix and platform-aware auto-healing message | Modify |
| `scripts/Instalar-Neo.bat` | Double-click Windows entry point for layperson installation (no terminal commands) | Create |
| `scripts/install-windows.ps1` | Automated runtime check (`winget`), venv, Vosk model download, Desktop shortcut & silent startup | Create |
| `scripts/start-assistant-silent.vbs` | Silent Windows Startup wrapper (`pythonw.exe`, no visible console window) | Create |
| `setup_ui.html` | Accessible, high-contrast local Setup Wizard served by `agent.py` at `/setup` | Create |
| `test/test_setup_wizard.py` | Unit tests for `/setup` endpoints (masked secrets, save, validation) | Create |
| `.gitignore` | Ignore `email_accounts.json` and `models/` | Modify |
| `.env.example` | Document `NEO_PROFILE`, `NEO_TTS_VOICE`, `NEO_TTS_RATE`, `NEO_FOLLOWUP_SECONDS` | Modify |
| `requirements.txt` | Add `edge-tts`; document optional Windows voice deps (`requirements-voice.txt`) | Modify / Create |
| `test/test_assistant_profile.py` | Unit tests for REQ-1, REQ-2, REQ-6 | Create |
| `test/test_email_tools.py` | Unit tests for REQ-3 (mock adapters + send confirmation guard) | Create |
| `test/test_voice_listener.py` | Unit tests for REQ-4 (state machine transitions + interrupt) | Create |
| `test/bridge-portable.test.js` | Unit test for REQ-5 (`os.tmpdir()` path resolution) | Create |
| `README.md` | Document Voice Accessibility Assistant roadmap & BYOK design | Modify |
