import unittest
from unittest.mock import MagicMock, patch


class TestVoiceListener(unittest.TestCase):
    def test_wake_phrase_matching_variants(self):
        import voice_listener as vl

        self.assertTrue(vl.matches_wake_phrase("ei neo"))
        self.assertTrue(vl.matches_wake_phrase("Oi, Neo! Lê meus emails"))
        self.assertTrue(vl.matches_wake_phrase("ok neo"))
        self.assertFalse(vl.matches_wake_phrase("bom dia maria"))
        self.assertFalse(vl.matches_wake_phrase(""))

    def test_state_machine_full_conversational_cycle_and_followup(self):
        import voice_listener as vl

        sm = vl.VoiceSessionStateMachine(followup_seconds=8)
        self.assertEqual(sm.state, vl.VoiceState.IDLE)

        # Wake word -> LISTENING
        cue = sm.on_wake_word("ei neo")
        self.assertEqual(sm.state, vl.VoiceState.LISTENING)
        self.assertEqual(cue, "start")

        # Speech captured -> PROCESSING
        cue = sm.on_speech_captured(b"fake-wav-bytes")
        self.assertEqual(sm.state, vl.VoiceState.PROCESSING)
        self.assertEqual(cue, "processing")

        # Reply ready -> SPEAKING
        sm.on_reply_ready("Você tem 2 e-mails novos. Quer ouvir os do Gmail?")
        self.assertEqual(sm.state, vl.VoiceState.SPEAKING)

        # Playback finished -> FOLLOWUP (no need to repeat "Ei Neo")
        sm.on_speaking_finished()
        self.assertEqual(sm.state, vl.VoiceState.FOLLOWUP)

        # User responds during follow-up -> PROCESSING directly
        cue = sm.on_speech_captured(b"sim-leia-o-gmail")
        self.assertEqual(sm.state, vl.VoiceState.PROCESSING)
        self.assertEqual(cue, "processing")

        # Next reply finishes -> FOLLOWUP -> silence timeout -> IDLE
        sm.on_reply_ready("Primeiro e-mail da Porto Seguro.")
        sm.on_speaking_finished()
        self.assertEqual(sm.state, vl.VoiceState.FOLLOWUP)

        cue = sm.on_silence_timeout()
        self.assertEqual(sm.state, vl.VoiceState.IDLE)
        self.assertIsNone(cue)

    def test_interrupt_stops_speaking_immediately(self):
        import voice_listener as vl

        sm = vl.VoiceSessionStateMachine()
        sm.on_wake_word("ei neo")
        sm.on_speech_captured(b"wav")
        sm.on_reply_ready("E-mail muito longo...")
        self.assertEqual(sm.state, vl.VoiceState.SPEAKING)

        sm.on_interrupt()
        self.assertEqual(sm.state, vl.VoiceState.IDLE)

    def test_processing_error_returns_to_idle_with_error_cue(self):
        import voice_listener as vl

        sm = vl.VoiceSessionStateMachine()
        sm.on_wake_word("oi neo")
        sm.on_speech_captured(b"wav")
        cue = sm.on_error("timeout")
        self.assertEqual(sm.state, vl.VoiceState.IDLE)
        self.assertEqual(cue, "error")

    def test_transcribe_and_chat_calls_backend_endpoints(self):
        import voice_listener as vl

        mock_transcribe = MagicMock()
        mock_transcribe.status_code = 200
        mock_transcribe.json.return_value = {"transcription": "lê meus e-mails"}

        mock_chat = MagicMock()
        mock_chat.status_code = 200
        mock_chat.json.return_value = {"response": "Você tem um e-mail da Porto Seguro."}

        with patch("voice_listener.requests.post", side_effect=[mock_transcribe, mock_chat]) as mock_post:
            transcript, reply = vl.transcribe_and_chat(
                b"RIFF....WAVE",
                backend_url="http://127.0.0.1:5000",
                internal_token="secret-token",
            )
            self.assertEqual(transcript, "lê meus e-mails")
            self.assertEqual(reply, "Você tem um e-mail da Porto Seguro.")
            self.assertEqual(mock_post.call_count, 2)
            self.assertTrue(mock_post.call_args_list[0].args[0].endswith("/transcribe"))
            self.assertTrue(mock_post.call_args_list[1].args[0].endswith("/chat"))


if __name__ == "__main__":
    unittest.main()
