# Context — voice-accessibility-assistant

Work intent: feature
Lifecycle: draft

## Background

Neo.JS currently operates as a developer-focused local assistant (`agent.py`, `bridge.js`, `tts_engine.py`, `neo-cli.py`, and Linux Go+Wails `daemon/`). Its default `SYSTEM_PROMPT` targets software engineering workflows (PHP, Node.js, Python, Docker) and exposes shell execution (`run_command`).

This feature upgrades Neo.JS with an accessible, voice-first **Assistant Profile** designed primarily for low-vision Windows users (initial real-world persona: an insurance broker with keratoconus and 20% vision in one eye) while remaining a first-class, **100% BYOK (Bring Your Own Key)** free upgrade to Neo.JS.

## Problem Statement

A low-vision user on Windows cannot comfortably navigate visual email clients (Gmail, Outlook) or type CLI commands. They need to:
- Activate Neo hands-free on Windows via a wake word (`"Ei Neo"`) or via WhatsApp voice messages (PTT).
- Converse in natural Brazilian Portuguese (`pt-BR`), where Neo proactively asks clarifying questions and listens for spoken replies without requiring rigid command syntax.
- Read, search, summarize, and reply to emails across **both Gmail and Outlook** safely by voice.
- Run Neo locally on Windows at zero subscription cost using their own LLM API key (BYOK), while keeping the provider boundary clean for optional managed/paid tiers in the future.

## Existing Repository Evidence

- `agent.py`: FastAPI backend (`:5000`) using `google-generativeai` (`gemini-2.5-flash`), tool-calling (`run_command`, `view_file`, `edit_file`, `list_directory`), local RAG memory (`qdrant-client[fastembed]`), and `/chat`, `/chat/stream`, `/transcribe` endpoints.
- `tts_engine.py`: Modular PT-BR TTS currently backed by `gTTS`, writing `.ogg` files to `audio_cache/`.
- `bridge.js`: WhatsApp Web bridge (`whatsapp-web.js`, `:3303`) supporting PTT voice transcription and audio replies; currently hardcodes Linux-only `TEMP_DIR = '/tmp/neo-bridge-audio'` and `./start.sh` in auto-healing prompts.
- `.env.example`: Configures BYOK keys (`GEMINI_API_KEY`, optional `GROK_API_KEY`) and service tokens.
- `test/`: Uses Node's built-in `node --test` (`npm test`); Python tests can run with stdlib `unittest` without extra test runner dependencies.

## Constraints & Non-Goals

- **BYOK & Free Core:** All voice activation, TTS, email access, and LLM inference must work with zero paid third-party subscriptions beyond the user's own LLM key (e.g., Gemini API free/billed tier).
- **No Breaking Changes to Dev Mode:** Default `NEO_PROFILE=dev` must preserve existing developer workflows and tools.
- **No Unattended Email Sending:** Neo must never send or reply to an email without explicit user confirmation in the conversation.
- **Out of Scope (v1):** Billing/subscription backend, custom wake-word model training, full screen-reader replacement for arbitrary Windows apps, and automated OAuth app registration portals.

## Open Questions

1. **Outlook Flavor:** Does the target Windows PC use Classic Outlook Desktop (supports zero-auth local COM via `pywin32`), New Outlook / Outlook Web / Microsoft 365 (requires Microsoft Graph Device Code OAuth), or both? *(Design supports both adapters behind a single interface; prioritize Classic COM + Graph Device Code).*
2. **Audio Playback Library on Windows:** Confirm whether `pygame` or `sounddevice` + `soundfile` installs cleanly on the target Python 3.10+ Windows environment without C build tools.
