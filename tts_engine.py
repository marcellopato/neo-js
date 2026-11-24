import asyncio
import concurrent.futures
import glob
import os
import re
import sys
import uuid
from gtts import gTTS

# Configuration (PyInstaller-aware writable directory)
_BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__)
AUDIO_OUTPUT_DIR = os.path.join(_BASE_DIR, "audio_cache")
MAX_AUDIO_FILES = 50  # keep at most this many cached audio files
DEFAULT_EDGE_VOICE = "pt-BR-FranciscaNeural"
DEFAULT_EDGE_RATE = "+0%"

if not os.path.exists(AUDIO_OUTPUT_DIR):
    os.makedirs(AUDIO_OUTPUT_DIR)

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)


def sanitize_for_speech(text: str) -> str:
    """Strip markdown syntax, raw URLs in links, and emojis, and normalize 'Neo' pronunciation to 'Níu'."""
    if not text:
        return ""
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [label](url) -> label
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)  # remove fenced code blocks
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)  # inline code -> inner text
    cleaned = re.sub(r"[*#~>|]", "", cleaned)  # strip markdown punctuation
    cleaned = _EMOJI_RE.sub("", cleaned)
    # Pronounce "Neo" as "Níu" (Matrix style) in PT-BR TTS engines instead of "Nél"
    cleaned = re.sub(r"\b[Nn][Ee][Oo]\b", "Níu", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _cleanup_old_audio():
    """Remove oldest cached audio files beyond MAX_AUDIO_FILES to prevent unbounded growth."""
    files = []
    for ext in ("mp3", "ogg"):
        files.extend(glob.glob(os.path.join(AUDIO_OUTPUT_DIR, f"neo_voice_*.{ext}")))
    files.sort(key=os.path.getmtime)
    while len(files) > MAX_AUDIO_FILES:
        oldest = files.pop(0)
        try:
            os.remove(oldest)
            print(f"[TTS] Removido áudio antigo: {oldest}")
        except OSError as e:
            print(f"[TTS] Erro ao remover {oldest}: {e}")


def _synthesize_edge_tts(text: str, filepath: str, voice: str, rate: str) -> None:
    """Synthesize speech using Microsoft Edge neural TTS (free, no API key) with 10s timeout."""
    import edge_tts

    async def _run():
        communicator = edge_tts.Communicate(text, voice=voice, rate=rate)
        await asyncio.wait_for(communicator.save(filepath), timeout=10.0)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_run())
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, _run()).result(timeout=12.0)

    if not os.path.exists(filepath) or os.path.getsize(filepath) < 256:
        raise RuntimeError("edge-tts gerou arquivo de áudio vazio")


def _synthesize_gtts(text: str, filepath: str) -> None:
    """Fallback speech synthesis using gTTS (pt-BR)."""
    tts = gTTS(text=text, lang="pt", tld="com.br")
    tts.save(filepath)


def generate_audio(text: str) -> str | None:
    """Generate a PT-BR speech audio file and return its path, or None if disabled/failed."""
    if os.getenv("NEO_VOICE_ENABLED", "true").lower() != "true":
        return None

    clean_text = sanitize_for_speech(text)
    if not clean_text:
        return None

    _cleanup_old_audio()

    voice = os.getenv("NEO_TTS_VOICE", DEFAULT_EDGE_VOICE)
    rate = os.getenv("NEO_TTS_RATE", DEFAULT_EDGE_RATE)
    uid = uuid.uuid4().hex[:8]

    # Primary: edge-tts neural voice (.mp3)
    mp3_path = os.path.join(AUDIO_OUTPUT_DIR, f"neo_voice_{uid}.mp3")
    try:
        print(f"[TTS] Gerando áudio neural via edge-tts ({voice}, {rate}): {mp3_path}")
        _synthesize_edge_tts(clean_text, mp3_path, voice, rate)
        size = os.path.getsize(mp3_path) if os.path.exists(mp3_path) else 0
        print(f"[TTS] Áudio neural gerado ({size} bytes): {mp3_path}")
        return mp3_path
    except Exception as edge_err:
        print(f"[TTS Warning] edge-tts falhou ({edge_err}), usando fallback gTTS...")
        try:
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
        except OSError:
            pass

    # Fallback: gTTS (.mp3)
    fb_path = os.path.join(AUDIO_OUTPUT_DIR, f"neo_voice_{uid}_fb.mp3")
    try:
        print(f"[TTS] Gerando áudio via gTTS fallback: {fb_path}")
        _synthesize_gtts(clean_text, fb_path)
        size = os.path.getsize(fb_path) if os.path.exists(fb_path) else 0
        print(f"[TTS] Áudio gTTS gerado ({size} bytes): {fb_path}")
        return fb_path
    except Exception as gtts_err:
        print(f"[TTS Error] Falha ao gerar áudio (gTTS fallback): {gtts_err}")
        return None
