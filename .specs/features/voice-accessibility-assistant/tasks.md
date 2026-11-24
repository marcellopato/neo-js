# Tasks — voice-accessibility-assistant

## TASK-001: Assistant Profile, Safe Tooling & BYOK Provider Config

- **Acceptance criteria:**
  - `NEO_PROFILE=assistant` loads the voice-first `pt-BR` system prompt and excludes `run_command` and `edit_file` from `NeoAgent` tools.
  - `NEO_PROFILE=dev` (default) preserves all existing developer tools unchanged.
  - `get_llm_config()` centralizes `GEMINI_API_KEY`, `GROK_API_KEY`, and optional `NEO_LLM_BASE_URL` for BYOK and future managed routing.
- **Review boundary:** `agent.py`, `.env.example`, `test/test_assistant_profile.py`
- **Slice type:** Vertical (backend profile + safety invariant + config seam)
- **Independently verifiable:** Yes (`python3 -m unittest test/test_assistant_profile.py`)
- **Public seam:** `NEO_PROFILE` env var, `get_tools_for_profile(profile)`, `get_system_prompt(profile)`, `get_llm_config()`
- **Requirement anchors:** REQ-1, REQ-6
- **Dependencies:** None
- **Horizontal-slice justification:** N/A (vertical slice)
- **Expand-contract strategy:** Additive default-safe behavior (`NEO_PROFILE` defaults to `dev`).

### TDD baseline
- Write failing unit tests in `test/test_assistant_profile.py` asserting that `get_tools_for_profile("assistant")` excludes `run_command`/`edit_file`, `get_tools_for_profile("dev")` includes them, and `get_llm_config()` resolves BYOK env vars.
- Implement changes in `agent.py` until all tests pass.

---

## TASK-002: Neural PT-BR TTS Upgrade (`edge-tts` + `gTTS` Fallback) & Windows Bridge Portability

- **Acceptance criteria:**
  - `tts_engine.py` strips markdown/emojis, synthesizes audio via `edge-tts` (`NEO_TTS_VOICE`, `NEO_TTS_RATE`), and falls back to `gTTS` on error.
  - `bridge.js` uses `path.join(os.tmpdir(), 'neo-bridge-audio')` instead of hardcoded `/tmp/neo-bridge-audio` and adapts auto-healing restart hint for Windows.
- **Review boundary:** `tts_engine.py`, `bridge.js`, `requirements.txt`, `test/test_assistant_profile.py`, `test/bridge-portable.test.js`
- **Slice type:** Vertical (TTS engine + Windows bridge fix)
- **Independently verifiable:** Yes (`python3 -m unittest test/test_assistant_profile.py` and `npm test`)
- **Public seam:** `tts_engine.generate_audio(text)`, `tts_engine.sanitize_for_speech(text)`, `bridge.js` `TEMP_DIR`
- **Requirement anchors:** REQ-2, REQ-5
- **Dependencies:** None
- **Horizontal-slice justification:** N/A (vertical slice)
- **Expand-contract strategy:** `edge-tts` is primary with automatic fallback to existing `gTTS`; `os.tmpdir()` is drop-in compatible on Linux/macOS/Windows.

### TDD baseline
- Write failing tests for `sanitize_for_speech`, `edge-tts` invocation, `gTTS` fallback on exception, and `bridge.js` cross-platform temp dir resolution.
- Implement changes and verify both Python `unittest` and `npm test` pass.

---

## TASK-003: Multi-Account Email Tools (Gmail & Outlook) with Send Confirmation Guard

- **Acceptance criteria:**
  - `email_tools.py` implements `EmailManager` with `ImapSmtpAdapter` (Gmail App Password / generic IMAP), `OutlookComAdapter` (Windows Classic Outlook), and `OutlookGraphAdapter` (Outlook Web / Microsoft 365).
  - `list_emails`, `search_emails`, and `read_email` work across one or all accounts and return clean plain text suitable for voice summarization.
  - `send_email(..., confirmed=False)` blocks sending and returns a confirmation prompt; `send_email(..., confirmed=True)` sends via the selected adapter.
  - Tools are registered in `agent.py` for `NEO_PROFILE=assistant`; `email_accounts.json` is added to `.gitignore`.
- **Review boundary:** `email_tools.py`, `agent.py`, `.gitignore`, `test/test_email_tools.py`
- **Slice type:** Vertical (email adapters + tool registration + security guard)
- **Independently verifiable:** Yes (`python3 -m unittest test/test_email_tools.py`)
- **Public seam:** `list_emails`, `search_emails`, `read_email`, `send_email`, `EmailAccountAdapter`
- **Requirement anchors:** REQ-3, REQ-1
- **Dependencies:** TASK-001
- **Horizontal-slice justification:** N/A (vertical slice)
- **Expand-contract strategy:** New module with lazy OS-specific imports (`win32com.client` imported only on Windows when configured).

### TDD baseline
- Write failing unit tests in `test/test_email_tools.py` using mock adapters for Gmail and Outlook covering multi-account listing, HTML-to-text cleaning, search, and the `confirmed=False` vs `confirmed=True` send guard.
- Implement `email_tools.py` and wire into `agent.py` until all tests pass.

---

## TASK-004: Windows Hands-Free Wake Word & Conversational Voice Client (`voice_listener.py`)

- **Acceptance criteria:**
  - `voice_listener.py` implements a testable `VoiceSessionStateMachine` (`IDLE -> LISTENING -> PROCESSING -> SPEAKING -> FOLLOWUP -> IDLE`, plus immediate `SPEAKING -> IDLE` on `Esc` interrupt).
  - Offline wake-word detector using `Vosk` (`pt-BR` small model) triggers on `"ei neo"` / `"oi neo"`.
  - Audio cues (beeps) signal listening start, processing, and errors.
  - Recorded speech is sent to `agent.py` for transcription + response, spoken via `tts_engine.py`, and followed by an automatic follow-up listening window (`NEO_FOLLOWUP_SECONDS`).
- **Review boundary:** `voice_listener.py`, `requirements-voice.txt`, `.gitignore`, `test/test_voice_listener.py`
- **Slice type:** Vertical (voice client + state machine + audio loop)
- **Independently verifiable:** Yes (`python3 -m unittest test/test_voice_listener.py`)
- **Public seam:** `VoiceSessionStateMachine`, `voice_listener.py` CLI entry point, `NEO_FOLLOWUP_SECONDS`
- **Requirement anchors:** REQ-4, REQ-6
- **Dependencies:** TASK-001, TASK-002
- **Horizontal-slice justification:** N/A (vertical slice)
- **Expand-contract strategy:** Standalone client talking to existing `agent.py` HTTP API; does not disturb `neo-cli.py` or `daemon/`.

### TDD baseline
- Write failing unit tests in `test/test_voice_listener.py` verifying all state transitions, wake-phrase matching, follow-up window timeout back to `IDLE`, and immediate `Esc` playback cancellation.
- Implement `voice_listener.py` and verify tests pass.

---

## TASK-005: Layperson-Friendly Windows One-Click Installer & Accessible Setup Wizard

- **Acceptance criteria:**
  - `agent.py` serves `setup_ui.html` at `GET /setup` (high-contrast dark theme, large fonts, PT-BR guided steps for Gemini BYOK key, Gmail/Outlook accounts, voice/mic test, and optional WhatsApp QR) plus `GET /setup/status`, `POST /setup/save`, `POST /setup/test-llm`, and `POST /setup/test-email`.
  - `GET /setup/status` returns configured flags/masked hints only — never plaintext API keys or email passwords (`INV-3`).
  - `scripts/Instalar-Neo.bat` + `scripts/install-windows.ps1` handle double-click installation on Windows: check/install Python (and optional Node.js) via `winget`, create `venv`, install requirements, download `vosk-model-small-pt-0.3`, create Desktop shortcut + silent Startup launcher (`scripts/start-assistant-silent.vbs` via `pythonw.exe`), and open `http://127.0.0.1:5000/setup` in Edge app mode.
  - `README.md` documents the one-click Windows installation and Setup Wizard clearly for non-technical users.
- **Review boundary:** `setup_ui.html`, `agent.py` (`/setup*` routes), `scripts/Instalar-Neo.bat`, `scripts/install-windows.ps1`, `scripts/start-assistant-silent.vbs`, `README.md`, `.env.example`, `test/test_setup_wizard.py`
- **Slice type:** Vertical (installer + visual onboarding UI + setup API)
- **Independently verifiable:** Yes (`python3 -m unittest test/test_setup_wizard.py` + PowerShell/batch syntax check)
- **Public seam:** `GET /setup`, `GET /setup/status`, `POST /setup/save`, `POST /setup/test-llm`, `POST /setup/test-email`, `scripts/Instalar-Neo.bat`
- **Requirement anchors:** REQ-7, REQ-6
- **Dependencies:** TASK-001, TASK-002, TASK-003, TASK-004
- **Horizontal-slice justification:** N/A (vertical slice)
- **Expand-contract strategy:** Additive Windows scripts and `/setup` routes; existing Linux `start.sh` and `install.js` remain intact.

### TDD baseline
- Write failing unit tests in `test/test_setup_wizard.py` verifying that `GET /setup` returns HTTP 200 HTML, `POST /setup/save` persists `.env` / `email_accounts.json` to temp paths, and `GET /setup/status` masks all secrets (`INV-3`).
- Implement `/setup` routes, `setup_ui.html`, and Windows installer scripts until all tests pass.
