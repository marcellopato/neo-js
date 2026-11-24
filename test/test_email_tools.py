import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock

import agent


class FakeEmailAdapter:
    def __init__(self, name, provider, messages):
        self.name = name
        self.provider = provider
        self._messages = messages
        self.sent = []

    def list_messages(self, unread_only=True, limit=5):
        items = [m for m in self._messages if (not unread_only or m.get("unread", True))]
        return items[:limit]

    def search_messages(self, query, limit=5):
        q = query.lower()
        items = [
            m
            for m in self._messages
            if q in m["subject"].lower()
            or q in m["sender"].lower()
            or q in m.get("body", "").lower()
        ]
        return items[:limit]

    def read_message(self, email_id):
        for m in self._messages:
            if str(m["id"]) == str(email_id):
                return m
        return None

    def send_message(self, to, subject, body):
        self.sent.append({"to": to, "subject": subject, "body": body})
        return True


class TestEmailTools(unittest.TestCase):
    def test_html_to_plain_text_strips_tags_styles_and_entities(self):
        import email_tools

        raw = (
            "<html><head><style>body{color:red;}</style></head>"
            "<body><p>Ol&aacute;, <b>Maria</b>!</p>"
            "<script>alert(1)</script><p>Ap&oacute;lice #123 aprovada.</p></body></html>"
        )
        clean = email_tools.html_to_plain_text(raw)
        self.assertIn("Olá, Maria!", clean)
        self.assertIn("Apólice #123 aprovada.", clean)
        self.assertNotIn("color:red", clean)
        self.assertNotIn("alert(1)", clean)
        self.assertNotIn("<p>", clean)

    def test_multi_account_list_search_and_read(self):
        import email_tools

        gmail = FakeEmailAdapter(
            "Gmail Pessoal",
            "gmail",
            [
                {
                    "id": "g1",
                    "sender": "Porto Seguro <contato@portoseguro.com.br>",
                    "subject": "Apólice renovada - João Silva",
                    "date": "2026-11-24 10:00",
                    "unread": True,
                    "body": "<p>Sua apólice foi renovada com sucesso.</p>",
                }
            ],
        )
        outlook = FakeEmailAdapter(
            "Outlook Corretora",
            "outlook",
            [
                {
                    "id": "o1",
                    "sender": "Bradesco Seguros <sinistro@bradesco.com.br>",
                    "subject": "Atualização de sinistro #442",
                    "date": "2026-11-24 11:15",
                    "unread": True,
                    "body": "O sinistro 442 entrou em análise.",
                }
            ],
        )
        mgr = email_tools.EmailManager(adapters={"gmail": gmail, "outlook": outlook})

        all_res = mgr.list_emails(account="all", unread_only=True, limit=5)
        self.assertIn("Porto Seguro", all_res)
        self.assertIn("Bradesco Seguros", all_res)

        gmail_only = mgr.list_emails(account="gmail", unread_only=True, limit=5)
        self.assertIn("Porto Seguro", gmail_only)
        self.assertNotIn("Bradesco Seguros", gmail_only)

        search_res = mgr.search_emails(query="sinistro", account="all", limit=5)
        self.assertIn("442", search_res)
        self.assertNotIn("Porto Seguro", search_res)

        read_res = mgr.read_email(email_id="g1", account="gmail")
        self.assertIn("renovada com sucesso", read_res)
        self.assertNotIn("<p>", read_res)

    def test_send_email_requires_explicit_confirmation(self):
        import email_tools

        gmail = FakeEmailAdapter("Gmail", "gmail", [])
        mgr = email_tools.EmailManager(adapters={"gmail": gmail})

        # INV-2: confirmed=False must NOT send
        unconfirmed = mgr.send_email(
            account="gmail",
            to="cliente@exemplo.com",
            subject="Cotação de seguro",
            body="Segue o valor atualizado.",
            confirmed=False,
        )
        self.assertEqual(len(gmail.sent), 0)
        self.assertIn("confirma", unconfirmed.lower())
        self.assertIn("cliente@exemplo.com", unconfirmed)

        # confirmed=True sends once
        confirmed = mgr.send_email(
            account="gmail",
            to="cliente@exemplo.com",
            subject="Cotação de seguro",
            body="Segue o valor atualizado.",
            confirmed=True,
        )
        self.assertEqual(len(gmail.sent), 1)
        self.assertEqual(gmail.sent[0]["to"], "cliente@exemplo.com")
        self.assertIn("enviado", confirmed.lower())

    def test_load_accounts_config_never_leaks_secrets(self):
        import email_tools

        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "email_accounts.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "accounts": [
                            {
                                "id": "gmail",
                                "label": "Gmail Pessoal",
                                "type": "imap",
                                "imap_host": "imap.gmail.com",
                                "smtp_host": "smtp.gmail.com",
                                "username": "maria@gmail.com",
                                "password": "SUPER_SECRET_APP_PASSWORD",
                            }
                        ]
                    },
                    f,
                )

            mgr = email_tools.EmailManager.from_config_file(cfg_path)
            summary = mgr.list_accounts()
            self.assertIn("Gmail Pessoal", summary)
            self.assertNotIn("SUPER_SECRET_APP_PASSWORD", summary)

    def test_assistant_profile_registers_email_tools_safely(self):
        tool_names = [fn.__name__ for fn in agent.get_tools_for_profile("assistant")]
        self.assertIn("list_email_accounts", tool_names)
        self.assertIn("list_emails", tool_names)
        self.assertIn("search_emails", tool_names)
        self.assertIn("read_email", tool_names)
        self.assertIn("send_email", tool_names)
        self.assertNotIn("run_command", tool_names)
        self.assertNotIn("edit_file", tool_names)


if __name__ == "__main__":
    unittest.main()
