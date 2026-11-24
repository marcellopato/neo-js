"""Multi-account email tools for Neo.JS (Gmail IMAP/SMTP + Outlook COM / Graph)."""

from __future__ import annotations

import email
import html
import imaplib
import json
import os
import re
import smtplib
from email.header import decode_header
from email.message import EmailMessage
from typing import Any

import requests

DEFAULT_ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "email_accounts.json")
MAX_EMAIL_BODY_CHARS = 3000


def html_to_plain_text(raw: str) -> str:
    """Convert HTML email content into clean, voice-friendly plain text."""
    if not raw:
        return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</?(p|div|li|tr|h[1-6]|table|section|article)\b[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            decoded.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(str(chunk))
    return "".join(decoded).strip()


def _extract_email_body(msg: email.message.Message) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            disposition = str(part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            ctype = part.get_content_type()
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if ctype == "text/plain":
                plain_parts.append(decoded)
            elif ctype == "text/html":
                html_parts.append(decoded)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                html_parts.append(decoded)
            else:
                plain_parts.append(decoded)

    if plain_parts:
        return "\n".join(plain_parts).strip()
    if html_parts:
        return html_to_plain_text("\n".join(html_parts))
    return "(sem conteúdo de texto)"


class EmailAccountAdapter:
    """Base interface for email backends."""

    name: str
    provider: str

    def list_messages(self, unread_only: bool = True, limit: int = 5) -> list[dict[str, Any]]:
        raise NotImplementedError

    def search_messages(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        raise NotImplementedError

    def read_message(self, email_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def send_message(self, to: str, subject: str, body: str) -> bool:
        raise NotImplementedError

    def test_connection(self) -> tuple[bool, str]:
        try:
            self.list_messages(unread_only=False, limit=1)
            return True, "Conexão verificada com sucesso."
        except Exception as exc:
            return False, str(exc)


class ImapSmtpAdapter(EmailAccountAdapter):
    """Stdlib IMAP/SMTP adapter — ideal for Gmail App Passwords and generic broker IMAP."""

    def __init__(
        self,
        name: str,
        imap_host: str,
        smtp_host: str,
        username: str,
        password: str,
        imap_port: int = 993,
        smtp_port: int = 465,
        provider: str = "imap",
    ):
        self.name = name
        self.provider = provider
        self.imap_host = imap_host
        self.imap_port = int(imap_port)
        self.smtp_host = smtp_host
        self.smtp_port = int(smtp_port)
        self.username = username
        self._password = password

    def _connect_imap(self) -> imaplib.IMAP4_SSL:
        conn = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        conn.login(self.username, self._password)
        conn.select("INBOX")
        return conn

    def _fetch_ids(self, conn: imaplib.IMAP4_SSL, ids: list[bytes], limit: int) -> list[dict[str, Any]]:
        selected = ids[-limit:][::-1]
        results = []
        for raw_id in selected:
            status, data = conn.fetch(raw_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if status != "OK" or not data or not data[0]:
                continue
            header_bytes = data[0][1] if isinstance(data[0], tuple) else b""
            msg = email.message_from_bytes(header_bytes)
            results.append(
                {
                    "id": raw_id.decode("ascii", errors="ignore"),
                    "sender": _decode_mime_header(msg.get("From")),
                    "subject": _decode_mime_header(msg.get("Subject")) or "(sem assunto)",
                    "date": _decode_mime_header(msg.get("Date")),
                }
            )
        return results

    def list_messages(self, unread_only: bool = True, limit: int = 5) -> list[dict[str, Any]]:
        conn = self._connect_imap()
        try:
            criteria = "UNSEEN" if unread_only else "ALL"
            status, data = conn.search(None, criteria)
            if status != "OK" or not data or not data[0]:
                return []
            ids = data[0].split()
            return self._fetch_ids(conn, ids, limit)
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def search_messages(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        conn = self._connect_imap()
        try:
            safe_q = query.replace('"', "").strip()
            status, data = conn.search(None, "TEXT", f'"{safe_q}"')
            if status != "OK" or not data or not data[0]:
                return []
            ids = data[0].split()
            return self._fetch_ids(conn, ids, limit)
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def read_message(self, email_id: str) -> dict[str, Any] | None:
        conn = self._connect_imap()
        try:
            status, data = conn.fetch(str(email_id), "(RFC822)")
            if status != "OK" or not data or not data[0]:
                return None
            raw_bytes = data[0][1] if isinstance(data[0], tuple) else b""
            msg = email.message_from_bytes(raw_bytes)
            return {
                "id": str(email_id),
                "sender": _decode_mime_header(msg.get("From")),
                "subject": _decode_mime_header(msg.get("Subject")) or "(sem assunto)",
                "date": _decode_mime_header(msg.get("Date")),
                "body": _extract_email_body(msg),
            }
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def send_message(self, to: str, subject: str, body: str) -> bool:
        message = EmailMessage()
        message["From"] = self.username
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        if self.smtp_port == 587:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self._password)
                server.send_message(message)
        else:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                server.login(self.username, self._password)
                server.send_message(message)
        return True


class OutlookComAdapter(EmailAccountAdapter):
    """Windows Classic Outlook Desktop adapter using local MAPI session (zero password)."""

    def __init__(self, name: str = "Outlook Desktop"):
        self.name = name
        self.provider = "outlook_com"

    def _get_inbox(self):
        import win32com.client  # Windows-only lazy import

        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        return outlook, namespace.GetDefaultFolder(6)  # 6 = olFolderInbox

    def list_messages(self, unread_only: bool = True, limit: int = 5) -> list[dict[str, Any]]:
        _, inbox = self._get_inbox()
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)
        if unread_only:
            items = items.Restrict("[UnRead] = true")
        results = []
        for item in items:
            if len(results) >= limit:
                break
            results.append(
                {
                    "id": str(getattr(item, "EntryID", "")),
                    "sender": str(getattr(item, "SenderName", "")),
                    "subject": str(getattr(item, "Subject", "(sem assunto)")),
                    "date": str(getattr(item, "ReceivedTime", "")),
                }
            )
        return results

    def search_messages(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        _, inbox = self._get_inbox()
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)
        q = query.lower()
        results = []
        for item in items:
            if len(results) >= limit:
                break
            subj = str(getattr(item, "Subject", ""))
            sender = str(getattr(item, "SenderName", ""))
            body = str(getattr(item, "Body", ""))
            if q in subj.lower() or q in sender.lower() or q in body.lower():
                results.append(
                    {
                        "id": str(getattr(item, "EntryID", "")),
                        "sender": sender,
                        "subject": subj or "(sem assunto)",
                        "date": str(getattr(item, "ReceivedTime", "")),
                    }
                )
        return results

    def read_message(self, email_id: str) -> dict[str, Any] | None:
        import win32com.client

        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        item = namespace.GetItemFromID(email_id)
        if not item:
            return None
        return {
            "id": str(email_id),
            "sender": str(getattr(item, "SenderName", "")),
            "subject": str(getattr(item, "Subject", "(sem assunto)")),
            "date": str(getattr(item, "ReceivedTime", "")),
            "body": str(getattr(item, "Body", "")).strip(),
        }

    def send_message(self, to: str, subject: str, body: str) -> bool:
        outlook, _ = self._get_inbox()
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.To = to
        mail.Subject = subject
        mail.Body = body
        mail.Send()
        return True


class OutlookGraphAdapter(EmailAccountAdapter):
    """Microsoft Graph REST adapter for Outlook.com / Microsoft 365 / New Outlook."""

    BASE_URL = "https://graph.microsoft.com/v1.0/me"

    def __init__(self, name: str, access_token: str):
        self.name = name
        self.provider = "outlook_graph"
        self._access_token = access_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def list_messages(self, unread_only: bool = True, limit: int = 5) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "$top": limit,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,receivedDateTime,isRead",
        }
        if unread_only:
            params["$filter"] = "isRead eq false"
        res = requests.get(f"{self.BASE_URL}/mailFolders/inbox/messages", headers=self._headers(), params=params, timeout=20)
        res.raise_for_status()
        out = []
        for m in res.json().get("value", []):
            sender_info = (m.get("from") or {}).get("emailAddress") or {}
            out.append(
                {
                    "id": m.get("id", ""),
                    "sender": sender_info.get("name") or sender_info.get("address", ""),
                    "subject": m.get("subject") or "(sem assunto)",
                    "date": m.get("receivedDateTime", ""),
                }
            )
        return out

    def search_messages(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        safe_q = query.replace('"', "").strip()
        params = {"$top": limit, "$search": f'"{safe_q}"', "$select": "id,subject,from,receivedDateTime"}
        res = requests.get(f"{self.BASE_URL}/messages", headers=self._headers(), params=params, timeout=20)
        res.raise_for_status()
        out = []
        for m in res.json().get("value", []):
            sender_info = (m.get("from") or {}).get("emailAddress") or {}
            out.append(
                {
                    "id": m.get("id", ""),
                    "sender": sender_info.get("name") or sender_info.get("address", ""),
                    "subject": m.get("subject") or "(sem assunto)",
                    "date": m.get("receivedDateTime", ""),
                }
            )
        return out

    def read_message(self, email_id: str) -> dict[str, Any] | None:
        res = requests.get(
            f"{self.BASE_URL}/messages/{email_id}",
            headers=self._headers(),
            params={"$select": "id,subject,from,receivedDateTime,body"},
            timeout=20,
        )
        if res.status_code == 404:
            return None
        res.raise_for_status()
        m = res.json()
        sender_info = (m.get("from") or {}).get("emailAddress") or {}
        body_obj = m.get("body") or {}
        raw_body = body_obj.get("content", "")
        if str(body_obj.get("contentType", "")).lower() == "html":
            raw_body = html_to_plain_text(raw_body)
        return {
            "id": m.get("id", ""),
            "sender": sender_info.get("name") or sender_info.get("address", ""),
            "subject": m.get("subject") or "(sem assunto)",
            "date": m.get("receivedDateTime", ""),
            "body": raw_body,
        }

    def send_message(self, to: str, subject: str, body: str) -> bool:
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            }
        }
        res = requests.post(f"{self.BASE_URL}/sendMail", headers=self._headers(), json=payload, timeout=20)
        res.raise_for_status()
        return True


def build_adapter_from_entry(entry: dict[str, Any]) -> EmailAccountAdapter:
    """Instantiate an EmailAccountAdapter from a config dictionary."""
    acct_type = str(entry.get("type", "imap")).strip().lower()
    label = entry.get("label") or entry.get("id") or "E-mail"
    if acct_type == "outlook_com":
        return OutlookComAdapter(name=label)
    if acct_type == "outlook_graph":
        return OutlookGraphAdapter(name=label, access_token=entry.get("access_token", ""))
    return ImapSmtpAdapter(
        name=label,
        imap_host=entry.get("imap_host", "imap.gmail.com"),
        smtp_host=entry.get("smtp_host", "smtp.gmail.com"),
        username=entry.get("username", ""),
        password=entry.get("password", ""),
        imap_port=int(entry.get("imap_port", 993)),
        smtp_port=int(entry.get("smtp_port", 465)),
        provider=entry.get("provider", acct_type),
    )


class EmailManager:
    """Coordinates multiple email accounts and enforces send confirmation (INV-2)."""

    def __init__(self, adapters: dict[str, EmailAccountAdapter] | None = None):
        self.adapters: dict[str, EmailAccountAdapter] = adapters or {}

    @classmethod
    def from_config_file(cls, config_path: str | None = None) -> "EmailManager":
        path = config_path or os.getenv("NEO_EMAIL_ACCOUNTS_FILE", DEFAULT_ACCOUNTS_FILE)
        adapters: dict[str, EmailAccountAdapter] = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for entry in data.get("accounts", []):
                    key = str(entry.get("id") or entry.get("label") or "").strip().lower()
                    if not key:
                        continue
                    adapters[key] = build_adapter_from_entry(entry)
            except Exception as exc:
                print(f"[EmailManager] Erro ao carregar contas de e-mail: {exc}")
        return cls(adapters=adapters)

    def _resolve_adapters(self, account: str) -> list[tuple[str, EmailAccountAdapter]]:
        if not self.adapters:
            return []
        target = (account or "all").strip().lower()
        if target in ("all", "todas", "todos", ""):
            return list(self.adapters.items())
        if target in self.adapters:
            return [(target, self.adapters[target])]
        # Fuzzy match by label or provider
        matched = [
            (k, a)
            for k, a in self.adapters.items()
            if target in k or target in a.name.lower() or target in getattr(a, "provider", "").lower()
        ]
        return matched

    def list_accounts(self) -> str:
        if not self.adapters:
            return "Nenhuma conta de e-mail está configurada no momento."
        lines = ["Contas de e-mail configuradas:"]
        for key, adapter in self.adapters.items():
            lines.append(f"- {adapter.name} (identificador: {key})")
        return "\n".join(lines)

    def list_emails(self, account: str = "all", unread_only: bool = True, limit: int = 5) -> str:
        selected = self._resolve_adapters(account)
        if not selected:
            return "Nenhuma conta de e-mail correspondente foi encontrada."

        limit = max(1, min(int(limit), 15))
        lines: list[str] = []
        for key, adapter in selected:
            try:
                msgs = adapter.list_messages(unread_only=unread_only, limit=limit)
            except Exception as exc:
                lines.append(f"Conta {adapter.name}: erro ao consultar ({exc}).")
                continue
            if not msgs:
                status_txt = "não lidos" if unread_only else "recentes"
                lines.append(f"Conta {adapter.name}: nenhum e-mail {status_txt}.")
                continue
            lines.append(f"Conta {adapter.name} ({len(msgs)} e-mail(s)):")
            for idx, m in enumerate(msgs, start=1):
                lines.append(
                    f"  {idx}. ID {m['id']} | De: {m['sender']} | Assunto: {m['subject']} | Data: {m.get('date', '')}"
                )
        return "\n".join(lines)

    def search_emails(self, query: str, account: str = "all", limit: int = 5) -> str:
        if not query or not query.strip():
            return "Informe um termo de busca para procurar nos e-mails."
        selected = self._resolve_adapters(account)
        if not selected:
            return "Nenhuma conta de e-mail correspondente foi encontrada."

        limit = max(1, min(int(limit), 15))
        lines: list[str] = []
        for key, adapter in selected:
            try:
                msgs = adapter.search_messages(query=query, limit=limit)
            except Exception as exc:
                lines.append(f"Conta {adapter.name}: erro na busca ({exc}).")
                continue
            if not msgs:
                continue
            lines.append(f"Resultados em {adapter.name}:")
            for idx, m in enumerate(msgs, start=1):
                lines.append(
                    f"  {idx}. ID {m['id']} | De: {m['sender']} | Assunto: {m['subject']} | Data: {m.get('date', '')}"
                )
        if not lines:
            return f"Nenhum e-mail encontrado para '{query}'."
        return "\n".join(lines)

    def read_email(self, email_id: str, account: str) -> str:
        selected = self._resolve_adapters(account)
        if not selected:
            return f"Conta de e-mail '{account}' não encontrada."
        _, adapter = selected[0]
        try:
            msg = adapter.read_message(email_id)
        except Exception as exc:
            return f"Erro ao ler o e-mail {email_id} na conta {adapter.name}: {exc}"
        if not msg:
            return f"E-mail {email_id} não encontrado na conta {adapter.name}."

        clean_body = html_to_plain_text(msg.get("body", ""))
        if len(clean_body) > MAX_EMAIL_BODY_CHARS:
            clean_body = clean_body[:MAX_EMAIL_BODY_CHARS] + "... (texto truncado)"
        return (
            f"Conta: {adapter.name}\n"
            f"De: {msg.get('sender', '')}\n"
            f"Assunto: {msg.get('subject', '')}\n"
            f"Data: {msg.get('date', '')}\n"
            f"Conteúdo:\n{clean_body}"
        )

    def send_email(
        self,
        account: str,
        to: str,
        subject: str,
        body: str,
        confirmed: bool = False,
    ) -> str:
        selected = self._resolve_adapters(account)
        if not selected:
            return f"Conta de e-mail '{account}' não encontrada."
        _, adapter = selected[0]

        # INV-2: Never transmit without explicit user confirmation
        if not confirmed:
            return (
                "Confirmação necessária antes de enviar o e-mail. "
                f"Conta: {adapter.name}. Para: {to}. Assunto: {subject}. "
                f"Mensagem: {body}. "
                "Pergunte ao usuário se confirma o envio e só chame send_email com confirmed=True após a confirmação."
            )

        try:
            adapter.send_message(to=to, subject=subject, body=body)
            return f"E-mail enviado com sucesso pela conta {adapter.name} para {to}."
        except Exception as exc:
            return f"Erro ao enviar e-mail pela conta {adapter.name}: {exc}"


def _default_manager() -> EmailManager:
    return EmailManager.from_config_file()


# ── Tool functions exposed to Gemini ──────────────────────────────────────────

def list_email_accounts() -> str:
    """List the configured email accounts (Gmail, Outlook, etc.) without exposing secrets."""
    return _default_manager().list_accounts()


def list_emails(account: str = "all", unread_only: bool = True, limit: int = 5) -> str:
    """List recent or unread emails from one account ('gmail', 'outlook', etc.) or 'all'."""
    return _default_manager().list_emails(account=account, unread_only=unread_only, limit=limit)


def search_emails(query: str, account: str = "all", limit: int = 5) -> str:
    """Search emails by sender, subject, or keyword across one or all configured accounts."""
    return _default_manager().search_emails(query=query, account=account, limit=limit)


def read_email(email_id: str, account: str) -> str:
    """Read the full plain-text content of a specific email by its ID and account."""
    return _default_manager().read_email(email_id=email_id, account=account)


def send_email(
    account: str,
    to: str,
    subject: str,
    body: str,
    confirmed: bool = False,
) -> str:
    """Send an email. MUST first be called with confirmed=False so the user confirms recipient, subject, and body."""
    return _default_manager().send_email(
        account=account,
        to=to,
        subject=subject,
        body=body,
        confirmed=confirmed,
    )


EMAIL_TOOLS = [
    list_email_accounts,
    list_emails,
    search_emails,
    read_email,
    send_email,
]
