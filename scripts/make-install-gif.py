#!/usr/bin/env python3
"""Gera o GIF animado da instalação do Neo (assets/install-demo.gif).

Roda o instalador DE VERDADE (`node install.js`) num sandbox seguro
(venv/node_modules pré-aquecidos, HOME isolado) e anima a saída real num
GIF estilo terminal, com cores e digitação simulada.

Uso:
    python3 scripts/make-install-gif.py <demo-dir> <saida.gif> [HOME_isolado]

Exemplo (via scripts/record-install-demo.sh):
    HOME=/tmp/neo-install-demo/home python3 scripts/make-install-gif.py \
        /tmp/neo-install-demo/demo assets/install-demo.gif
"""

import os
import re
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageDraw, ImageFont

# ── Configuração do "terminal" ───────────────────────────────────────────────
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
PT = 14
MARGIN = 10
TITLE_H = 34
COLS = 84
ROWS = 28
FRAME_MS = 100            # duração de cada quadro
HOLD_FRAMES = 22          # pausa no quadro final
TYPE_FRAMES = 2           # quadros por caractere digitado

# Cores
BG = (12, 14, 18)
TITLE_BG = (22, 26, 34)
TEXT = (216, 216, 216)
GREEN = (96, 232, 150)
YELLOW = (255, 214, 92)
RED = (255, 105, 105)
MAGENTA = (255, 120, 224)
CYAN = (110, 205, 255)
ORANGE = (255, 190, 90)
DIM = (150, 155, 165)

FAKE_KEY = "AIzaSyNeo-Demo-Key-0000"   # chave fictícia digitada no demo


def colorize(text: str) -> tuple:
    """Escolhe a cor de uma linha com base no conteúdo."""
    if "Step" in text or "CONCLUÍDA" in text or "NEO.JS" in text or "INSTALADOR" in text:
        return MAGENTA
    if text.startswith("✓") or "Sucesso" in text or "detectado" in text \
            or "criado" in text or "concluído" in text or "Adicionado" in text \
            or "preservada" in text or "salvo" in text:
        return GREEN
    if text.startswith("✗") or "Erro" in text or "Falha" in text or "não foi" in text:
        return RED
    if "GEMINI_API_KEY" in text or "Digite sua" in text or "(s/n):" in text \
            or "Deseja" in text:
        return CYAN
    if text.startswith("⚠"):
        return ORANGE
    if text.startswith("[Processando]") or text.startswith("$ "):
        return TEXT
    return TEXT


def parse_transcript(raw: str):
    """Converte a saída bruta (com ANSI e \r) em eventos de linha.

    Retorna lista de eventos: ("line", texto).
    """
    ansi_clear = re.compile(r"\x1b\[[0-9;?]*[HJ]")   # clear screen / cursor home
    ansi_leftover = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\[[0-9;?]*|\x1b")
    events = []
    for part in ansi_clear.split(raw):
        part = ansi_leftover.sub("", part)   # remove sequências ANSI incompletas
        buf = ""
        i = 0
        n = len(part)
        while i < n:
            c = part[i]
            if c == "\r" and i + 1 < n and part[i + 1] == "\n":
                if buf.strip():
                    events.append(("line", buf.rstrip()))
                buf = ""
                i += 2
                continue
            if c == "\n":
                if buf.strip():
                    events.append(("line", buf.rstrip()))
                buf = ""
                i += 1
                continue
            if c == "\r":
                buf = ""          # barra de progresso: sobrescreve a linha
                i += 1
                continue
            buf += c
            i += 1
        if buf.strip():
            events.append(("line", buf.rstrip()))
    return events


# ── Captura do instalador real ───────────────────────────────────────────────
def capture_installer(demo_dir: str, home_dir: str) -> tuple[str, int]:
    env = dict(os.environ)
    env["HOME"] = home_dir
    env.pop("NEO_BACKEND_URL", None)
    # Stubs rápidos do demo (npm fictício) têm prioridade no PATH
    bin_dir = os.path.join(home_dir, "bin")
    if os.path.isdir(bin_dir):
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")

    proc = subprocess.Popen(
        ["node", "install.js"],
        cwd=demo_dir,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,   # pipes binários: leitura por chunks funciona de imediato
    )

    answered = set()
    lines = []       # linhas completas (com \n) + prompt final sem \n
    buf = ""
    deadline = time.time() + 180   # trava de segurança contra hangs

    def maybe_respond(buffer: str):
        if "Digite sua GEMINI_API_KEY" in buffer and "key" not in answered:
            answered.add("key")
            proc.stdin.write((FAKE_KEY + "\n").encode()); proc.stdin.flush()
        elif "Deseja recriar o ambiente virtual" in buffer and "venv" not in answered:
            answered.add("venv")
            proc.stdin.write(b"n\n"); proc.stdin.flush()
        elif "Deseja configurar o neo.service" in buffer and "systemd" not in answered:
            answered.add("systemd")
            proc.stdin.write(b"n\n"); proc.stdin.flush()
        elif "Deseja sobrescrevê-lo" in buffer and "overwrite" not in answered:
            answered.add("overwrite")
            proc.stdin.write(b"n\n"); proc.stdin.flush()
        elif "Deseja instalar o PM2" in buffer and "pm2" not in answered:
            answered.add("pm2")
            proc.stdin.write(b"n\n"); proc.stdin.flush()
        elif "(s/n):" in buffer:
            key = "generic-" + str(len(answered))
            if key not in answered:
                answered.add(key)
                proc.stdin.write(b"n\n"); proc.stdin.flush()

    # Leitura por chunks: prompts do readline NÃO terminam com \n, então
    # marcadores são detectados no buffer acumulado, não linha a linha.
    try:
        while True:
            if time.time() > deadline:
                proc.kill()
                break
            raw = proc.stdout.read(4096)
            if not raw:
                break
            buf += raw.decode("utf-8", "replace")
            maybe_respond(buf)
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if line.strip():
                    lines.append(line + "\n")
        if buf.strip():
            lines.append(buf)   # prompt final sem newline
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
    proc.wait()
    return "".join(lines), proc.returncode


# ── Renderização dos quadros ─────────────────────────────────────────────────
def build_fonts():
    font = ImageFont.truetype(FONT_PATH, PT)
    bold = ImageFont.truetype(FONT_BOLD_PATH, PT)
    title = ImageFont.truetype(FONT_BOLD_PATH, 12)
    return font, bold, title


def wrap_to_cols(line: str, cols: int) -> list[str]:
    """Quebra uma linha longa respeitando a largura em colunas."""
    if len(line) <= cols:
        return [line]
    out = []
    while len(line) > cols:
        cut = line[:cols]
        out.append(cut)
        line = line[cols:]
    out.append(line)
    return out


# DejaVu Sans Mono não cobre emojis — troca por texto para não virar "tofu".
EMOJI_MAP = {"🚀": "^", "🎉": "!", "🔒": "[lock]", "✅": "[ok]", "⚠": "!", "ℹ": "i"}


def clean_text(text: str) -> str:
    for k, v in EMOJI_MAP.items():
        text = text.replace(k, v)
    return "".join(c for c in text if ord(c) <= 0xFFFF)


class Terminal:
    def __init__(self, font, bold, title_font):
        self.font = font
        self.bold = bold
        self.title_font = title_font
        self.cell_w = max(8, int(font.getlength("M") + 0.5))
        self.line_h = PT + 6
        self.W = MARGIN * 2 + COLS * self.cell_w
        self.H = MARGIN * 2 + TITLE_H + ROWS * self.line_h
        self.lines = []   # lista de (texto, cor, bold?)

    def clear(self):
        self.lines = []

    def push(self, text: str, force_bold=False):
        text = clean_text(text)
        for piece in wrap_to_cols(text, COLS):
            self.lines.append((piece, colorize(text), force_bold))
        if len(self.lines) > ROWS:
            self.lines = self.lines[-ROWS:]

    def render(self):
        img = Image.new("RGB", (self.W, self.H), BG)
        d = ImageDraw.Draw(img)
        # barra de título
        d.rectangle([0, 0, self.W, TITLE_H], fill=TITLE_BG)
        d.text((MARGIN, 9), "Neo.JS - Interactive Installer", font=self.title_font,
               fill=CYAN)
        d.line([(0, TITLE_H), (self.W, TITLE_H)], fill=(38, 44, 58))
        y = MARGIN + TITLE_H
        for text, color, bold in self.lines:
            d.text((MARGIN, y), text, font=(self.bold if bold else self.font), fill=color)
            y += self.line_h
        return img


def render_gif(events: list, out_path: str):
    font, bold, title_font = build_fonts()
    term = Terminal(font, bold, title_font)
    frames = []

    def add_frame():
        frames.append(term.render())

    # 1) Tela vazia + comando inicial digitado
    term.push("$ ")
    add_frame()
    for ch in "node install.js":
        last = term.lines[-1]
        term.lines[-1] = (last[0] + ch, TEXT, False)   # anexa o char UMA vez
        for _ in range(TYPE_FRAMES):
            add_frame()
    term.push("")          # Enter
    add_frame()

    # 2) Replay dos eventos reais
    key_prompt = "Digite sua GEMINI_API_KEY (Gemini 2.0 Flash): "
    typing_key = False
    for ev in events:
        line = ev[1]
        # O prompt do readline não termina com \n, então ele aparece colado na
        # linha seguinte — divide para digitar a chave antes de mostrar o resto.
        if "Digite sua GEMINI_API_KEY" in line and not typing_key:
            typing_key = True
            idx = line.find(key_prompt)
            prompt_part = line[: idx + len(key_prompt)] if idx >= 0 else line
            rest = line[idx + len(key_prompt):] if idx >= 0 else ""
            term.push(prompt_part)
            add_frame()
            term.push("")
            for ch in FAKE_KEY:
                last = term.lines[-1]
                term.lines[-1] = (last[0] + ch, CYAN, False)
                for _ in range(TYPE_FRAMES):
                    add_frame()
            if rest:
                term.push(rest)
                add_frame()
            continue
        term.push(line)
        add_frame()

    # 3) Pausa final
    for _ in range(HOLD_FRAMES):
        add_frame()

    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=True,
    )
    return len(frames)


def main():
    demo_dir = sys.argv[1]
    out_path = sys.argv[2]
    home_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
        tempfile.gettempdir(), "neo-install-demo-home")
    os.makedirs(home_dir, exist_ok=True)

    print(f"[gif] Capturando instalador em {demo_dir} ...", flush=True)
    t0 = time.time()
    raw, code = capture_installer(demo_dir, home_dir)
    print(f"[gif] Instalador terminou (exit={code}) em {time.time()-t0:.1f}s", flush=True)
    if code != 0:
        sys.stderr.write(f"[gif] ERRO: instalador retornou {code}\n")
        sys.exit(1)

    events = parse_transcript(raw)
    print(f"[gif] {len(events)} eventos de linha capturados", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    n_frames = render_gif(events, out_path)
    size = os.path.getsize(out_path) / 1024
    print(f"[gif] OK: {out_path} ({n_frames} quadros, {size:.0f} KB)", flush=True)


if __name__ == "__main__":
    main()
