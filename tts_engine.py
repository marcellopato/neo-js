import os
from gtts import gTTS
import uuid

# Configuration
USE_VOICE = os.getenv("NEO_VOICE_ENABLED", "true").lower() == "true"
AUDIO_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "audio_cache")

if not os.path.exists(AUDIO_OUTPUT_DIR):
    os.makedirs(AUDIO_OUTPUT_DIR)

def generate_audio(text: str) -> str:
    """
    Gera um arquivo de áudio a partir do texto e retorna o caminho do arquivo gerado.
    Retorna None se o recurso de voz estiver desativado.
    """
    if not USE_VOICE:
        return None
        
    clean_text = text.replace('*', '').replace('_', '')
    
    filename = f"neo_voice_{uuid.uuid4().hex[:8]}.ogg"
    filepath = os.path.join(AUDIO_OUTPUT_DIR, filename)
    
    try:
        # TODO: Quando quiser plugar o seu modelo XTTS/Coqui local (aquele do profile-neo.voicebox.zip),
        # você pode substituir este código do gTTS por uma chamada à API do seu modelo local
        # ou importando a biblioteca de inferência.
        
        print(f"[TTS] Gerando áudio via gTTS para: {filepath}")
        tts = gTTS(text=clean_text, lang='pt', tld='com.br')
        tts.save(filepath)
        
        return filepath
    except Exception as e:
        print(f"[TTS Error] Falha ao gerar áudio: {e}")
        return None
