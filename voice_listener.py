"""Hands-free wake-word ('Ei Neo') and conversational voice client for Neo.JS."""

from __future__ import annotations

import base64
import io
import json
import math
import os
import re
import struct
import sys
import threading
import time
import unicodedata
import wave
from enum import Enum

import requests
from dotenv import load_dotenv

import tts_engine

load_dotenv()

DEFAULT_WAKE_PHRASES = (
    "jarvis",
    "ei jarvis",
    "oi jarvis",
    "ok jarvis",
    "ola jarvis",
    "jarbas",
    "ei jarbas",
    "oi jarbas",
    "ok jarbas",
    "ei chaves",
    "oi chaves",
    "ok chaves",
    "ei charles",
    "oi charles",
    "ei neo",
    "oi neo",
    "ok neo",
    "ei niu",
    "oi niu",
    "ok niu",
    "ei nil",
    "oi nil",
    "ok nil",
    "ei new",
    "oi new",
    "ok new",
    "ei nio",
    "oi nio",
    "ok nio",
    "ei nel",
    "oi nel",
    "ok nel",
    "ei neu",
    "oi neu",
    "ok neu",
    "ei meu",
    "oi meu",
    "ok meu",
    "ei mil",
    "oi mil",
    "ok mil",
    "em mil",
    "em meu",
    "em nil",
    "em niu",
    "em neo",
    "e mil",
    "hein mil",
    "hey neo",
    "hey niu",
    "ola neo",
    "ola niu",
    "ola nil",
)

_WAKE_REGEX = re.compile(
    r"\b(?:"
    r"(?:(?:ei|hey|oi|ou|ok|okey|o\s+que|oque|ola|ai|e|em|en|hem|hein|um)\s+)?(?:jarvis|jarves|jarbas|de\s+aves|de\s+arabes|d\s+aves)"
    r"|"
    r"(?:ei|hey|oi|ou|ok|okey|o\s+que|oque|ola|ai|e|em|en|hem|hein|um)\s+(?:chaves|charles|neo|niu|nil|new|nio|nel|neu|meu|mil|ninho)"
    r")\b"
)


def extract_command_after_wake(text: str) -> str:
    """If the user spoke a command in the same breath as the wake phrase (e.g. 'em mil leia meus emails'), extract it."""
    norm = re.sub(r"\s+", " ", _normalize_text(text))
    m = _WAKE_REGEX.search(norm)
    if not m:
        return ""
    remainder = norm[m.end():].strip()
    return remainder if len(remainder) >= 4 else ""
DEFAULT_BACKEND_URL = os.getenv("NEO_BACKEND_URL", "http://127.0.0.1:5000")


def _resolve_vosk_model_dir() -> str:
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidate = os.path.join(exe_dir, "models", "vosk-pt")
        if os.path.isdir(candidate):
            return candidate
        meipass = getattr(sys, "_MEIPASS", exe_dir)
        return os.path.join(meipass, "models", "vosk-pt")
    return os.path.join(os.path.dirname(__file__), "models", "vosk-pt")


DEFAULT_VOSK_MODEL_DIR = _resolve_vosk_model_dir()
SAMPLE_RATE = 16000


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    FOLLOWUP = "followup"


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    no_accents = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9\s]", " ", no_accents).strip()


def matches_wake_phrase(text: str, phrases: tuple[str, ...] = DEFAULT_WAKE_PHRASES) -> bool:
    """Return True if recognized speech contains any configured wake phrase (including PT-BR phonetic variants for 'Ei Niu')."""
    norm = re.sub(r"\s+", " ", _normalize_text(text))
    if not norm:
        return False
    if any(_normalize_text(p) in norm for p in phrases):
        return True
    return bool(_WAKE_REGEX.search(norm))


class VoiceSessionStateMachine:
    """Hardware-independent state machine for hands-free voice turns and follow-up windows."""

    def __init__(
        self,
        followup_seconds: float | None = None,
        wake_phrases: tuple[str, ...] = DEFAULT_WAKE_PHRASES,
    ):
        self.state = VoiceState.IDLE
        self.wake_phrases = wake_phrases
        self.followup_seconds = float(
            followup_seconds
            if followup_seconds is not None
            else os.getenv("NEO_FOLLOWUP_SECONDS", "8")
        )
        self.last_reply: str = ""

    def on_wake_word(self, recognized_text: str) -> str | None:
        if self.state != VoiceState.IDLE:
            return None
        if matches_wake_phrase(recognized_text, self.wake_phrases):
            self.state = VoiceState.LISTENING
            return "start"
        return None

    def on_speech_captured(self, audio_bytes: bytes | None) -> str | None:
        if self.state not in (VoiceState.LISTENING, VoiceState.FOLLOWUP):
            return None
        if not audio_bytes:
            self.state = VoiceState.IDLE
            return "timeout" if self.state == VoiceState.LISTENING else None
        self.state = VoiceState.PROCESSING
        return "processing"

    def on_reply_ready(self, reply_text: str) -> None:
        if self.state != VoiceState.PROCESSING:
            return
        self.last_reply = reply_text
        self.state = VoiceState.SPEAKING

    def on_speaking_finished(self) -> None:
        if self.state == VoiceState.SPEAKING:
            self.state = VoiceState.FOLLOWUP

    def on_silence_timeout(self) -> str | None:
        prev = self.state
        self.state = VoiceState.IDLE
        return "timeout" if prev == VoiceState.LISTENING else None

    def on_interrupt(self) -> None:
        self.state = VoiceState.IDLE

    def on_error(self, _reason: str = "") -> str:
        self.state = VoiceState.IDLE
        return "error"


def _make_beep_wav(freq: int, duration_ms: int, volume: float = 0.35) -> bytes:
    """Synthesize a clean sine-wave WAV in memory so beeps work on all Windows speakers/headphones."""
    num_samples = int(SAMPLE_RATE * (duration_ms / 1000.0))
    samples = []
    for i in range(num_samples):
        val = int(32767 * volume * math.sin(2.0 * math.pi * freq * (i / SAMPLE_RATE)))
        samples.append(struct.pack("<h", val))
    return _pcm_to_wav_bytes(samples, SAMPLE_RATE)


def play_cue_async(cue_name: str | None) -> None:
    """Play audio cue in a daemon thread so microphone capture never drops frames."""
    if not cue_name:
        return
    threading.Thread(target=play_cue, args=(cue_name,), daemon=True).start()


def play_cue(cue_name: str | None) -> None:
    """Play short non-verbal audio cues (beeps on Windows) for eyes-free feedback."""
    if not cue_name:
        return
    tones = {
        "start": (880, 180),       # high beep: listening
        "processing": (520, 130),  # mid beep: thinking
        "timeout": (380, 140),     # soft low beep: timed out
        "error": (260, 260),       # low longer beep: error
    }
    freq, duration_ms = tones.get(cue_name, (600, 120))
    if sys.platform == "win32":
        try:
            import winsound

            wav_data = _make_beep_wav(freq, duration_ms)
            winsound.PlaySound(wav_data, winsound.SND_MEMORY)
        except Exception:
            pass
    else:
        print(f"[VoiceCue] ({cue_name})")


def chat_with_text(
    message: str,
    backend_url: str = DEFAULT_BACKEND_URL,
    internal_token: str | None = None,
) -> str:
    """Send already-transcribed text to Neo backend /chat and return the reply."""
    token = internal_token or os.getenv("INTERNAL_API_KEY", "")
    headers = {"X-Neo-Token": token}
    base = backend_url.rstrip("/")
    res_c = requests.post(
        f"{base}/chat",
        json={"message": message},
        headers=headers,
        timeout=120,
    )
    res_c.raise_for_status()
    return (res_c.json().get("response") or "").strip()


def transcribe_and_chat(
    wav_bytes: bytes,
    backend_url: str = DEFAULT_BACKEND_URL,
    internal_token: str | None = None,
) -> tuple[str, str]:
    """Send WAV audio to Neo backend /transcribe, then query /chat in natural language."""
    token = internal_token or os.getenv("INTERNAL_API_KEY", "")
    headers = {"X-Neo-Token": token}
    base = backend_url.rstrip("/")

    b64_audio = base64.b64encode(wav_bytes).decode("ascii")
    res_t = requests.post(
        f"{base}/transcribe",
        json={"data": b64_audio, "mimeType": "audio/wav"},
        headers=headers,
        timeout=60,
    )
    res_t.raise_for_status()
    transcript = (res_t.json().get("transcription") or "").strip()
    if not transcript:
        return "", ""

    reply = chat_with_text(transcript, backend_url=backend_url, internal_token=token)
    return transcript, reply


def _pcm_rms(chunk: bytes) -> float:
    if not chunk:
        return 0.0
    count = len(chunk) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", chunk[: count * 2])
    mean_sq = sum(s * s for s in samples) / count
    return math.sqrt(mean_sq)


def _pcm_to_wav_bytes(pcm_chunks: list[bytes], sample_rate: int = SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(pcm_chunks))
    return buf.getvalue()


def record_until_silence(
    max_wait_seconds: float = 8.0,
    silence_seconds: float = 1.6,
    max_record_seconds: float = 20.0,
    rms_threshold: float = 180.0,
) -> bytes | None:
    """Record 16kHz mono PCM from default microphone until speech ends with silence."""
    import sounddevice as sd

    block_duration = 0.2
    block_size = int(SAMPLE_RATE * block_duration)
    chunks: list[bytes] = []
    speech_started = False
    start_time = time.monotonic()
    last_voice_time = start_time

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE, blocksize=block_size, dtype="int16", channels=1
    ) as stream:
        while True:
            data, _ = stream.read(block_size)
            raw = bytes(data)
            now = time.monotonic()
            rms = _pcm_rms(raw)

            if rms >= rms_threshold:
                speech_started = True
                last_voice_time = now

            if speech_started:
                chunks.append(raw)
                if (now - last_voice_time) >= silence_seconds:
                    break
                if (now - start_time) >= max_record_seconds:
                    break
            else:
                if (now - start_time) >= max_wait_seconds:
                    return None

    return _pcm_to_wav_bytes(chunks) if chunks else None


def play_audio_interruptible(filepath: str, stop_event: threading.Event) -> bool:
    """Play MP3/OGG audio via pygame.mixer, stopping immediately if stop_event is set.

    Returns True if interrupted, False if playback completed naturally.
    """
    import pygame

    if not pygame.mixer.get_init():
        pygame.mixer.init()
    pygame.mixer.music.load(filepath)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        if stop_event.is_set():
            pygame.mixer.music.stop()
            return True
        time.sleep(0.05)
    return False


def recognize_speech_ptbr(pcm_bytes: bytes, vosk_recognizer=None) -> str:
    """Recognize PT-BR speech from raw 16kHz 16-bit mono PCM bytes.

    Uses Google Web Speech API (via SpeechRecognition, free, no API key, high accuracy for 'Jarvis')
    as primary engine, with offline Vosk as automatic fallback.
    """
    if not pcm_bytes:
        return ""

    # 1. Primary: SpeechRecognition Google pt-BR (understands 'Jarvis' natively)
    try:
        import speech_recognition as sr

        rec = sr.Recognizer()
        audio_data = sr.AudioData(pcm_bytes, SAMPLE_RATE, 2)
        text = rec.recognize_google(audio_data, language="pt-BR")
        if text and text.strip():
            return text.strip()
    except Exception:
        pass

    # 2. Fallback: local offline Vosk
    if vosk_recognizer is not None:
        try:
            vosk_recognizer.Reset()
            vosk_recognizer.AcceptWaveform(pcm_bytes)
            res = json.loads(vosk_recognizer.FinalResult()).get("text", "")
            return (res or "").strip()
        except Exception:
            pass
    return ""


def run_voice_loop(
    model_dir: str = DEFAULT_VOSK_MODEL_DIR,
    backend_url: str = DEFAULT_BACKEND_URL,
) -> None:
    """Main hands-free loop: Local VAD -> Google PT-BR / Vosk STT -> Gemini Chat -> Edge TTS -> Follow-up."""
    import sounddevice as sd
    from collections import deque

    vosk_recognizer = None
    if os.path.isdir(model_dir):
        try:
            from vosk import KaldiRecognizer, Model

            print(f"[Voice] Carregando fallback offline Vosk de {model_dir}...")
            model = Model(model_dir)
            vosk_recognizer = KaldiRecognizer(model, SAMPLE_RATE)
        except Exception as exc:
            print(f"[Voice] Aviso Vosk fallback: {exc}")

    sm = VoiceSessionStateMachine()
    stop_event = threading.Event()

    # Optional global Esc hotkey to interrupt speech immediately
    try:
        import keyboard

        keyboard.add_hotkey("esc", lambda: (stop_event.set(), sm.on_interrupt()))
        print("[Voice] Atalho global Esc ativo para interromper a fala.")
    except Exception as exc:
        print(f"[Voice] Aviso: atalho global Esc indisponível ({exc}).")

    print("[Voice] Jarvis ouvindo em modo standby. Diga 'Jarvis' ou 'Ei Jarvis' para começar.")

    block_size = 3200  # 0.2s at 16kHz
    rms_threshold = 170.0

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE, blocksize=block_size, dtype="int16", channels=1
    ) as stream:
        while True:
            # ── 1. Standby (IDLE): wait for local voice activity, then transcribe utterance ──
            if sm.state == VoiceState.IDLE:
                pre_buffer: deque[bytes] = deque(maxlen=4)  # 0.8s pre-roll so 'Jar...' is never clipped
                utterance: list[bytes] = []
                speech_started = False
                start_t = 0.0
                last_voice_t = 0.0

                while sm.state == VoiceState.IDLE:
                    data, _ = stream.read(block_size)
                    raw = bytes(data)
                    rms = _pcm_rms(raw)
                    now = time.monotonic()

                    if not speech_started:
                        pre_buffer.append(raw)
                        if rms >= rms_threshold:
                            speech_started = True
                            start_t = now
                            last_voice_t = now
                            utterance.extend(pre_buffer)
                    else:
                        utterance.append(raw)
                        if rms >= rms_threshold:
                            last_voice_t = now
                        # End of utterance: 1.2s of silence or 14s max duration
                        if (now - last_voice_t) >= 1.2 or (now - start_t) >= 14.0:
                            pcm_data = b"".join(utterance)
                            utterance.clear()
                            speech_started = False

                            heard = recognize_speech_ptbr(pcm_data, vosk_recognizer)
                            if not heard:
                                continue
                            print(f"[Voice] Ouvido: '{heard}'")

                            cue = sm.on_wake_word(heard)
                            if cue:
                                inline_cmd = extract_command_after_wake(heard)
                                if inline_cmd:
                                    print(f"[Voice] Gatilho + comando reconhecido: '{inline_cmd}'")
                                    play_cue_async(sm.on_speech_captured(pcm_data))
                                    _handle_command_and_speak(inline_cmd, backend_url, sm, stop_event)
                                else:
                                    print("[Voice] Gatilho 'Jarvis' reconhecido! Ouvindo seu pedido...")
                                    play_cue_async(cue)
                                break

            # ── 2. Active Listening (after saying just 'Jarvis' or during 8s FOLLOWUP window) ──
            if sm.state in (VoiceState.LISTENING, VoiceState.FOLLOWUP):
                wait_sec = sm.followup_seconds if sm.state == VoiceState.FOLLOWUP else 8.0
                print(f"[Voice] Aguardando sua fala por até {wait_sec}s...")

                pre_buf: deque[bytes] = deque(maxlen=3)
                utt: list[bytes] = []
                started = False
                t0 = time.monotonic()
                last_v = t0

                while True:
                    data, _ = stream.read(block_size)
                    raw = bytes(data)
                    rms = _pcm_rms(raw)
                    now = time.monotonic()

                    if not started:
                        pre_buf.append(raw)
                        if rms >= rms_threshold:
                            started = True
                            last_v = now
                            utt.extend(pre_buf)
                        elif (now - t0) >= wait_sec:
                            break
                    else:
                        utt.append(raw)
                        if rms >= rms_threshold:
                            last_v = now
                        if (now - last_v) >= 1.4 or (now - t0) >= 20.0:
                            break

                if not utt:
                    print("[Voice] Silêncio detectado, voltando ao modo standby.")
                    play_cue_async(sm.on_silence_timeout())
                    continue

                pcm_captured = b"".join(utt)
                play_cue_async(sm.on_speech_captured(pcm_captured))

                transcript = recognize_speech_ptbr(pcm_captured, vosk_recognizer)
                if not transcript:
                    try:
                        wav_bytes = _pcm_to_wav_bytes([pcm_captured])
                        transcript, reply = transcribe_and_chat(wav_bytes, backend_url=backend_url)
                        if transcript and reply:
                            _speak_reply(transcript, reply, sm, stop_event)
                            continue
                    except Exception as exc:
                        print(f"[Voice] Erro no fallback de transcrição: {exc}")
                    play_cue_async(sm.on_error("empty"))
                    continue

                cleaned = extract_command_after_wake(transcript)
                if cleaned:
                    transcript = cleaned
                _handle_command_and_speak(transcript, backend_url, sm, stop_event)


def _handle_command_and_speak(
    transcript: str,
    backend_url: str,
    sm: VoiceSessionStateMachine,
    stop_event: threading.Event,
) -> None:
    try:
        print(f"[Voice] Você: {transcript}")
        reply = chat_with_text(transcript, backend_url=backend_url)
        if not reply:
            play_cue_async(sm.on_error("empty"))
            return
        _speak_reply(transcript, reply, sm, stop_event)
    except Exception as exc:
        print(f"[Voice] Erro ao consultar o Jarvis: {exc}")
        play_cue_async(sm.on_error(str(exc)))


def _speak_reply(
    _transcript: str,
    reply: str,
    sm: VoiceSessionStateMachine,
    stop_event: threading.Event,
) -> None:
    print(f"[Voice] Jarvis: {reply}")
    sm.on_reply_ready(reply)
    audio_path = tts_engine.generate_audio(reply)
    if audio_path and os.path.exists(audio_path):
        print(f"[Voice] Reproduzindo resposta em voz alta ({audio_path})...")
        stop_event.clear()
        interrupted = play_audio_interruptible(audio_path, stop_event)
        if interrupted:
            print("[Voice] Fala interrompida via Esc.")
            sm.on_interrupt()
        else:
            print("[Voice] Fala concluída. Microfone aberto para você continuar conversando...")
            sm.on_speaking_finished()
    else:
        sm.on_speaking_finished()


def test_microphone_sample(duration_seconds: float = 3.0) -> dict:
    """Record a short sample from the default microphone, compute RMS volume, and test PT-BR speech recognition."""
    import sounddevice as sd

    block_size = 4000
    num_blocks = max(1, int((SAMPLE_RATE * duration_seconds) / block_size))
    peak_rms = 0.0
    chunks: list[bytes] = []

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE, blocksize=block_size, dtype="int16", channels=1
    ) as stream:
        for _ in range(num_blocks):
            data, _ = stream.read(block_size)
            raw = bytes(data)
            chunks.append(raw)
            rms = _pcm_rms(raw)
            if rms > peak_rms:
                peak_rms = rms

    vosk_rec = None
    if os.path.isdir(DEFAULT_VOSK_MODEL_DIR):
        try:
            from vosk import KaldiRecognizer, Model

            vosk_rec = KaldiRecognizer(Model(DEFAULT_VOSK_MODEL_DIR), SAMPLE_RATE)
        except Exception:
            pass

    heard_text = recognize_speech_ptbr(b"".join(chunks), vosk_rec)
    wake_detected = matches_wake_phrase(heard_text)
    has_signal = peak_rms >= 150.0
    return {
        "ok": has_signal,
        "peak_rms": round(peak_rms, 1),
        "heard_text": heard_text,
        "wake_detected": wake_detected,
        "message": (
            f"Microfone funcionando! Volume máximo: {int(peak_rms)}. "
            + (f"Ouvido: '{heard_text}'." if heard_text else "Som captado (nenhuma palavra reconhecida no trecho).")
            + (" Gatilho 'Jarvis' reconhecido!" if wake_detected else "")
            if has_signal
            else f"Microfone muito baixo ou sem som (Volume: {int(peak_rms)}). Verifique o microfone padrão do Windows."
        ),
    }


if __name__ == "__main__":
    run_voice_loop()
