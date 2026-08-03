#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo CLI — converse com o Neo direto do terminal (ou do Termux no celular!).

Uso:
    python3 neo-cli.py [--backend http://127.0.0.1:5000] [--api-key KEY]
                       [--ask-port 3303] [--no-stream] [--no-ask] [--no-voice]

Comandos no REPL:
    /help        mostra esta ajuda
    /status      mostra a configuração atual da sessão
    /reset       reinicia o contexto de conversa do Neo (novo /reset no backend)
    /voz on|off  liga/desliga a voz (apenas no Termux, via termux-tts-speak)
    /audio       grava áudio do microfone e envia transcrito (apenas no Termux)
    /copiar      copia a última resposta para a área de transferência (Termux)
    /exit        sai do Neo CLI  (ou Ctrl+D)

Configuração (via .env ou variáveis de ambiente):
    INTERNAL_API_KEY    token interno (obrigatório — o mesmo do .env do Neo)
    NEO_BACKEND_URL     URL do backend  (default http://127.0.0.1:5000)
    NEO_GEMINI_API_KEY  chave Gemini opcional (header X-Gemini-API-Key)
    NEO_ASK_PORT        porta do servidor local de aprovações (default 3303)
    NEO_VOICE           "on"/"off" — força voz no Termux (default: on no Termux)

Aprovações de comandos:
    O servidor local de aprovações (porta 3303 por padrão) responde ao
    POST /ask do backend. No Termux aparece uma NOTIFICAÇÃO com botões
    Sim/Não; fora do Termux (ou sem termux-api), o pedido é exibido no
    próprio terminal para você responder sim/não.
"""

import argparse
import base64
import json
import os
import re
import select
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from shutil import which

try:
    import readline  # noqa: F401 — setas/histórico no terminal
except ImportError:
    pass

import requests

try:
    from dotenv import load_dotenv
except ImportError:
    # dotenv é opcional: sem ele, as variáveis de ambiente do sistema bastam.
    def load_dotenv(*args, **kwargs):
        return None

load_dotenv()  # .env do diretório atual (quando rodado da raiz do projeto)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))  # raiz do projeto sempre

# ── Cores ANSI ────────────────────────────────────────────────────────────────
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"


def colorize(text, color):
    return f"{color}{text}{C.RESET}"


# ── Detecção do Termux ────────────────────────────────────────────────────────
def is_termux():
    """True se estivermos rodando dentro do Termux (Android)."""
    return bool(os.environ.get("TERMUX_VERSION")) or os.environ.get(
        "PREFIX", ""
    ).startswith("/data/data/com.termux")


def termux_cmd(name):
    """Retorna o caminho de um utilitário do termux-api, ou None."""
    return which(name) if is_termux() else None


def strip_markdown(text):
    """Remove markdown básico para leitura em voz."""
    t = re.sub(r"```.*?```", " código. ", text, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"\*([^*]+)\*", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"[*_~>]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:2000]


# Sinalizado quando há um pedido de aprovação pendente — o loop principal
# pausa a leitura do stdin para não roubar a resposta digitada pelo usuário.
approval_pending = threading.Event()


# ── Voz (Termux) ──────────────────────────────────────────────────────────────
voice_enabled = False


def speak(text):
    """Lê a resposta em voz alta no Termux (termux-tts-speak)."""
    if not voice_enabled:
        return
    tts = termux_cmd("termux-tts-speak")
    if not tts:
        return
    clean = strip_markdown(text)
    if not clean:
        return
    try:
        subprocess.run([tts, "-r", "1.0", clean], timeout=120, check=False)
    except Exception:
        pass


def notify_ask(command, resp_file):
    """Dispara notificação no Termux com botões Sim/Não que escrevem no arquivo."""
    try:
        subprocess.Popen(
            [
                "termux-notification",
                "--id", "neo_ask",
                "--title", "🔐 Neo pede aprovação",
                "--content", f"Comando: {command}",
                "--sound",
                "--button1", "✅ Sim",
                "--button1-action", f"echo SIM > {resp_file}",
                "--button2", "❌ Não",
                "--button2-action", f"echo NAO > {resp_file}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def wait_decision(resp_file=None, timeout=120):
    """Aguarda a decisão do usuário: botões da notificação (arquivo) OU digitação.

    Retorna True se aprovado, False se negado/timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if resp_file and os.path.exists(resp_file):
            try:
                with open(resp_file, "r") as f:
                    answer = f.read().strip().upper()
                os.remove(resp_file)
                return answer == "SIM"
            except Exception:
                return False

        # Terminal: leitura não-bloqueante (POSIX)
        if os.name == "posix":
            try:
                ready, _, _ = select.select([sys.stdin], [], [], 0.3)
            except (ValueError, OSError):
                ready = []
            if sys.stdin in ready:
                line = sys.stdin.readline().strip().lower()
                if line:
                    return line in ("sim", "s", "yes", "y", "ok", "pode", "aprovar")
        else:
            # Windows: input() bloqueante (sem deadline perfeito)
            try:
                line = input("→ ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return False
            if line:
                return line in ("sim", "s", "yes", "y", "ok", "pode", "aprovar")

    return False


def request_approval(command):
    """Exibe o comando e pede aprovação. Retorna True/False."""
    approval_pending.set()
    try:
        print("\n" + colorize("🔐 " + "=" * 58, C.YELLOW))
        print(colorize("  O Neo quer executar este comando no sistema:", C.YELLOW))
        print(colorize(f"  $ {command}", C.BOLD + C.CYAN))
        print(colorize("=" * 64, C.YELLOW))

        resp_file = None
        if termux_cmd("termux-notification"):
            # Nome único por requisição: evita que um processo local pré-crie o
            # arquivo com "SIM" e aprove comandos sem a sua confirmação.
            resp_file = os.path.join(
                tempfile.gettempdir(), f"neo_ask_response_{os.getpid()}_{int(time.time()*1000)}"
            )
            if os.path.exists(resp_file):
                os.remove(resp_file)
            notify_ask(command, resp_file)
            print(colorize("  📲 Notificação enviada! Toque em Sim/Não ou digite aqui.", C.DIM))

        print("  → Aprovar? [s/N] ", end="", flush=True)
        approved = wait_decision(resp_file)
        print()
        if approved:
            print(colorize("  ✅ Aprovado!", C.GREEN))
        else:
            print(colorize("  ❌ Negado.", C.RED))
        return approved
    finally:
        approval_pending.clear()


# ── Servidor de aprovações (responde ao POST /ask do backend) ────────────────
class AskHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        expected = os.getenv("INTERNAL_API_KEY")
        token = self.headers.get("X-Neo-Token", "")
        if expected and token != expected:
            self._send_json(401, {"error": "Unauthorized"})
            return

        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length).decode("utf-8", "replace")
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {}
        command = payload.get("command", "")
        approved = request_approval(command)
        self._send_json(200, {"approved": approved})

    def _send_json(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # silencioso
        pass


def start_ask_server(port):
    """Inicia o servidor de aprovações em segundo plano. Retorna a porta ou None."""
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), AskHandler)
    except OSError as e:
        print(
            colorize(
                f"  ⚠️  Servidor de aprovações não iniciado na porta {port}: {e.strerror or e}.",
                C.YELLOW,
            )
        )
        print(
            colorize(
                "     (Se o WhatsApp bridge estiver ocupando a porta, tudo bem — as aprovações seguem por lá.)",
                C.DIM,
            )
        )
        return None
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return port


# ── Comunicação com o backend ─────────────────────────────────────────────────
def build_headers(cfg):
    headers = {"X-Neo-Token": cfg.token}
    if cfg.gemini_key:
        headers["X-Gemini-API-Key"] = cfg.gemini_key
    return headers


def stream_chat(cfg, text, on_chunk, on_status):
    """Streaming via POST /chat/stream (SSE). Retorna o texto completo."""
    reply = ""
    headers = build_headers(cfg)
    with requests.post(
        f"{cfg.backend}/chat/stream",
        json={"message": text},
        headers=headers,
        stream=True,
        timeout=(30, 600),
    ) as r:
        if r.status_code != 200:
            try:
                detail = r.json().get("detail") or f"HTTP {r.status_code}"
            except Exception:
                detail = r.text[:300] or f"HTTP {r.status_code}"
            raise RuntimeError(detail)

        r.encoding = "utf-8"
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data: "):
                continue
            line = raw[6:].strip()
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "chunk" in data:
                reply += data["chunk"]
                on_chunk(data["chunk"])
            elif data.get("status") == "thinking":
                on_status("💭 Neo está pensando...")
            elif data.get("status") == "executing":
                on_status(data.get("detail") or "⚡ Executando...")
            elif data.get("error"):
                on_status(f"⚠️  {data['error']}")
            elif data.get("done"):
                break
    return reply


def sync_chat(cfg, text):
    """Fallback via POST /chat (sem streaming)."""
    r = requests.post(
        f"{cfg.backend}/chat",
        json={"message": text},
        headers=build_headers(cfg),
        timeout=600,
    )
    if r.status_code != 200:
        try:
            detail = r.json().get("detail") or f"HTTP {r.status_code}"
        except Exception:
            detail = r.text[:300] or f"HTTP {r.status_code}"
        raise RuntimeError(detail)
    return r.json().get("response", "")


def reset_conversation(cfg):
    r = requests.post(
        f"{cfg.backend}/reset",
        headers=build_headers(cfg),
        timeout=30,
    )
    if r.status_code == 200:
        print(colorize("  🧹 Contexto de conversa reiniciado!", C.GREEN))
    else:
        try:
            detail = r.json().get("detail") or f"HTTP {r.status_code}"
        except Exception:
            detail = r.text[:200] or f"HTTP {r.status_code}"
        print(colorize(f"  ⚠️  Falha ao resetar: {detail}", C.RED))


# ── Comandos REPL ─────────────────────────────────────────────────────────────
def print_help():
    print(colorize("""
┌─ Comandos do Neo CLI ─────────────────────────────────────────┐
│  /help          mostra esta ajuda                            │
│  /status        mostra a configuração atual da sessão        │
│  /reset         reinicia o contexto de conversa do Neo       │
│  /voz on|off    liga/desliga a voz (Termux)                  │
│  /audio         grava áudio do microfone e envia (Termux)    │
│  /copiar        copia a última resposta (Termux)             │
│  /exit          sai do Neo CLI  (ou Ctrl+D)                  │
│                                                              │
│  Qualquer outra coisa digitada é enviada ao Neo.             │
└───────────────────────────────────────────────────────────────┘
""", C.CYAN))
    if is_termux():
        print(colorize("💡 Dica: instale o termux-api com `pkg install termux-api`\n"
                       "   e o app Termux:API para voz, microfone e notificações.", C.DIM))


def print_status(cfg, ask_port):
    lines = [
        ("Backend", cfg.backend),
        ("Token interno", "✅ definido" if cfg.token else "❌ FALTA INTERNAL_API_KEY"),
        ("Chave Gemini", "✅" if cfg.gemini_key else "— (usará a do backend)"),
        ("Modo", "streaming (SSE)" if cfg.stream else "síncrono"),
        ("Aprovações", f"servidor local :{ask_port}" if ask_port else "desativadas"),
        ("Ambiente", "📱 Termux" if is_termux() else "💻 Terminal"),
        ("Voz", "✅ ativa" if voice_enabled else "— desativada"),
    ]
    print(colorize("┌─ Status ───────────────────────────────────────┐", C.CYAN))
    for k, v in lines:
        print(colorize(f"│  {k:<14}: {v}", C.CYAN))
    print(colorize("└────────────────────────────────────────────────┘", C.CYAN))


def record_and_send(cfg):
    """Grava áudio no Termux, transcreve no backend e envia como mensagem."""
    if not termux_cmd("termux-microphone-record"):
        print(
            colorize(
                "  ⚠️  Microfone disponível apenas no Termux com `pkg install termux-api`.",
                C.YELLOW,
            )
        )
        return
    path = os.path.join(tempfile.gettempdir(), "neo_voz.m4a")
    if os.path.exists(path):
        os.remove(path)
    print(colorize("  🎙️  Gravando (até 15s)... fale agora! 🎙️", C.MAGENTA))
    try:
        subprocess.run(
            ["termux-microphone-record", "-f", path, "-l", "15"],
            timeout=25,
            check=False,
        )
    except Exception:
        pass
    subprocess.run(["termux-microphone-record", "-q"], stdout=subprocess.DEVNULL)

    if not os.path.exists(path) or os.path.getsize(path) == 0:
        print(colorize("  ⚠️  Nada gravado. Tente novamente.", C.RED))
        return

    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    try:
        r = requests.post(
            f"{cfg.backend}/transcribe",
            json={"data": data, "mimeType": "audio/mp4"},
            headers={"X-Neo-Token": cfg.token},
            timeout=90,
        )
    except requests.exceptions.RequestException as e:
        print(colorize(f"  ⚠️  Erro ao transcrever: {e}", C.RED))
        return
    if r.status_code != 200:
        print(colorize(f"  ⚠️  Falha na transcrição: HTTP {r.status_code}", C.RED))
        return
    transcription = (r.json().get("transcription") or "").strip()
    print(colorize(f"  🎙️  Transcrição: {transcription}", C.MAGENTA))
    if transcription:
        send_message(cfg, transcription)


def copy_last_response(cfg):
    if not cfg.last_response:
        print(colorize("  ⚠️  Ainda não há resposta para copiar.", C.YELLOW))
        return
    clip = termux_cmd("termux-clipboard-set")
    if not clip:
        print(
            colorize(
                "  ⚠️  Área de transferência disponível apenas no Termux (termux-api).",
                C.YELLOW,
            )
        )
        return
    try:
        subprocess.run([clip, cfg.last_response[:10000]], timeout=15, check=False)
        print(colorize("  📋 Última resposta copiada para a área de transferência!", C.GREEN))
    except Exception as e:
        print(colorize(f"  ⚠️  Falha ao copiar: {e}", C.RED))


def send_message(cfg, text):
    """Envia mensagem ao Neo (streaming SSE com fallback automático para sync)."""
    reply = ""
    state = {"prefix": False}

    def on_chunk(chunk):
        if not state["prefix"]:
            sys.stdout.write(colorize("🤖 Neo: ", C.CYAN + C.BOLD))
            sys.stdout.flush()
            state["prefix"] = True
        sys.stdout.write(chunk)
        sys.stdout.flush()

    def on_status(status):
        sys.stdout.write("\n" + colorize(f"  {status}", C.DIM) + "\n")
        sys.stdout.flush()

    try:
        if cfg.stream:
            try:
                reply = stream_chat(cfg, text, on_chunk, on_status)
            except RuntimeError as stream_err:
                # Fallback automático para /chat se o streaming falhar
                print(colorize(f"  ⚠️  Streaming falhou ({stream_err}). Usando modo síncrono...", C.YELLOW))
                reply = sync_chat(cfg, text)
                if reply:
                    sys.stdout.write(colorize("🤖 Neo: ", C.CYAN + C.BOLD))
                    sys.stdout.write(reply)
                    sys.stdout.flush()
        else:
            reply = sync_chat(cfg, text)
            if reply:
                sys.stdout.write(colorize("🤖 Neo: ", C.CYAN + C.BOLD))
                sys.stdout.write(reply)
                sys.stdout.flush()
    except RuntimeError as e:
        print("\n" + colorize(f"  ⚠️  {e}", C.RED))
        return
    except requests.exceptions.RequestException as e:
        print(
            "\n"
            + colorize(
                f"  ⚠️  Erro de conexão com o backend ({cfg.backend}): {e}", C.RED
            )
        )
        print(colorize("     💡 O backend está rodando? Tente: ./start.sh (ou --no-stream)", C.DIM))
        return

    if state["prefix"] or reply:
        print()
    cfg.last_response = reply
    speak(reply)


def handle_command(cfg, raw):
    parts = raw.split()
    name = parts[0].lower()

    if name in ("/help", "/?"):
        print_help()
    elif name == "/status":
        print_status(cfg, cfg.ask_port_running)
    elif name in ("/exit", "/quit"):
        print(colorize("👋 Até logo! 🧠", C.CYAN))
        sys.exit(0)
    elif name == "/reset":
        reset_conversation(cfg)
    elif name == "/voz":
        global voice_enabled
        if len(parts) > 1:
            voice_enabled = parts[1].lower() in ("on", "1", "true", "sim", "s")
        else:
            voice_enabled = not voice_enabled
        if voice_enabled and not termux_cmd("termux-tts-speak"):
            print(colorize("  ⚠️  Voz só funciona no Termux com termux-api instalado.", C.YELLOW))
        print(colorize(f"  🗣️  Voz {'ATIVA' if voice_enabled else 'desativada'}.", C.GREEN))
    elif name == "/audio":
        record_and_send(cfg)
    elif name == "/copiar":
        copy_last_response(cfg)
    else:
        print(colorize(f"  Comando desconhecido: {name}  (digite /help)", C.YELLOW))


# ── Configuração ──────────────────────────────────────────────────────────────
class Config:
    def __init__(self, args):
        self.backend = args.backend
        self.gemini_key = args.gemini_key
        self.token = os.getenv("INTERNAL_API_KEY", "")
        self.stream = not args.no_stream
        self.ask_port_running = None
        self.last_response = ""

        env_voice = os.getenv("NEO_VOICE", "").lower()
        if env_voice in ("on", "1", "true"):
            global voice_enabled
            voice_enabled = True
        elif env_voice in ("off", "0", "false"):
            voice_enabled = False
        else:
            voice_enabled = is_termux() and not args.no_voice


def parse_args():
    p = argparse.ArgumentParser(description="Neo CLI — converse com o Neo no terminal")
    p.add_argument("--backend", default=os.getenv("NEO_BACKEND_URL", "http://127.0.0.1:5000"))
    p.add_argument("--api-key", dest="gemini_key", default=os.getenv("NEO_GEMINI_API_KEY") or None)
    p.add_argument("--ask-port", type=int, default=int(os.getenv("NEO_ASK_PORT", "3303")))
    p.add_argument("--no-stream", action="store_true", help="usa POST /chat sem streaming")
    p.add_argument("--no-ask", action="store_true", help="não inicia o servidor de aprovações")
    p.add_argument("--no-voice", action="store_true", help="não ativa voz no Termux")
    return p.parse_args()


# ── Arte do Neo (gerada a partir de neo_head.png, half-blocks truecolor) ─────
NEO_ART = [
    '\x1b[38;2;18;67;37m\x1b[48;2;8;41;25m▀\x1b[38;2;4;11;17m\x1b[48;2;4;15;17m▀\x1b[38;2;0;34;10m\x1b[48;2;0;13;11m▀\x1b[38;2;4;14;16m\x1b[48;2;5;18;19m▀\x1b[38;2;3;14;15m\x1b[48;2;2;17;16m▀\x1b[38;2;5;28;16m\x1b[48;2;1;22;14m▀\x1b[38;2;6;17;19m\x1b[48;2;5;21;21m▀\x1b[38;2;5;22;20m\x1b[48;2;8;20;20m▀\x1b[38;2;1;14;8m\x1b[48;2;9;34;23m▀\x1b[38;2;6;20;21m\x1b[48;2;12;30;28m▀\x1b[38;2;14;53;25m\x1b[48;2;4;20;18m▀\x1b[38;2;17;74;37m\x1b[48;2;20;79;43m▀\x1b[38;2;7;19;19m\x1b[48;2;9;27;24m▀\x1b[38;2;3;30;18m\x1b[48;2;9;23;23m▀\x1b[38;2;24;113;55m\x1b[48;2;10;44;27m▀\x1b[38;2;4;16;17m\x1b[48;2;3;18;18m▀\x1b[38;2;28;115;53m\x1b[48;2;0;33;17m▀\x1b[38;2;5;15;18m\x1b[48;2;4;22;18m▀\x1b[38;2;4;12;16m\x1b[48;2;3;11;13m▀\x1b[38;2;32;133;59m\x1b[48;2;0;9;8m▀\x1b[0m',
    '\x1b[38;2;11;48;28m\x1b[48;2;10;42;27m▀\x1b[38;2;2;16;17m\x1b[48;2;8;22;22m▀\x1b[38;2;16;76;38m\x1b[48;2;0;5;0m▀\x1b[38;2;6;18;16m\x1b[48;2;0;2;0m▀\x1b[38;2;0;1;0m\x1b[48;2;22;38;29m▀\x1b[38;2;1;3;3m\x1b[48;2;67;75;75m▀\x1b[38;2;0;0;0m\x1b[48;2;64;74;73m▀\x1b[38;2;73;89;81m\x1b[48;2;18;25;31m▀\x1b[38;2;34;42;43m\x1b[48;2;18;22;24m▀\x1b[38;2;73;86;79m\x1b[48;2;17;24;28m▀\x1b[38;2;62;73;68m\x1b[48;2;31;38;40m▀\x1b[38;2;21;29;33m\x1b[48;2;0;0;1m▀\x1b[38;2;39;49;47m\x1b[48;2;43;52;47m▀\x1b[38;2;83;96;87m\x1b[48;2;24;33;35m▀\x1b[38;2;17;21;22m\x1b[48;2;58;66;63m▀\x1b[38;2;1;0;0m\x1b[48;2;79;91;86m▀\x1b[38;2;30;107;53m\x1b[48;2;0;0;0m▀\x1b[38;2;4;33;20m\x1b[48;2;2;17;15m▀\x1b[38;2;5;16;17m\x1b[48;2;4;19;20m▀\x1b[38;2;33;162;65m\x1b[48;2;14;75;33m▀\x1b[0m',
    '\x1b[38;2;26;87;50m\x1b[48;2;12;57;28m▀\x1b[38;2;29;69;39m\x1b[48;2;36;81;45m▀\x1b[38;2;1;0;1m\x1b[48;2;1;1;1m▀\x1b[38;2;0;0;0m\x1b[48;2;0;1;1m▀\x1b[38;2;0;0;1m\x1b[48;2;0;0;0m▀\x1b[38;2;25;30;35m\x1b[48;2;1;1;1m▀\x1b[38;2;0;0;0m\x1b[48;2;12;9;4m▀\x1b[38;2;0;0;0m\x1b[48;2;6;5;4m▀\x1b[38;2;0;0;0m\x1b[48;2;10;5;3m▀\x1b[38;2;0;0;0m\x1b[48;2;8;5;3m▀\x1b[38;2;0;0;0m\x1b[48;2;7;4;3m▀\x1b[38;2;0;0;0m\x1b[48;2;0;1;1m▀\x1b[38;2;0;0;1m\x1b[48;2;8;6;3m▀\x1b[38;2;0;0;0m\x1b[48;2;10;6;4m▀\x1b[38;2;1;2;1m\x1b[48;2;2;3;2m▀\x1b[38;2;0;0;1m\x1b[48;2;21;27;30m▀\x1b[38;2;11;13;15m\x1b[48;2;0;3;1m▀\x1b[38;2;14;86;37m\x1b[48;2;14;82;36m▀\x1b[38;2;6;20;21m\x1b[48;2;5;23;23m▀\x1b[38;2;4;47;22m\x1b[48;2;20;107;48m▀\x1b[0m',
    '\x1b[38;2;23;106;54m\x1b[48;2;26;102;53m▀\x1b[38;2;35;76;42m\x1b[48;2;37;78;45m▀\x1b[38;2;0;0;0m\x1b[48;2;1;1;1m▀\x1b[38;2;1;1;1m\x1b[48;2;0;0;0m▀\x1b[38;2;1;1;1m\x1b[48;2;0;0;0m▀\x1b[38;2;1;2;1m\x1b[48;2;15;10;8m▀\x1b[38;2;203;161;117m\x1b[48;2;205;164;120m▀\x1b[38;2;238;204;158m\x1b[48;2;239;206;160m▀\x1b[38;2;235;202;156m\x1b[48;2;239;205;158m▀\x1b[38;2;235;202;156m\x1b[48;2;238;204;156m▀\x1b[38;2;234;202;155m\x1b[48;2;238;204;159m▀\x1b[38;2;234;201;153m\x1b[48;2;236;203;157m▀\x1b[38;2;235;203;156m\x1b[48;2;238;205;157m▀\x1b[38;2;234;204;155m\x1b[48;2;238;207;159m▀\x1b[38;2;236;201;154m\x1b[48;2;236;206;158m▀\x1b[38;2;203;160;118m\x1b[48;2;204;160;116m▀\x1b[38;2;0;0;0m\x1b[48;2;0;0;0m▀\x1b[38;2;4;29;21m\x1b[48;2;18;104;45m▀\x1b[38;2;6;25;20m\x1b[48;2;7;31;24m▀\x1b[38;2;12;60;33m\x1b[48;2;11;59;32m▀\x1b[0m',
    '\x1b[38;2;11;44;29m\x1b[48;2;15;63;32m▀\x1b[38;2;35;76;43m\x1b[48;2;36;80;44m▀\x1b[38;2;0;0;0m\x1b[48;2;1;1;1m▀\x1b[38;2;1;1;1m\x1b[48;2;0;0;0m▀\x1b[38;2;6;1;0m\x1b[48;2;4;1;1m▀\x1b[38;2;213;168;124m\x1b[48;2;142;116;93m▀\x1b[38;2;209;169;128m\x1b[48;2;4;6;7m▀\x1b[38;2;238;205;158m\x1b[48;2;4;8;9m▀\x1b[38;2;239;206;161m\x1b[48;2;23;34;28m▀\x1b[38;2;238;206;158m\x1b[48;2;43;57;46m▀\x1b[38;2;238;204;159m\x1b[48;2;158;138;113m▀\x1b[38;2;241;205;161m\x1b[48;2;165;144;116m▀\x1b[38;2;237;202;155m\x1b[48;2;65;57;48m▀\x1b[38;2;236;203;157m\x1b[48;2;5;7;11m▀\x1b[38;2;237;204;160m\x1b[48;2;15;20;19m▀\x1b[38;2;213;170;128m\x1b[48;2;43;65;51m▀\x1b[38;2;77;61;47m\x1b[48;2;18;23;18m▀\x1b[38;2;11;53;31m\x1b[48;2;19;111;49m▀\x1b[38;2;5;26;20m\x1b[48;2;6;29;20m▀\x1b[38;2;36;155;67m\x1b[48;2;21;104;46m▀\x1b[0m',
    '\x1b[38;2;20;92;46m\x1b[48;2;17;65;36m▀\x1b[38;2;36;80;47m\x1b[48;2;37;82;49m▀\x1b[38;2;6;0;0m\x1b[48;2;7;1;0m▀\x1b[38;2;0;4;2m\x1b[48;2;183;139;101m▀\x1b[38;2;10;2;0m\x1b[48;2;6;1;0m▀\x1b[38;2;2;2;2m\x1b[48;2;75;58;42m▀\x1b[38;2;14;25;26m\x1b[48;2;8;15;15m▀\x1b[38;2;49;77;62m\x1b[48;2;21;35;35m▀\x1b[38;2;23;40;38m\x1b[48;2;25;42;38m▀\x1b[38;2;18;28;36m\x1b[48;2;10;18;19m▀\x1b[38;2;39;31;24m\x1b[48;2;117;96;74m▀\x1b[38;2;175;133;96m\x1b[48;2;238;201;153m▀\x1b[38;2;10;16;20m\x1b[48;2;37;33;28m▀\x1b[38;2;10;21;25m\x1b[48;2;22;39;38m▀\x1b[38;2;27;49;42m\x1b[48;2;28;44;41m▀\x1b[38;2;70;99;78m\x1b[48;2;14;26;30m▀\x1b[38;2;5;9;9m\x1b[48;2;4;5;6m▀\x1b[38;2;17;93;42m\x1b[48;2;13;70;34m▀\x1b[38;2;6;37;25m\x1b[48;2;7;42;27m▀\x1b[38;2;11;58;32m\x1b[48;2;13;87;40m▀\x1b[0m',
    '\x1b[38;2;22;85;46m\x1b[48;2;9;50;28m▀\x1b[38;2;38;84;49m\x1b[48;2;37;82;49m▀\x1b[38;2;7;1;0m\x1b[48;2;3;0;1m▀\x1b[38;2;181;136;97m\x1b[48;2;171;130;92m▀\x1b[38;2;174;128;92m\x1b[48;2;178;135;98m▀\x1b[38;2;239;206;157m\x1b[48;2;243;208;163m▀\x1b[38;2;154;121;96m\x1b[48;2;238;202;156m▀\x1b[38;2;1;1;1m\x1b[48;2;215;176;132m▀\x1b[38;2;1;1;1m\x1b[48;2;219;179;136m▀\x1b[38;2;198;150;107m\x1b[48;2;241;211;165m▀\x1b[38;2;238;206;157m\x1b[48;2;241;207;157m▀\x1b[38;2;238;208;163m\x1b[48;2;240;208;159m▀\x1b[38;2;204;163;117m\x1b[48;2;239;208;159m▀\x1b[38;2;5;5;4m\x1b[48;2;213;177;133m▀\x1b[38;2;2;2;2m\x1b[48;2;215;173;129m▀\x1b[38;2;3;3;2m\x1b[48;2;216;177;137m▀\x1b[38;2;91;77;60m\x1b[48;2;86;74;57m▀\x1b[38;2;9;67;34m\x1b[48;2;14;73;38m▀\x1b[38;2;9;45;28m\x1b[48;2;8;42;26m▀\x1b[38;2;37;138;65m\x1b[48;2;29;144;60m▀\x1b[0m',
    '\x1b[38;2;10;53;27m\x1b[48;2;10;72;37m▀\x1b[38;2;37;84;50m\x1b[48;2;1;5;1m▀\x1b[38;2;8;0;0m\x1b[48;2;72;52;37m▀\x1b[38;2;159;122;86m\x1b[48;2;150;115;82m▀\x1b[38;2;153;116;82m\x1b[48;2;140;105;75m▀\x1b[38;2;241;201;152m\x1b[48;2;211;170;126m▀\x1b[38;2;240;209;161m\x1b[48;2;226;192;146m▀\x1b[38;2;241;209;161m\x1b[48;2;243;210;162m▀\x1b[38;2;241;209;161m\x1b[48;2;243;212;163m▀\x1b[38;2;242;211;164m\x1b[48;2;242;210;160m▀\x1b[38;2;143;104;74m\x1b[48;2;242;211;162m▀\x1b[38;2;142;104;74m\x1b[48;2;241;209;158m▀\x1b[38;2;204;168;130m\x1b[48;2;242;208;159m▀\x1b[38;2;240;209;159m\x1b[48;2;239;208;160m▀\x1b[38;2;238;207;160m\x1b[48;2;239;207;158m▀\x1b[38;2;238;205;155m\x1b[48;2;216;175;128m▀\x1b[38;2;89;75;55m\x1b[48;2;78;64;49m▀\x1b[38;2;13;76;38m\x1b[48;2;14;102;45m▀\x1b[38;2;5;45;24m\x1b[48;2;9;54;31m▀\x1b[38;2;16;98;46m\x1b[48;2;34;147;64m▀\x1b[0m',
    '\x1b[38;2;15;90;41m\x1b[48;2;83;103;87m▀\x1b[38;2;0;0;0m\x1b[48;2;56;64;61m▀\x1b[38;2;144;108;77m\x1b[48;2;11;16;18m▀\x1b[38;2;139;103;74m\x1b[48;2;2;2;0m▀\x1b[38;2;135;101;71m\x1b[48;2;43;52;51m▀\x1b[38;2;211;169;126m\x1b[48;2;17;21;25m▀\x1b[38;2;210;165;121m\x1b[48;2;0;0;0m▀\x1b[38;2;239;208;161m\x1b[48;2;98;73;56m▀\x1b[38;2;240;208;159m\x1b[48;2;101;78;57m▀\x1b[38;2;239;207;158m\x1b[48;2;97;73;55m▀\x1b[38;2;239;208;160m\x1b[48;2;93;72;52m▀\x1b[38;2;239;207;161m\x1b[48;2;100;76;56m▀\x1b[38;2;238;206;156m\x1b[48;2;37;28;21m▀\x1b[38;2;238;204;154m\x1b[48;2;1;1;1m▀\x1b[38;2;218;182;138m\x1b[48;2;15;21;24m▀\x1b[38;2;198;158;117m\x1b[48;2;48;55;54m▀\x1b[38;2;71;56;42m\x1b[48;2;1;1;1m▀\x1b[38;2;17;90;43m\x1b[48;2;95;119;95m▀\x1b[38;2;11;61;34m\x1b[48;2;89;115;92m▀\x1b[38;2;14;67;33m\x1b[48;2;97;123;97m▀\x1b[0m',
    '\x1b[38;2;59;65;62m\x1b[48;2;19;25;27m▀\x1b[38;2;58;65;64m\x1b[48;2;62;67;67m▀\x1b[38;2;20;28;30m\x1b[48;2;58;66;66m▀\x1b[38;2;67;84;73m\x1b[48;2;18;24;28m▀\x1b[38;2;52;61;60m\x1b[48;2;1;1;1m▀\x1b[38;2;19;27;28m\x1b[48;2;85;99;90m▀\x1b[38;2;0;1;1m\x1b[48;2;50;56;54m▀\x1b[38;2;126;91;65m\x1b[48;2;16;22;24m▀\x1b[38;2;145;105;75m\x1b[48;2;16;18;19m▀\x1b[38;2;160;121;89m\x1b[48;2;20;12;6m▀\x1b[38;2;165;122;90m\x1b[48;2;21;15;7m▀\x1b[38;2;162;123;89m\x1b[48;2;19;15;8m▀\x1b[38;2;68;48;36m\x1b[48;2;6;7;10m▀\x1b[38;2;0;0;0m\x1b[48;2;0;1;0m▀\x1b[38;2;18;23;27m\x1b[48;2;87;100;90m▀\x1b[38;2;60;66;66m\x1b[48;2;5;8;7m▀\x1b[38;2;41;53;41m\x1b[48;2;11;16;17m▀\x1b[38;2;15;22;27m\x1b[48;2;60;66;66m▀\x1b[38;2;63;70;71m\x1b[48;2;32;38;41m▀\x1b[38;2;61;67;67m\x1b[48;2;26;32;36m▀\x1b[0m',
]


def _vis_len(s):
    """Largura visível no terminal, ignorando códigos ANSI.

    Emojis e caracteres CJK ocupam 2 colunas (east_asian_width W/F) — sem isso,
    a borda direita da caixa do banner fica desalinhada em terminais reais.
    """
    import unicodedata
    s = re.sub(r"\x1b\[[0-9;]*m", "", s)
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def build_banner(cfg):
    """Banner estilo neofetch: arte do Neo à esquerda + caixa de boas-vindas.

    A arte usa meio-blocos (▀/▄) com cores truecolor (38;2 / 48;2), gerada a
    partir de neo_head.png. O texto à direita mostra as boas-vindas e o backend.
    """
    art = NEO_ART
    art_w = max(_vis_len(a) for a in art)
    n = len(art)

    # Conteúdo da caixa (a borda superior ocupa a linha 0 e a inferior a n-1,
    # então cabem exatamente n-2 linhas de texto no meio).
    content = [
        ("NEO CLI", C.CYAN + C.BOLD),
        ("seu agente direto no terminal", C.CYAN),
        ("", ""),
        ("👋 Olá! Eu sou o Neo.", C.RESET),
        ("Me dê tarefas, comandos e", C.RESET),
        ("perguntas — eu executo.", C.RESET),
        (f"Backend : {cfg.backend}", C.DIM),
        ("💡 /help  ·  /status  ·  /reset", C.DIM),
    ]
    inner_rows = max(0, n - 2)
    panel = (content + [("", "")] * inner_rows)[:inner_rows]

    inner = max(_vis_len(t) for t, _ in content) + 2
    lines = []
    for i in range(n):
        art_line = art[i]
        art_pad = art_line + " " * (art_w - _vis_len(art_line))
        if i == 0:
            body = "╔" + "═" * (inner + 2) + "╗"
        elif i == n - 1:
            body = "╚" + "═" * (inner + 2) + "╝"
        else:
            text, color = panel[i - 1]
            txt = (color + text + C.RESET) if text else ""
            pad = max(0, inner - _vis_len(text))
            body = "║ " + txt + " " * pad + " ║"
        lines.append(art_pad + "   " + body)
    return "\n".join(lines)



def setup_token(cfg):
    """Setup de primeira execução: pede a INTERNAL_API_KEY e salva no .env.

    Roda apenas quando o token não foi encontrado no ambiente nem no .env.
    Só pergunta em terminal interativo (isatty) — com stdin piped, evita
    engolir a primeira linha como se fosse a chave. Depois de validar contra
    o backend, grava no .env do projeto para as próximas execuções não
    pedirem de novo.
    """
    print(colorize("\n  🔑 INTERNAL_API_KEY não encontrada no ambiente nem no .env.", C.YELLOW))
    print(colorize("     Ela é o token interno que protege o backend (o mesmo do .env do Neo).", C.DIM))

    if not sys.stdin.isatty():
        print(colorize("  ⚠️  Terminal não interativo — não vou pedir a chave agora.", C.RED))
        print(colorize("     Defina INTERNAL_API_KEY no .env ou exporte no ambiente antes de rodar.", C.DIM))
        return

    try:
        raw = input(colorize("  → Cole aqui a INTERNAL_API_KEY (ou Enter para pular): ", C.CYAN)).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if not raw:
        print(colorize("  ⚠️  Sem chave — o backend vai responder 401. Dá pra definir depois no .env.", C.RED))
        return

    # Valida contra o backend (endpoint leve, sem gastar Gemini)
    verified = None  # True=ok, False=inválida, None=backend offline
    try:
        r = requests.post(f"{cfg.backend}/reset", headers={"X-Neo-Token": raw}, timeout=15)
        if r.status_code == 200:
            verified = True
            print(colorize("  ✅ Token validado! O backend respondeu OK.", C.GREEN))
        else:
            verified = False
            print(colorize(f"  ⚠️  O backend respondeu HTTP {r.status_code} — o token parece errado.", C.YELLOW))
    except requests.exceptions.RequestException as e:
        print(colorize(f"  ⚠️  Não consegui validar (backend offline?): {e}", C.YELLOW))

    if verified is False:
        try:
            retry = input(colorize("  → Salvar mesmo assim? [s/N] ", C.CYAN)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            retry = ""
        if retry not in ("s", "sim", "y", "yes"):
            print(colorize("  ✋ Não salvo. Você pode tentar de novo com a chave correta.", C.DIM))
            return

    # Salva no .env do projeto (idempotente)
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        out = []
        replaced = False
        for ln in lines:
            if ln.startswith("INTERNAL_API_KEY="):
                out.append(f"INTERNAL_API_KEY={raw}")
                replaced = True
            else:
                out.append(ln)
        if not replaced:
            out.append(f"INTERNAL_API_KEY={raw}")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        # Protege o .env: só o dono pode ler/escrever (contém segredos)
        try:
            os.chmod(env_path, 0o600)
        except OSError:
            pass
        print(colorize(f"  💾 Salvo em {env_path} (permissão 600)", C.DIM))
    except OSError as e:
        print(colorize(f"  ⚠️  Não consegui salvar no .env: {e}", C.RED))

    cfg.token = raw
    os.environ["INTERNAL_API_KEY"] = raw


def main():
    args = parse_args()
    cfg = Config(args)

    print(build_banner(cfg))
    if not cfg.token:
        setup_token(cfg)

    if is_termux():
        print(colorize("  📱 Termux detectado! Voz, microfone e notificações ativos.", C.GREEN))
        missing = [n for n in ("termux-tts-speak", "termux-notification", "termux-microphone-record") if not termux_cmd(n)]
        if missing:
            print(
                colorize(
                    f"  💡 Falta: {', '.join(missing)} — instale `pkg install termux-api` + app Termux:API.",
                    C.YELLOW,
                )
            )

    if not args.no_ask:
        cfg.ask_port_running = start_ask_server(args.ask_port)
    print()

    while True:
        # Se houver aprovação pendente, não leia o stdin (evita roubar a resposta)
        while approval_pending.is_set():
            time.sleep(0.1)
        try:
            raw = input(colorize("💻 você> ", C.GREEN))
        except (EOFError, KeyboardInterrupt):
            print("\n" + colorize("👋 Até logo! 🧠", C.CYAN))
            break

        message = raw.strip()
        if not message:
            continue
        if message.startswith("/"):
            handle_command(cfg, message)
            continue

        try:
            send_message(cfg, message)
        except KeyboardInterrupt:
            print("\n" + colorize("  ⏹️  Cancelado.", C.YELLOW))
        except Exception as e:
            print("\n" + colorize(f"  ⚠️  Erro inesperado: {e}", C.RED))


if __name__ == "__main__":
    main()
