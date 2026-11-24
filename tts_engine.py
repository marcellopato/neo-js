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
    """Strip markdown syntax, raw URLs in links, and emojis for natural spoken output."""
    if not text:
        return ""
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [label](url) -> label
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)  # remove fenced code blocks
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)  # inline code -> inner text
    cleaned = re.sub(r"[*#~>|]", "", cleaned)  # strip markdown punctuation
    cleaned = _EMOJI_RE.sub("", cleaned)
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
    """Synthesize speech using Microsoft Edge neural TTS (free, no API key)."""
    import edge_tts

    async def _run():
        communicator = edge_tts.Communicate(text, voice=voice, rate=rate)
        await communicator.save(filepath)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_run())
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, _run()).result()


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
        return mp3_path
    except Exception as edge_err:
        print(f"[TTS Warning] edge-tts falhou ({edge_err}), usando fallback gTTS...")

    # Fallback: gTTS (.ogg)
    ogg_path = os.path.join(AUDIO_OUTPUT_DIR, f"neo_voice_{uid}.ogg")
    try:
        print(f"[TTS] Gerando áudio via gTTS fallback: {ogg_path}")
        _synthesize_gtts(clean_text, ogg_path)
        return ogg_path
    except Exception as gtts_err:
        print(f"[TTS Error] Falha ao gerar áudio (gTTS fallback): {gtts_err}")
        return None
