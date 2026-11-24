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
    r"(?:(?:ei|hey|oi|ou|ok|okey|o\s+que|oque|ola|ai|e|em|en|hem|hein|um)\s+)?(?:jarvis|jarves|jarbas)"
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


def run_voice_loop(
    model_dir: str = DEFAULT_VOSK_MODEL_DIR,
    backend_url: str = DEFAULT_BACKEND_URL,
) -> None:
    """Main hands-free loop: Vosk wake word -> Gemini STT/Chat -> Edge TTS -> Follow-up."""
    import sounddevice as sd
    from vosk import KaldiRecognizer, Model

    if not os.path.isdir(model_dir):
        raise FileNotFoundError(
            f"Modelo Vosk não encontrado em '{model_dir}'. "
            "Execute scripts/Instalar-Neo.bat para baixar automaticamente."
        )

    sm = VoiceSessionStateMachine()
    stop_event = threading.Event()

    # Optional global Esc hotkey to interrupt speech immediately
    try:
        import keyboard

        keyboard.add_hotkey("esc", lambda: (stop_event.set(), sm.on_interrupt()))
        print("[Voice] Atalho global Esc ativo para interromper a fala.")
    except Exception as exc:
        print(f"[Voice] Aviso: atalho global Esc indisponível ({exc}).")

    print(f"[Voice] Carregando modelo offline Vosk de {model_dir}...")
    model = Model(model_dir)
    recognizer = KaldiRecognizer(model, SAMPLE_RATE)

    print("[Voice] Jarvis ouvindo em modo standby. Diga 'Jarvis' ou 'Ei Jarvis' para começar.")
    last_partial = ""

    while True:
        # 1. Wait for wake word while IDLE (keep a 1-second pre-buffer of PCM so speech in one breath isn't lost)
        if sm.state == VoiceState.IDLE:
            from collections import deque

            pre_buffer: deque[bytes] = deque(maxlen=4)
            captured_chunks: list[bytes] = []
            vosk_heard_command = ""

            with sd.RawInputStream(
                samplerate=SAMPLE_RATE, blocksize=4000, dtype="int16", channels=1
            ) as stream:
                while sm.state == VoiceState.IDLE:
                    data, _ = stream.read(4000)
                    raw_bytes = bytes(data)
                    pre_buffer.append(raw_bytes)
                    if recognizer.AcceptWaveform(raw_bytes):
                        text = json.loads(recognizer.Result()).get("text", "")
                    else:
                        text = json.loads(recognizer.PartialResult()).get("partial", "")

                    if text and text != last_partial:
                        last_partial = text
                        print(f"[Voice/Vosk] Ouvido: '{text}'")

                    cue = sm.on_wake_word(text)
                    if cue:
                        print(f"[Voice] Gatilho reconhecido ('{text}')! Captando comando sem fechar microfone...")
                        play_cue_async(cue)
                        captured_chunks.extend(pre_buffer)

                        # Continue reading on the SAME open stream until 1.6s of silence after speech
                        start_t = time.monotonic()
                        last_voice_t = start_t
                        speech_active = bool(extract_command_after_wake(text))
                        while True:
                            d2, _ = stream.read(4000)
                            b2 = bytes(d2)
                            captured_chunks.append(b2)
                            now_t = time.monotonic()
                            if recognizer.AcceptWaveform(b2):
                                t2 = json.loads(recognizer.Result()).get("text", "")
                            else:
                                t2 = json.loads(recognizer.PartialResult()).get("partial", "")
                            if t2 and t2 != last_partial:
                                last_partial = t2
                                print(f"[Voice/Vosk] Captando: '{t2}'")
                            if _pcm_rms(b2) >= 160.0:
                                speech_active = True
                                last_voice_t = now_t
                            if speech_active and (now_t - last_voice_t) >= 1.6:
                                break
                            if not speech_active and (now_t - start_t) >= 7.0:
                                break
                            if (now_t - start_t) >= 18.0:
                                break

                        final_vosk = json.loads(recognizer.FinalResult()).get("text", "") or last_partial
                        recognizer.Reset()
                        last_partial = ""
                        vosk_heard_command = extract_command_after_wake(final_vosk) or final_vosk
                        break

        # 2. Capture user utterance (initial from open stream or follow-up)
        if sm.state in (VoiceState.LISTENING, VoiceState.FOLLOWUP):
            if sm.state == VoiceState.FOLLOWUP:
                print(f"[Voice] Janela de resposta aberta por {sm.followup_seconds}s...")
                wav_bytes = record_until_silence(max_wait_seconds=sm.followup_seconds)
                vosk_heard_command = ""
            else:
                wav_bytes = _pcm_to_wav_bytes(captured_chunks) if captured_chunks else None

            if not wav_bytes and not vosk_heard_command:
                print("[Voice] Silêncio detectado, voltando ao modo standby.")
                play_cue_async(sm.on_silence_timeout())
                continue
            play_cue_async(sm.on_speech_captured(wav_bytes or b"inline"))

            # 3. Transcribe + Chat via Neo backend
            try:
                transcript = ""
                reply = ""
                if wav_bytes:
                    print("[Voice] Enviando áudio captado para o Gemini transcrever e responder...")
                    try:
                        transcript, reply = transcribe_and_chat(wav_bytes, backend_url=backend_url)
                        cleaned_tr = extract_command_after_wake(transcript)
                        if cleaned_tr:
                            transcript = cleaned_tr
                    except Exception as tr_err:
                        print(f"[Voice] Aviso na transcrição de áudio ({tr_err}), usando transcrição local Vosk...")

                if (not transcript or not reply) and vosk_heard_command:
                    cmd_txt = extract_command_after_wake(vosk_heard_command) or vosk_heard_command
                    if not matches_wake_phrase(cmd_txt) or len(cmd_txt.split()) > 2:
                        transcript = cmd_txt
                        print(f"[Voice] Consultando Gemini com texto captado: '{transcript}'")
                        reply = chat_with_text(transcript, backend_url=backend_url)

                if not transcript or not reply:
                    print("[Voice] Pedido vazio após o gatilho. Voltando ao standby.")
                    play_cue_async(sm.on_error("empty"))
                    continue
                print(f"[Voice] Você: {transcript}")
                print(f"[Voice] Neo: {reply}")
                sm.on_reply_ready(reply)

                # 4. Speak response aloud with Esc interrupt support
                audio_path = tts_engine.generate_audio(reply)
                if audio_path and os.path.exists(audio_path):
                    print(f"[Voice] Reproduzindo resposta em voz alta ({audio_path})...")
                    stop_event.clear()
                    interrupted = play_audio_interruptible(audio_path, stop_event)
                    if interrupted:
                        print("[Voice] Fala interrompida via Esc.")
                        sm.on_interrupt()
                    else:
                        print("[Voice] Fala concluída. Microfone reaberto para resposta contínua...")
                        sm.on_speaking_finished()
                else:
                    sm.on_speaking_finished()
            except Exception as exc:
                print(f"[Voice] Erro no ciclo de voz: {exc}")
                play_cue_async(sm.on_error(str(exc)))


def test_microphone_sample(duration_seconds: float = 3.0) -> dict:
    """Record a short sample from the default microphone, compute RMS volume, and test Vosk recognition."""
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

    heard_text = ""
    if os.path.isdir(DEFAULT_VOSK_MODEL_DIR):
        try:
            from vosk import KaldiRecognizer, Model

            model = Model(DEFAULT_VOSK_MODEL_DIR)
            rec = KaldiRecognizer(model, SAMPLE_RATE)
            for c in chunks:
                rec.AcceptWaveform(c)
            heard_text = (json.loads(rec.FinalResult()).get("text") or "").strip()
        except Exception as exc:
            heard_text = f"(erro Vosk: {exc})"

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
