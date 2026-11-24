import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import agent


class TestSetupWizard(unittest.TestCase):
    def test_get_setup_page_returns_accessible_html(self):
        resp = asyncio.run(agent.setup_page())
        self.assertEqual(resp.status_code, 200)
        body = resp.body.decode("utf-8")
        self.assertIn("Neo", body)
        self.assertIn("GEMINI", body.upper())
        self.assertIn("Gmail", body)
        self.assertIn("Outlook", body)

    def test_save_and_status_persist_config_and_mask_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            accounts_path = os.path.join(tmp, "email_accounts.json")

            with patch.object(agent, "SETUP_ENV_PATH", env_path), patch.object(
                agent, "SETUP_ACCOUNTS_PATH", accounts_path
            ):
                payload = agent.SetupSavePayload(
                    gemini_api_key="AIzaSySUPER_SECRET_TEST_KEY_9999",
                    profile="assistant",
                    tts_voice="pt-BR-FranciscaNeural",
                    followup_seconds=9,
                    accounts=[
                        {
                            "id": "gmail",
                            "label": "Gmail Pessoal",
                            "type": "imap",
                            "imap_host": "imap.gmail.com",
                            "smtp_host": "smtp.gmail.com",
                            "username": "maria@gmail.com",
                            "password": "APP_PASSWORD_SECRET_1234",
                        }
                    ],
                )
                save_res = asyncio.run(agent.setup_save(payload))
                self.assertTrue(save_res["ok"])
                self.assertTrue(os.path.exists(env_path))
                self.assertTrue(os.path.exists(accounts_path))

                # INV-3: /setup/status must NEVER leak plaintext keys or email passwords
                status = asyncio.run(agent.setup_status())
                status_json = json.dumps(status)
                self.assertTrue(status["gemini_configured"])
                self.assertNotIn("AIzaSySUPER_SECRET_TEST_KEY_9999", status_json)
                self.assertNotIn("APP_PASSWORD_SECRET_1234", status_json)
                self.assertEqual(status["profile"], "assistant")
                self.assertEqual(len(status["accounts"]), 1)
                self.assertEqual(status["accounts"][0]["label"], "Gmail Pessoal")

    def test_setup_test_email_uses_adapter_connection_check(self):
        fake_adapter = MagicMock()
        fake_adapter.test_connection.return_value = (True, "Conexão verificada com sucesso.")

        with patch("agent.build_adapter_from_entry", return_value=fake_adapter):
            payload = agent.SetupTestEmailPayload(
                account={
                    "id": "gmail",
                    "label": "Gmail",
                    "type": "imap",
                    "imap_host": "imap.gmail.com",
                    "smtp_host": "smtp.gmail.com",
                    "username": "maria@gmail.com",
                    "password": "secret",
                }
            )
            res = agent.setup_test_email(payload)
            self.assertTrue(res["ok"])
            self.assertIn("sucesso", res["message"].lower())


if __name__ == "__main__":
    unittest.main()
