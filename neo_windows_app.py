"""Unified Windows entry point for NeoAssistente.exe (PyInstaller bundle)."""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser

APP_DIR = (
    os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)
os.chdir(APP_DIR)

# In PyInstaller --noconsole mode on Windows, sys.stdout/sys.stderr are None.
# Redirect them to a local log file so print() and uvicorn never crash.
if sys.stdout is None or sys.stderr is None:
    log_path = os.path.join(APP_DIR, "neo-assistant.log")
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = log_file
    sys.stderr = log_file

import uvicorn
import agent
import email_tools
import memory
import tts_engine
import voice_listener

SETUP_URL = "http://127.0.0.1:5000/setup"


def _is_port_open(port: int = 5000) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def open_setup_window() -> None:
    """Open the accessible Setup Wizard in Edge app mode (or default browser fallback)."""
    edge_path = shutil.which("msedge")
    if not edge_path and sys.platform == "win32":
        for candidate in (
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ):
            if os.path.exists(candidate):
                edge_path = candidate
                break

    if edge_path:
        try:
            subprocess.Popen([edge_path, f"--app={SETUP_URL}"])
            return
        except Exception:
            pass
    webbrowser.open(SETUP_URL)


def _ensure_initial_env() -> bool:
    """Create default .env if missing. Returns True if GEMINI_API_KEY is already configured."""
    env_path = os.path.join(APP_DIR, ".env")
    if not os.path.exists(env_path):
        token = secrets.token_hex(16)
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(
                "NEO_PROFILE=assistant\n"
                "NEO_VOICE_ENABLED=true\n"
                "NEO_TTS_VOICE=pt-BR-FranciscaNeural\n"
                "NEO_FOLLOWUP_SECONDS=8\n"
                f"INTERNAL_API_KEY={token}\n"
            )
        return False

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("GEMINI_API_KEY="):
                val = line.strip().split("=", 1)[1].strip()
                if val and val != "sua_completa_api_key_aqui":
                    return True
    return False


def main() -> None:
    force_setup = "--setup" in sys.argv

    # Single-instance check: if backend is already running on :5000, just open Setup UI and exit.
    if _is_port_open(5000):
        print("[JarvisApp] Jarvis já está rodando em segundo plano. Abrindo tela de configuração...")
        open_setup_window()
        return

    has_gemini_key = _ensure_initial_env()

    def _run_backend():
        uvicorn.run(agent.app, host="127.0.0.1", port=5000, log_config=None)

    server_thread = threading.Thread(target=_run_backend, daemon=True)
    server_thread.start()

    # Wait up to 8s for backend port 5000
    for _ in range(32):
        if _is_port_open(5000):
            break
        time.sleep(0.25)

    if force_setup or not has_gemini_key:
        open_setup_window()

    # Run hands-free voice loop resiliently
    while True:
        try:
            voice_listener.run_voice_loop()
        except Exception as exc:
            print(f"[NeoApp] Aguardando microfone/configuração ({exc}). Nova tentativa em 10s...")
            time.sleep(10)


if __name__ == "__main__":
    main()
