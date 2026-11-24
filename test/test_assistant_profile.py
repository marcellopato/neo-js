import os
import unittest
from unittest.mock import patch, MagicMock

import agent


class TestAssistantProfile(unittest.TestCase):
    def test_default_profile_is_dev(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NEO_PROFILE", None)
            self.assertEqual(agent.get_active_profile(), "dev")

    def test_assistant_profile_env_normalization(self):
        with patch.dict(os.environ, {"NEO_PROFILE": "  ASSISTANT  "}):
            self.assertEqual(agent.get_active_profile(), "assistant")

        with patch.dict(os.environ, {"NEO_PROFILE": "unknown-mode"}):
            self.assertEqual(agent.get_active_profile(), "dev")

    def test_dev_profile_keeps_existing_tools(self):
        tool_names = [fn.__name__ for fn in agent.get_tools_for_profile("dev")]
        self.assertIn("run_command", tool_names)
        self.assertIn("edit_file", tool_names)
        self.assertIn("view_file", tool_names)
        self.assertIn("list_directory", tool_names)

    def test_assistant_profile_excludes_shell_and_file_write(self):
        # INV-1: assistant profile must NEVER expose run_command or edit_file
        tool_names = [fn.__name__ for fn in agent.get_tools_for_profile("assistant")]
        self.assertNotIn("run_command", tool_names)
        self.assertNotIn("edit_file", tool_names)
        self.assertIn("view_file", tool_names)
        self.assertIn("list_directory", tool_names)

    def test_assistant_system_prompt_is_voice_first_ptbr(self):
        prompt = agent.get_system_prompt("assistant")
        self.assertIn("voz", prompt.lower())
        self.assertIn("markdown", prompt.lower())
        self.assertIn("confirma", prompt.lower())
        self.assertNotEqual(prompt, agent.get_system_prompt("dev"))

    @patch("agent.genai.GenerativeModel")
    @patch("agent.genai.configure")
    def test_neo_agent_runtime_blocks_disallowed_tools_in_assistant_mode(
        self, mock_configure, mock_model_cls
    ):
        mock_model = MagicMock()
        mock_model_cls.return_value = mock_model

        neo = agent.NeoAgent(api_key="dummy-key", profile="assistant")
        self.assertEqual(neo.profile, "assistant")

        res_cmd = neo._execute_function("run_command", {"CommandLine": "whoami"})
        res_edit = neo._execute_function(
            "edit_file", {"file_path": "/tmp/x.txt", "content": "x"}
        )
        self.assertIn("não permitida", res_cmd.lower())
        self.assertIn("não permitida", res_edit.lower())

    def test_get_llm_config_byok_defaults_and_override(self):
        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "env-gemini-key",
                "GROK_API_KEY": "env-grok-key",
                "NEO_LLM_BASE_URL": "https://proxy.example.com",
            },
            clear=False,
        ):
            cfg = agent.get_llm_config()
            self.assertEqual(cfg["gemini_api_key"], "env-gemini-key")
            self.assertEqual(cfg["grok_api_key"], "env-grok-key")
            self.assertEqual(cfg["base_url"], "https://proxy.example.com")
            self.assertEqual(cfg["model_name"], "gemini-3.8-flash")

            cfg_override = agent.get_llm_config(api_key="header-key")
            self.assertEqual(cfg_override["gemini_api_key"], "header-key")

    def test_extract_suggested_model_from_404_message(self):
        err = (
            "404 This model models/gemini-2.5-flash is no longer available to new users. "
            "Please update your code to use models/gemini-3.8-flash for the latest features."
        )
        self.assertEqual(agent._extract_suggested_model(err), "gemini-3.8-flash")


class TestTTSEngine(unittest.TestCase):
    def test_sanitize_for_speech_removes_markdown_and_emojis(self):
        import tts_engine

        raw = "## Olá *Maria*! 🚀 Veja [o boleto](https://ex.com) e `codigo_1`."
        clean = tts_engine.sanitize_for_speech(raw)
        self.assertNotIn("*", clean)
        self.assertNotIn("#", clean)
        self.assertNotIn("`", clean)
        self.assertNotIn("🚀", clean)
        self.assertNotIn("https://ex.com", clean)
        self.assertIn("Olá Maria!", clean)
        self.assertIn("o boleto", clean)
        self.assertIn("codigo_1", clean)

    def test_generate_audio_uses_edge_tts_primarily(self):
        import tts_engine

        with patch.dict(
            os.environ,
            {
                "NEO_VOICE_ENABLED": "true",
                "NEO_TTS_VOICE": "pt-BR-FranciscaNeural",
                "NEO_TTS_RATE": "+10%",
            },
            clear=False,
        ):
            with patch.object(tts_engine, "_synthesize_edge_tts") as mock_edge, patch.object(
                tts_engine, "_synthesize_gtts"
            ) as mock_gtts:
                path = tts_engine.generate_audio("Olá *mundo* 🚀")
                self.assertIsNotNone(path)
                self.assertTrue(path.endswith(".mp3"))
                mock_edge.assert_called_once()
                args, _ = mock_edge.call_args
                self.assertEqual(args[0], "Olá mundo")
                self.assertEqual(args[2], "pt-BR-FranciscaNeural")
                self.assertEqual(args[3], "+10%")
                mock_gtts.assert_not_called()

    def test_generate_audio_falls_back_to_gtts_on_edge_error(self):
        import tts_engine

        with patch.dict(os.environ, {"NEO_VOICE_ENABLED": "true"}, clear=False):
            with patch.object(
                tts_engine, "_synthesize_edge_tts", side_effect=RuntimeError("edge offline")
            ) as mock_edge, patch.object(tts_engine, "_synthesize_gtts") as mock_gtts:
                path = tts_engine.generate_audio("Teste de fallback")
                self.assertIsNotNone(path)
                self.assertTrue(path.endswith(".ogg"))
                mock_edge.assert_called_once()
                mock_gtts.assert_called_once()


if __name__ == "__main__":
    unittest.main()
