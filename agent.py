import os
import asyncio
import json
import subprocess
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
import requests
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

from memory import store_memory, retrieve_context
from email_tools import EMAIL_TOOLS, DEFAULT_ACCOUNTS_FILE, build_adapter_from_entry
import tts_engine


# ── Rate limiter ──────────────────────────────────────────────────────────────
import time
from collections import defaultdict



class RateLimiter:
    """Simple in-memory sliding-window rate limiter.

    Tracks requests per client key (session ID or IP) and returns True
    if the request is allowed, False if rate-limited.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        """Check if a request from this key should be allowed.
        Returns True if allowed, False if rate-limited.
        """
        now = time.time()
        cutoff = now - self.window_seconds
        bucket = self._buckets[key]

        # Remove expired timestamps
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)

        if len(bucket) >= self.max_requests:
            return False

        bucket.append(now)
        return True

    def remaining(self, key: str) -> int:
        """Return how many requests remain in the current window."""
        now = time.time()
        cutoff = now - self.window_seconds
        bucket = self._buckets.get(key, [])
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        return max(0, self.max_requests - len(bucket))


chat_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


# ── Security helpers ──────────────────────────────────────────────────────────
def _bridge_base_url() -> str:
    """Base URL do serviço de aprovação (WhatsApp bridge OU neo-cli)."""
    bridge_host = os.getenv("BRIDGE_HOST", "localhost")
    bridge_port = os.getenv("BRIDGE_PORT", "3303")
    return f"http://{bridge_host}:{bridge_port}"


def is_safe_command(args: dict) -> bool:
    """Return True if the command is safe to auto-approve."""
    cmd = args.get("CommandLine", "")
    cmd_lower = cmd.lower()

    # Block shell chaining and I/O redirection
    for char in [">", "&&", ";", "|", "`", "$", "(", ")", "<", "&"]:
        if char in cmd_lower:
            return False

    # Block path traversal and sensitive directories
    if ".." in cmd or ".ssh" in cmd or "/etc" in cmd:
        return False

    tokens = cmd.strip().split()
    if not tokens:
        return True
    first_word = tokens[0].lower()

    # Whitelist of safe first words
    if first_word in ["ls", "cat", "grep", "find", "pwd", "whoami", "date",
                       "node", "npm", "python", "python3"]:
        return True

    # Whitelist of safe multi-word prefixes
    for prefix in ["git status", "git log", "git diff", "docker ps", "docker logs"]:
        if cmd.startswith(prefix):
            return True

    return False


async def whatsapp_approval_handler(command: str) -> bool:
    """Ask the user on WhatsApp whether to allow the given command."""
    print(f"[Agent Policy] Requesting approval for command: {command}")

    loop = asyncio.get_event_loop()
    def post():
        try:
            headers = {"X-Neo-Token": os.getenv("INTERNAL_API_KEY", "")}
            res = requests.post(
                f"{_bridge_base_url()}/ask",
                json={"command": command},
                headers=headers,
                timeout=600,
            )
            if res.status_code == 200:
                approved = res.json().get("approved", False)
                print(f"[Agent Policy] Approval result: {approved}")
                return approved
        except Exception as e:
            print(f"[Agent Policy] Error requesting WhatsApp approval: {e}")
        return False

    return await loop.run_in_executor(None, post)


SYSTEM_PROMPT = """Você é o Neo, um assistente pessoal de IA autônomo (nível engenheiro de software).
Você tem acesso ao terminal do sistema hospedeiro. O nome do usuário e o sistema operacional devem ser inferidos pelo ambiente.

PERSONALIDADE:
- Parceiro, sênior e descontraído. Use emojis como 🚀, 🐳 ou 💻 ocasionalmente.
- Seu foco principal é resolver problemas de programação e gerenciar projetos no ambiente do usuário.
- Você é expert em PHP, Node.js, Python e Docker.

REGRAS CRÍTICAS PARA AÇÃO (MUITO IMPORTANTE):
1. NUNCA responda apenas dizendo "Vou fazer", "Posso fazer" ou "Certo".
2. Você DEVE invocar as ferramentas disponíveis (como executar comandos no terminal, criar/editar arquivos) IMEDIATAMENTE para concluir a tarefa solicitada na mesma resposta.
3. Aja como um agente autônomo: se um comando falhar, analise o erro, corrija e tente novamente antes de responder.
4. Você só deve responder com texto para o usuário APÓS ter usado as ferramentas necessárias para concluir a tarefa, ou se precisar de informações que você não consiga obter sozinho.

METODOLOGIA SDD (SPEC-DRIVEN DEVELOPMENT):
- Ao criar novas funcionalidades ou refatorações complexas em um projeto, consulte o harness em `.sdd-agentic-flow/`.
- Siga a ordem metodológica: Especifique (.specs/features/) -> crie os prompts das tarefas -> implemente com testes (TDD/evidências) -> valide a solução.
- Para orientações de skills locais do sdd-agentic-flow, consulte `.sdd-agentic-flow/usage.md` ou execute `npx sdd-agentic-flow doctor`."""


ASSISTANT_SYSTEM_PROMPT = """Você é o Jarvis, um assistente pessoal por voz gentil, claro e eficiente em português do Brasil.
Você ajuda a pessoa no dia a dia no computador (especialmente na leitura, busca e resposta de e-mails e documentos) usando linguagem natural.

ESTILO DE RESPOSTA PARA VOZ (MUITO IMPORTANTE):
- Suas respostas serão lidas em voz alta. Nunca use emojis, asteriscos, marcações de markdown, tabelas ou listas com símbolos.
- Use frases curtas, diretas e naturais de ouvir.
- Para e-mails ou documentos longos, faça primeiro um resumo objetivo (remetente, assunto e ponto principal) e pergunte se a pessoa quer ouvir na íntegra ou responder.
- Se um pedido puder se referir a mais de uma conta (por exemplo, Gmail ou Outlook), pergunte de forma simples qual conta ela prefere ou ofereça verificar ambas.

REGRAS DE AÇÃO E SEGURANÇA:
1. Quando precisar consultar e-mails ou arquivos, use as ferramentas disponíveis imediatamente antes de responder.
2. Nunca envie ou responda um e-mail sem antes ler em voz alta o destinatário, o assunto e o texto do rascunho e receber confirmação explícita da pessoa.
3. Nunca invente informações que não estejam nos e-mails ou documentos consultados."""


VALID_PROFILES = ("dev", "assistant")


def get_active_profile() -> str:
    """Return the active Neo profile ('dev' or 'assistant'), defaulting to 'dev'."""
    raw = os.getenv("NEO_PROFILE", "dev").strip().lower()
    return raw if raw in VALID_PROFILES else "dev"


def get_system_prompt(profile: str | None = None) -> str:
    """Return the system instruction matching the requested or active profile."""
    resolved = (profile or get_active_profile()).strip().lower()
    if resolved == "assistant":
        return ASSISTANT_SYSTEM_PROMPT
    return SYSTEM_PROMPT


DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
FALLBACK_GEMINI_MODELS = (
    "gemini-3.8-flash",
    "gemini-3.8-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)


def _extract_suggested_model(error_text: str) -> str | None:
    """Extract replacement model name if Google 404 says 'use models/gemini-...'."""
    import re
    match = re.search(r"use\s+models/(gemini-[a-zA-Z0-9._-]+)", error_text or "", re.IGNORECASE)
    return match.group(1) if match else None


def get_llm_config(api_key: str | None = None) -> dict:
    """Centralized BYOK / provider config seam for Gemini, Grok fallback, and future gateways."""
    return {
        "gemini_api_key": api_key or os.getenv("GEMINI_API_KEY"),
        "grok_api_key": os.getenv("GROK_API_KEY"),
        "base_url": os.getenv("NEO_LLM_BASE_URL") or None,
        "model_name": os.getenv("NEO_GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
    }


# ── Tool implementations ──────────────────────────────────────────────────────

def run_command(CommandLine: str) -> str:
    """Execute a command in the system terminal and return its output."""
    if not CommandLine or not CommandLine.strip():
        return "(comando vazio — nada a executar)"
    try:
        result = subprocess.run(
            CommandLine,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30000,
        )
        output = result.stdout or result.stderr or "(no output)"
        return output.strip()[:2000]  # Truncate to save tokens
    except subprocess.TimeoutExpired:
        return "Erro: comando excedeu o tempo limite de 30 segundos."
    except Exception as e:
        return f"Erro ao executar comando: {e}"


def _is_safe_path(file_path: str) -> bool:
    """Block access to sensitive system paths."""
    resolved = os.path.realpath(os.path.expanduser(file_path))
    blocked_parts = [".ssh", "/etc", "/root", "/boot", "/sys"]
    for part in blocked_parts:
        if part in resolved:
            return False
    return True


def view_file(file_path: str) -> str:
    """Read the contents of a file at the given path."""
    if not _is_safe_path(file_path):
        return "⚠️ Acesso negado: caminho bloqueado por segurança."
    try:
        with open(os.path.expanduser(file_path), "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return content[:2000] or "(empty file)"
    except Exception as e:
        return f"Erro ao ler arquivo: {e}"


def edit_file(file_path: str, content: str) -> str:
    """Create or overwrite a file at the given path with the provided content."""
    if not _is_safe_path(file_path):
        return "⚠️ Acesso negado: caminho bloqueado por segurança."
    try:
        expanded = os.path.expanduser(file_path)
        os.makedirs(os.path.dirname(expanded) or ".", exist_ok=True)
        with open(expanded, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Arquivo salvo: {file_path}"
    except Exception as e:
        return f"Erro ao salvar arquivo: {e}"


def list_directory(path: str = ".") -> str:
    """List the files and directories inside a given folder path."""
    try:
        expanded = os.path.expanduser(path)
        entries = os.listdir(expanded)
        dirs = sorted(e for e in entries if os.path.isdir(os.path.join(expanded, e)))
        files = sorted(e for e in entries if os.path.isfile(os.path.join(expanded, e)))
        result = f"📁 {len(dirs)} pastas, 📄 {len(files)} arquivos em {path}\n"
        if dirs:
            result += "\nPastas:\n" + "\n".join(f"  📁 {d}/" for d in dirs)
        if files:
            result += "\n\nArquivos:\n" + "\n".join(f"  📄 {f}" for f in files)
        return result[:2000]
    except Exception as e:
        return f"Erro ao listar diretório: {e}"


# ── Gemini tool definitions ───────────────────────────────────────────────────
TOOLS = [
    run_command,
    view_file,
    edit_file,
    list_directory,
]

ASSISTANT_SAFE_TOOLS = [
    view_file,
    list_directory,
    *EMAIL_TOOLS,
]


def get_tools_for_profile(profile: str | None = None) -> list:
    """Return the allowed tool list for the given profile (INV-1: no shell/edit in assistant)."""
    resolved = (profile or get_active_profile()).strip().lower()
    if resolved == "assistant":
        return list(ASSISTANT_SAFE_TOOLS)
    tools = list(TOOLS)
    if os.getenv("NEO_EMAIL_ENABLED", "false").lower() == "true":
        tools.extend(EMAIL_TOOLS)
    return tools


# ── NeoAgent ──────────────────────────────────────────────────────────────────
class NeoAgent:
    """Wraps the Google Generative AI SDK with tool-calling + security policies."""

    def __init__(self, api_key: str | None = None, profile: str | None = None):
        self.profile = (profile or get_active_profile()).strip().lower()
        if self.profile not in VALID_PROFILES:
            self.profile = "dev"

        llm_cfg = get_llm_config(api_key=api_key)
        effective_key = llm_cfg["gemini_api_key"]
        model_name = llm_cfg["model_name"]
        tools = get_tools_for_profile(self.profile)
        self._allowed_tool_names = {fn.__name__ for fn in tools}
        self._tool_map = {fn.__name__: fn for fn in tools}

        genai.configure(api_key=effective_key, transport="rest")
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=get_system_prompt(self.profile),
            tools=tools,
        )
        self.chat = self.model.start_chat(history=[])
        print(
            f"[NeoAgent] Initialized (profile={self.profile}, model={model_name}, "
            f"api_key={'set' if effective_key else 'None'})"
        )

    async def chat_send(self, message: str) -> str:
        """Send a message through the function-calling loop and return the final text."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_chat, message)

    def _sync_chat(self, message: str) -> str:
        """Synchronous function-calling loop with max-iteration guard."""
        max_turns = 8
        for turn in range(max_turns):
            response = self.chat.send_message(message)

            if not response.candidates:
                break

            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts:
                break

            part = candidate.content.parts[0]

            # If the model returns text, we're done
            if part.text:
                return part.text

            # If the model requests a function call
            if part.function_call:
                fc = part.function_call
                fn_name = fc.name
                fn_args = {k: v for k, v in fc.args.items()}
                print(f"[NeoAgent] Function call: {fn_name}({fn_args})")

                result = self._execute_function(fn_name, fn_args)

                # Send result back and continue the loop
                message = genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fn_name,
                        response={"result": result},
                    )
                )
                continue

            break  # Safety: empty part

        return "Desculpe, não consegui processar sua solicitação após várias tentativas. Pode reformular?"

    def _execute_function(self, fn_name: str, fn_args: dict) -> str:
        """Execute a tool function by name with args. Called by both sync and streaming paths."""
        if fn_name not in self._allowed_tool_names:
            return f"Ação não permitida no perfil '{self.profile}': '{fn_name}'."

        if fn_name == "run_command":
            command = fn_args.get("CommandLine", "")
            if not is_safe_command({"CommandLine": command}):
                print(f"[NeoAgent] Unsafe command, requesting approval: {command}")
                approved = self._ask_sync(command)
                if not approved:
                    return "❌ Comando bloqueado pelo usuário."
                else:
                    return run_command(CommandLine=command)
            else:
                return run_command(CommandLine=command)
        elif fn_name in self._tool_map:
            return self._tool_map[fn_name](**fn_args)
        else:
            return f"Erro: ferramenta desconhecida '{fn_name}'"

    def _sync_chat_stream(self, message: str):
        """Generator that yields (type, data) tuples — streams text from Gemini as it arrives.

        Yields:
            ("text", str) — a chunk of generated text
            ("status", str) — a status update (e.g., "executing: run_command")
            ("done", None) — stream complete
        """
        max_turns = 8
        for turn in range(max_turns):
            response = self.chat.send_message(message, stream=True)

            text_buffer = ""
            function_call = None

            for chunk in response:
                if not chunk.candidates:
                    continue
                candidate = chunk.candidates[0]
                if not candidate.content or not candidate.content.parts:
                    continue
                for part in candidate.content.parts:
                    if part.text:
                        text_buffer += part.text
                        yield ("text", part.text)
                    if part.function_call:
                        function_call = part.function_call

            if function_call:
                fc = function_call
                fn_name = fc.name
                fn_args = {k: v for k, v in fc.args.items()}
                print(f"[NeoAgent/Stream] Function call: {fn_name}({fn_args})")
                yield ("status", f"⚡ Executando: {fn_name}...")

                result = self._execute_function(fn_name, fn_args)

                # Send result back and continue the loop
                message = genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fn_name,
                        response={"result": result},
                    )
                )
                continue

            # No function call — done
            if text_buffer:
                break
            break

        yield ("done", None)

    def _ask_sync(self, command: str) -> bool:
        """Synchronous HTTP call to the bridge for approval."""
        try:
            headers = {"X-Neo-Token": os.getenv("INTERNAL_API_KEY", "")}
            res = requests.post(
                f"{_bridge_base_url()}/ask",
                json={"command": command},
                headers=headers,
                timeout=600,
            )
            if res.status_code == 200:
                return res.json().get("approved", False)
        except Exception as e:
            print(f"[NeoAgent] Sync approval error: {e}")
        return False

    def clear_history(self):
        """Start a fresh chat session, discarding accumulated history."""
        self.chat = self.model.start_chat(history=[])
        print("[NeoAgent] History cleared.")

    def load_history(self, stored_messages: list[dict]) -> None:
        """Replay stored messages into a fresh Gemini chat so the conversation can continue.

        Accepts a list of dicts with 'role' ('user' or 'assistant') and 'content' (text).
        Function-call details are stripped (only text is preserved) — the model will
        have the text context without knowing the exact tool invocations.
        """
        history_parts = []
        for msg in stored_messages:
            role = "user" if msg["role"] == "user" else "model"
            history_parts.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        self.chat = self.model.start_chat(history=history_parts)
        print(f"[NeoAgent] Loaded history: {len(stored_messages)} messages ({len(stored_messages)//2} turns)")

    @property
    def conversation_id(self) -> str:
        """Return a stable identifier for this session (for compatibility)."""
        return str(id(self.chat))


# ── AgentManager ──────────────────────────────────────────────────────────────
class AgentManager:
    MAX_MESSAGES_PER_SESSION = 50  # reset context after this many turns

    def __init__(self):
        self.agent: NeoAgent | None = None
        self.api_key: str | None = None
        self.message_count = 0
        self.lock = asyncio.Lock()

    async def get_agent(self, api_key: str | None = None) -> NeoAgent:
        async with self.lock:
            key_changed = self.api_key != api_key
            session_expired = self.message_count >= self.MAX_MESSAGES_PER_SESSION

            if self.agent is None or key_changed or session_expired:
                if session_expired:
                    print(f"[Agent] Session limit reached ({self.MAX_MESSAGES_PER_SESSION} msgs). "
                          "Starting fresh context.")
                    self.message_count = 0
                self.api_key = api_key
                await self._start_agent()

            self.message_count += 1
            return self.agent

    async def _start_agent(self):
        print(f"[Agent] Initializing new NeoAgent (API Key present: {self.api_key is not None})...")
        new_agent = NeoAgent(api_key=self.api_key)
        self.agent = new_agent
        print(f"[Agent] Agent initialized (conversation_id: {new_agent.conversation_id})")

    async def recreate_agent(self):
        async with self.lock:
            print("[Agent] Recreating agent due to connection issues...")
            self.agent = None
            await self._start_agent()

    async def close(self):
        print("[Agent] Shutting down AgentManager...")
        self.agent = None


agent_manager = AgentManager()


# ── FastAPI app ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Neo backend starting up (WhatsApp-only mode)...")
    yield
    await agent_manager.close()

app = FastAPI(title="Neo Gemini Backend", lifespan=lifespan)

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")


def _require_token(x_neo_token: str | None = None) -> None:
    """Validate X-Neo-Token header. Raises 401 if invalid."""
    if not INTERNAL_API_KEY or not x_neo_token or x_neo_token != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


class TranscribePayload(BaseModel):
    data: str
    mimeType: str = "audio/ogg"


class ChatPayload(BaseModel):
    message: str


@app.post("/chat")
async def chat_endpoint(
    payload: ChatPayload,
    x_gemini_api_key: str = Header(None),
    x_neo_token: str = Header(None),
):
    _require_token(x_neo_token)

    rate_key = x_neo_token or "unknown"
    if not chat_rate_limiter.check(rate_key):
        raise HTTPException(
            status_code=429,
            detail="Limite de requisições excedido. Máx: 10/min. Aguarde e tente novamente.",
        )

    try:
        augmented_message, target_api_key = await _prepare_chat_context(
            payload, x_gemini_api_key
        )

        is_first_init = agent_manager.agent is None
        if is_first_init:
            print("[Agent] First request: initializing agent...")

        print(f"[Agent] Received message: {payload.message}")

        # ── Fallback chain closure ──
        async def call_fallback_chain():
            print("[Agent] Quota/Tokens exceeded. Iniciando chain de fallback...")
            gemini_key = target_api_key or os.getenv("GEMINI_API_KEY")

            # Fallback 2: Iterate through Flash / Flash-Lite models via direct REST HTTP (handles 503 high demand & 429)
            if gemini_key:
                active_prompt = get_system_prompt(get_active_profile())
                for fb_model in FALLBACK_GEMINI_MODELS:
                    print(f"[Agent] Tentando Fallback REST: {fb_model}...")
                    try:
                        gemini_url = (
                            "https://generativelanguage.googleapis.com/v1beta/models/"
                            f"{fb_model}:generateContent?key={gemini_key}"
                        )
                        headers = {"Content-Type": "application/json"}
                        data = {
                            "systemInstruction": {"parts": [{"text": active_prompt}]},
                            "contents": [{"parts": [{"text": augmented_message}]}],
                        }
                        loop = asyncio.get_event_loop()
                        res = await loop.run_in_executor(
                            None, lambda u=gemini_url: requests.post(u, json=data, headers=headers, timeout=30)
                        )
                        if res.status_code == 200:
                            try:
                                text_resp = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                                os.environ["NEO_GEMINI_MODEL"] = fb_model
                                return text_resp
                            except Exception:
                                pass
                        else:
                            print(f"[Agent] {fb_model} falhou com status {res.status_code}: {res.text[:160]}")
                    except Exception as e:
                        print(f"[Agent] Erro na requisição de {fb_model}: {e}")

            # Fallback 3: Grok
            grok_api_key = os.getenv("GROK_API_KEY")
            if grok_api_key:
                print("[Agent] Tentando Fallback 3: Grok...")
                try:
                    grok_url = "https://api.x.ai/v1/chat/completions"
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {grok_api_key}",
                    }
                    data = {
                        "model": "grok-4.5",
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": augmented_message},
                        ],
                    }
                    loop = asyncio.get_event_loop()
                    res = await loop.run_in_executor(
                        None, lambda: requests.post(grok_url, json=data, headers=headers, timeout=60)
                    )
                    if res.status_code == 200:
                        return "⚠️ *Aviso: Usando servidor de emergência Grok.* ⚠️\n\n" + res.json()["choices"][0]["message"]["content"]
                    else:
                        print(f"[Agent] Erro no Grok: {res.status_code} - {res.text}")
                except Exception as e:
                    print(f"[Agent] Grok fallback failed: {e}")
            else:
                print("[Agent] GROK_API_KEY não configurada no .env. Pulando fallback Grok.")

            return ("⚠️ *Aviso do Sistema:* Minha cota de uso da API principal esgotou e os "
                    "servidores reserva (Grok/1.5-Flash) também falharam ou estão sem saldo. "
                    "Por favor, tente novamente mais tarde.")

        # ── Main ──
        try:
            agent_instance = await agent_manager.get_agent(api_key=target_api_key)
            if is_first_init:
                print("[Agent] Agent initialized successfully!")
            response = await agent_instance.chat_send(augmented_message)
            reply_text = response
        except Exception as chat_err:
            err_str = str(chat_err).lower()
            print(f"[Agent] Error during chat: {chat_err}")

            is_quota_error = (
                "429" in err_str
                or "503" in err_str
                or "404" in err_str
                or "high demand" in err_str
                or "overloaded" in err_str
                or "no longer available" in err_str
                or "quota" in err_str
                or "exhausted" in err_str
                or "billing" in err_str
                or "resource exhausted" in err_str
                or "rate limit" in err_str
            )

            is_connection_error = (
                "connection" in err_str
                or "closed" in err_str
                or "deadline" in err_str
                or "timeout" in err_str
                or "unavailable" in err_str
            )

            if is_quota_error:
                reply_text = await call_fallback_chain()
            elif is_connection_error:
                print("[Agent] Recreating agent due to connection error and retrying...")
                await agent_manager.recreate_agent()
                agent_instance = await agent_manager.get_agent(api_key=target_api_key)
                try:
                    response = await agent_instance.chat_send(augmented_message)
                    reply_text = response
                except Exception as retry_err:
                    err_str2 = str(retry_err).lower()
                    is_retry_quota = (
                        "429" in err_str2
                        or "quota" in err_str2
                        or "exhausted" in err_str2
                        or "billing" in err_str2
                    )
                    if is_retry_quota:
                        reply_text = await call_fallback_chain()
                    else:
                        raise retry_err
            else:
                raise chat_err

        store_memory(payload.message, reply_text)

        print(f"[Agent] Response generated: {reply_text[:100]}...")
        return {"response": reply_text}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Agent] Error during chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Shared helpers ────────────────────────────────────────────────────────────

async def _prepare_chat_context(payload: ChatPayload, x_gemini_api_key: str | None):
    """Build augmented message with RAG context. Auth is done by callers before calling this."""
    target_api_key = x_gemini_api_key
    if target_api_key:
        target_api_key = target_api_key.strip()
        if not target_api_key:
            target_api_key = None
    else:
        target_api_key = None

    past_context = retrieve_context(payload.message)
    augmented_message = payload.message
    if past_context:
        augmented_message = f"{payload.message}\n{past_context}"

    return augmented_message, target_api_key


# ── Audio transcription endpoint (for bridge) ──────────────────────────────────

@app.post("/transcribe")
async def transcribe_audio(
    payload: TranscribePayload,
    x_neo_token: str = Header(None),
):
    """Transcribe audio using Gemini. Accepts base64-encoded audio data + MIME type.
    Used by the WhatsApp bridge as an alternative to the JS SDK.
    """
    _require_token(x_neo_token)

    try:
        import base64 as b64

        # Configure Gemini (may already be configured by NeoAgent, but ensure it is)
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key, transport="rest")

        audio_bytes = b64.b64decode(payload.data)
        prompt = "Por favor, transcreva o audio desta mensagem em portugues e retorne APENAS o texto da transcricao literal de forma limpa, sem comentarios ou explicacoes."

        candidates = list(dict.fromkeys([get_llm_config()["model_name"], *FALLBACK_GEMINI_MODELS]))
        response = None
        last_err = None
        while candidates:
            candidate = candidates.pop(0)
            try:
                model = genai.GenerativeModel(model_name=candidate)
                response = model.generate_content([
                    prompt,
                    {"mime_type": payload.mimeType, "data": audio_bytes},
                ])
                os.environ["NEO_GEMINI_MODEL"] = candidate
                break
            except Exception as err:
                last_err = err
                err_str = str(err)
                suggested = _extract_suggested_model(err_str)
                if suggested and suggested not in candidates and suggested != candidate:
                    candidates.insert(0, suggested)
                if not any(code in err_str.lower() for code in ("404", "503", "429", "high demand", "overloaded", "unavailable")):
                    break
        if response is None and last_err is not None:
            raise last_err

        if not response or not response.text:
            return {"transcription": "", "error": "Empty response"}

        print(f"[Transcribe] Audio transcribed: {len(response.text)} chars")
        return {"transcription": response.text.strip()}

    except Exception as e:
        print(f"[Transcribe] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e)[:300])


# ── SSE Streaming endpoint (true streaming) ───────────────────────────────────

@app.post("/chat/stream")
async def chat_stream(
    payload: ChatPayload,
    x_gemini_api_key: str = Header(None),
    x_neo_token: str = Header(None),
):
    """Streams the Gemini response in real-time via SSE.

    Unlike the previous version, this uses Gemini's native streaming
    (stream=True on send_message) so chunks arrive as the model generates them.
    Function calls interrupt the stream momentarily and resume afterward.

    Protocol — each line is SSE format:
      data: {"status": "thinking"}
      data: {"status": "executing", "detail": "run_command: ls -la"}
      data: {"chunk": "Olá"}
      data: {"chunk": "! Tud"}
      data: {"chunk": "o bem"}
      data: {"done": true}
    """
    _require_token(x_neo_token)

    rate_key = x_neo_token or "unknown"
    if not chat_rate_limiter.check(rate_key):
        raise HTTPException(
            status_code=429,
            detail="Limite de requisições excedido. Máx: 10/min. Aguarde e tente novamente.",
        )

    augmented_message, target_api_key = await _prepare_chat_context(
        payload, x_gemini_api_key
    )

    is_first_init = agent_manager.agent is None
    if is_first_init:
        print("[Agent] First request: initializing agent...")

    print(f"[Agent/Stream] Received: {payload.message}")

    async def event_generator():
        loop = asyncio.get_event_loop()
        try:
            # Send immediate status
            yield f"data: {json.dumps({'status': 'thinking'})}\n\n"

            agent_instance = await agent_manager.get_agent(api_key=target_api_key)
            if is_first_init:
                print("[Agent] Agent initialized successfully!")

            # ── True streaming via generator ──
            # We bridge the sync generator into async via a Queue
            queue: asyncio.Queue = asyncio.Queue()

            def run_stream():
                """Run the sync generator in a thread and push items to the queue."""
                try:
                    for chunk_type, data in agent_instance._sync_chat_stream(augmented_message):
                        loop.call_soon_threadsafe(queue.put_nowait, (chunk_type, data))
                except Exception as e:
                    print(f"[Agent/Stream] Generator error: {e}")
                    loop.call_soon_threadsafe(queue.put_nowait, ("error", str(e)[:200]))
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

            # Start the streaming thread
            stream_task = loop.run_in_executor(None, run_stream)

            # Read from the queue and yield SSE events
            accumulated_text = ""
            while True:
                chunk_type, data = await queue.get()
                if chunk_type == "done":
                    break
                elif chunk_type == "error":
                    yield f"data: {json.dumps({'error': data})}\n\n"
                    break
                elif chunk_type == "text":
                    accumulated_text += data
                    yield f"data: {json.dumps({'chunk': data})}\n\n"
                elif chunk_type == "status":
                    yield f"data: {json.dumps({'status': 'executing', 'detail': data})}\n\n"

            await stream_task

            # Store memory
            if accumulated_text:
                store_memory(payload.message, accumulated_text)

            yield f"data: {json.dumps({'done': True})}\n\n"
            print(f"[Agent/Stream] Streamed {len(accumulated_text)} chars from Gemini.")

        except Exception as e:
            print(f"[Agent/Stream] Error: {e}")
            yield f"data: {json.dumps({'error': str(e)[:200]})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Conversation reset endpoint (used by neo-cli / desktop) ────────────────────

@app.post("/reset")
async def reset_conversation(
    x_neo_token: str = Header(None),
):
    """Clear the agent's conversation history so the next message starts fresh."""
    _require_token(x_neo_token)

    async with agent_manager.lock:
        if agent_manager.agent is not None:
            agent_manager.agent.clear_history()
            agent_manager.message_count = 0
            print("[Agent] Conversation reset via /reset")
            return {"status": "ok", "message": "Contexto de conversa reiniciado."}
        else:
            return {"status": "ok", "message": "Nenhum agente ativo para reiniciar."}


# ── Local Accessible Setup Wizard (/setup — localhost only, INV-3) ────────────

import sys as _sys

_APP_DATA_DIR = (
    os.path.dirname(_sys.executable)
    if getattr(_sys, "frozen", False)
    else os.path.dirname(__file__)
)
_BUNDLE_DIR = getattr(_sys, "_MEIPASS", _APP_DATA_DIR) if getattr(_sys, "frozen", False) else _APP_DATA_DIR

SETUP_ENV_PATH = os.path.join(_APP_DATA_DIR, ".env")
SETUP_ACCOUNTS_PATH = DEFAULT_ACCOUNTS_FILE
SETUP_UI_PATH = (
    os.path.join(_APP_DATA_DIR, "setup_ui.html")
    if os.path.exists(os.path.join(_APP_DATA_DIR, "setup_ui.html"))
    else os.path.join(_BUNDLE_DIR, "setup_ui.html")
)


def _mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def _read_env_file(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            values[k.strip()] = v.strip()
    return values


def _write_env_file(path: str, updates: dict[str, str]) -> None:
    existing = _read_env_file(path)
    existing.update({k: str(v) for k, v in updates.items() if v is not None})
    if not existing.get("INTERNAL_API_KEY"):
        import secrets
        existing["INTERNAL_API_KEY"] = secrets.token_hex(16)
    lines = [f"{k}={v}" for k, v in existing.items()]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


class SetupSavePayload(BaseModel):
    gemini_api_key: str | None = None
    profile: str = "assistant"
    tts_voice: str = "pt-BR-FranciscaNeural"
    followup_seconds: int = 8
    accounts: list[dict] | None = None


class SetupTestLLMPayload(BaseModel):
    gemini_api_key: str | None = None


class SetupTestEmailPayload(BaseModel):
    account: dict


class SetupTestVoicePayload(BaseModel):
    voice: str = "pt-BR-FranciscaNeural"


@app.get("/setup", response_class=HTMLResponse)
async def setup_page():
    """Serve the high-contrast accessible Setup Wizard UI (localhost only)."""
    with open(SETUP_UI_PATH, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.get("/setup/status")
async def setup_status():
    """Return masked setup status — NEVER exposes plaintext API keys or passwords (INV-3)."""
    env_vals = _read_env_file(SETUP_ENV_PATH)
    gemini_key = env_vals.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
    profile = env_vals.get("NEO_PROFILE") or get_active_profile()
    tts_voice = env_vals.get("NEO_TTS_VOICE") or os.getenv("NEO_TTS_VOICE", "pt-BR-FranciscaNeural")
    followup = int(env_vals.get("NEO_FOLLOWUP_SECONDS") or os.getenv("NEO_FOLLOWUP_SECONDS", "8"))

    safe_accounts = []
    if os.path.exists(SETUP_ACCOUNTS_PATH):
        try:
            with open(SETUP_ACCOUNTS_PATH, "r", encoding="utf-8") as f:
                raw_accounts = json.load(f).get("accounts", [])
            for a in raw_accounts:
                safe_accounts.append(
                    {
                        "id": a.get("id", ""),
                        "label": a.get("label", ""),
                        "type": a.get("type", "imap"),
                        "provider": a.get("provider", ""),
                        "imap_host": a.get("imap_host", ""),
                        "smtp_host": a.get("smtp_host", ""),
                        "username": a.get("username", ""),
                        "has_password": bool(a.get("password") or a.get("access_token")),
                    }
                )
        except Exception:
            pass

    wa_connected = False
    try:
        token = env_vals.get("INTERNAL_API_KEY") or os.getenv("INTERNAL_API_KEY", "")
        r = requests.get(f"{_bridge_base_url()}/status", headers={"X-Neo-Token": token}, timeout=2)
        if r.status_code == 200:
            wa_connected = bool(r.json().get("connected", False))
    except Exception:
        pass

    return {
        "gemini_configured": bool(gemini_key),
        "gemini_key_masked": _mask_secret(gemini_key),
        "profile": profile,
        "tts_voice": tts_voice,
        "followup_seconds": followup,
        "accounts": safe_accounts,
        "outlook_desktop_supported": os.name == "nt",
        "whatsapp_connected": wa_connected,
    }


@app.post("/setup/save")
async def setup_save(payload: SetupSavePayload):
    """Persist BYOK settings to .env and email accounts to email_accounts.json."""
    global INTERNAL_API_KEY

    env_updates: dict[str, str] = {
        "NEO_PROFILE": payload.profile if payload.profile in VALID_PROFILES else "assistant",
        "NEO_VOICE_ENABLED": "true",
        "NEO_TTS_VOICE": payload.tts_voice,
        "NEO_FOLLOWUP_SECONDS": str(max(3, min(int(payload.followup_seconds), 30))),
    }
    if payload.gemini_api_key:
        env_updates["GEMINI_API_KEY"] = payload.gemini_api_key.strip()
    if os.getenv("NEO_GEMINI_MODEL"):
        env_updates["NEO_GEMINI_MODEL"] = os.getenv("NEO_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    _write_env_file(SETUP_ENV_PATH, env_updates)
    saved_env = _read_env_file(SETUP_ENV_PATH)
    for k, v in saved_env.items():
        os.environ[k] = v
    INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

    if payload.accounts is not None:
        # Preserve existing stored password/token when UI sends account without re-entering secret
        existing_by_id: dict[str, dict] = {}
        if os.path.exists(SETUP_ACCOUNTS_PATH):
            try:
                with open(SETUP_ACCOUNTS_PATH, "r", encoding="utf-8") as f:
                    for item in json.load(f).get("accounts", []):
                        existing_by_id[str(item.get("id", ""))] = item
            except Exception:
                pass

        merged_accounts = []
        for acct in payload.accounts:
            entry = dict(acct)
            prev = existing_by_id.get(str(entry.get("id", "")), {})
            if not entry.get("password") and prev.get("password"):
                entry["password"] = prev["password"]
            if not entry.get("access_token") and prev.get("access_token"):
                entry["access_token"] = prev["access_token"]
            entry.pop("has_password", None)
            merged_accounts.append(entry)

        with open(SETUP_ACCOUNTS_PATH, "w", encoding="utf-8") as f:
            json.dump({"accounts": merged_accounts}, f, indent=2, ensure_ascii=False)

    # Reset active agent so new profile/key takes effect immediately
    async with agent_manager.lock:
        agent_manager.agent = None
        agent_manager.message_count = 0

    return {"ok": True, "message": "Tudo salvo! O Neo Assistente já está pronto para uso."}


@app.post("/setup/test-llm")
def setup_test_llm(payload: SetupTestLLMPayload):
    """Validate a BYOK Gemini API key via fast REST HTTPS (10s timeout) with 503 resilience."""
    key = (payload.gemini_api_key or "").strip() or os.getenv("GEMINI_API_KEY")
    if not key:
        return {"ok": False, "message": "Cole a chave do Gemini antes de testar."}

    candidates = list(dict.fromkeys([get_llm_config()["model_name"], *FALLBACK_GEMINI_MODELS]))
    last_err = ""
    saw_503 = False

    while candidates:
        candidate = candidates.pop(0)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent?key={key}"
        body = {"contents": [{"parts": [{"text": "Responda apenas: OK"}]}]}
        try:
            res = requests.post(url, json=body, timeout=10)
            if res.status_code == 200:
                os.environ["NEO_GEMINI_MODEL"] = candidate
                genai.configure(api_key=key, transport="rest")
                return {
                    "ok": True,
                    "message": f"Conexão com o Gemini ({candidate}) funcionando perfeitamente!",
                }
            if res.status_code == 503:
                saw_503 = True
            err_msg = res.text
            try:
                err_msg = res.json().get("error", {}).get("message", res.text)
            except Exception:
                pass
            last_err = f"{res.status_code} {err_msg}"
            if res.status_code in (400, 403) and "api_key_invalid" in res.text.lower():
                break
            suggested = _extract_suggested_model(last_err)
            if suggested and suggested not in candidates and suggested != candidate:
                candidates.insert(0, suggested)
        except Exception as exc:
            last_err = str(exc)

    # Fallback validation: if models returned 503 high demand, verify key against /v1beta/models
    if saw_503:
        try:
            models_res = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                timeout=8,
            )
            if models_res.status_code == 200:
                genai.configure(api_key=key, transport="rest")
                return {
                    "ok": True,
                    "message": "Chave do Gemini válida! (Servidores gratuitos do Google em pico de demanda agora; fallback automático ativado).",
                }
        except Exception:
            pass

    return {"ok": False, "message": f"Não foi possível conectar ao Gemini: {last_err[:220]}"}


@app.post("/setup/test-email")
def setup_test_email(payload: SetupTestEmailPayload):
    """Test an email account configuration before saving."""
    try:
        adapter = build_adapter_from_entry(payload.account)
        ok, msg = adapter.test_connection()
        return {"ok": ok, "message": msg}
    except Exception as exc:
        return {"ok": False, "message": f"Falha ao testar e-mail: {str(exc)[:180]}"}


@app.post("/setup/test-voice")
def setup_test_voice(payload: SetupTestVoicePayload):
    """Generate and return a short PT-BR voice sample so the user can hear Jarvis."""
    os.environ["NEO_VOICE_ENABLED"] = "true"
    os.environ["NEO_TTS_VOICE"] = payload.voice or "pt-BR-FranciscaNeural"
    audio_path = tts_engine.generate_audio(
        "Olá! Eu sou o Jarvis, seu assistente por voz. Tudo pronto para começarmos."
    )
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=500, detail="Não foi possível gerar o áudio de teste.")
    media_type = "audio/mpeg" if audio_path.endswith(".mp3") else "audio/ogg"
    return FileResponse(audio_path, media_type=media_type)


@app.post("/setup/test-mic")
def setup_test_mic():
    """Record 3 seconds from the default microphone and report volume + Vosk wake-word recognition."""
    try:
        import voice_listener

        return voice_listener.test_microphone_sample(duration_seconds=3.0)
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Erro ao acessar o microfone: {str(exc)[:180]}",
        }


# ── In-App Auto-Updater from GitHub Releases (main -> Release -> /VERYSILENT) ─

GITHUB_LATEST_RELEASE_API = "https://api.github.com/repos/marcellopato/neo-js/releases/latest"
GITHUB_DIRECT_EXE_URL = "https://github.com/marcellopato/neo-js/releases/latest/download/Neo-Assistente-Setup.exe"


def _get_local_build_commit() -> str:
    for base in (_APP_DATA_DIR, _BUNDLE_DIR):
        info_path = os.path.join(base, "build_info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    return str(json.load(f).get("commit", ""))[:12]
            except Exception:
                pass
    return ""


@app.get("/setup/check-update")
def setup_check_update():
    """Check GitHub Releases for a newer Windows .exe build published from main."""
    import re
    local_commit = _get_local_build_commit()
    try:
        res = requests.get(GITHUB_LATEST_RELEASE_API, timeout=8)
        if res.status_code != 200:
            return {"ok": False, "update_available": False, "message": "Não foi possível consultar o GitHub."}
        data = res.json()
        body = data.get("body") or ""
        m = re.search(r"Commit:\s*([0-9a-fA-F]{7,40})", body)
        remote_commit = m.group(1)[:12] if m else ""
        published_at = data.get("published_at") or ""

        if local_commit and remote_commit:
            update_available = not remote_commit.startswith(local_commit[:7])
        else:
            update_available = bool(remote_commit)

        return {
            "ok": True,
            "update_available": update_available,
            "local_commit": local_commit or "desconhecido",
            "remote_commit": remote_commit or "latest",
            "published_at": published_at,
            "download_url": GITHUB_DIRECT_EXE_URL,
            "message": (
                f"Nova versão disponível ({remote_commit[:7]})!"
                if update_available
                else f"Seu Neo já está na versão mais recente ({local_commit[:7] or 'atual'})."
            ),
        }
    except Exception as exc:
        return {"ok": False, "update_available": False, "message": f"Erro ao verificar atualização: {exc}"}


@app.post("/setup/apply-update")
def setup_apply_update():
    """Start downloading the latest Neo-Assistente-Setup.exe with live progress and launch /SILENT installer."""
    import tempfile
    import threading

    if os.name != "nt":
        return {"ok": False, "message": "Atualização automática via .exe disponível apenas no Windows."}

    if _UPDATE_PROGRESS.get("stage") == "downloading":
        return {"ok": True, "message": _UPDATE_PROGRESS.get("message", "Download já em andamento...")}

    target_exe = os.path.join(tempfile.gettempdir(), "Neo-Assistente-Setup-Update.exe")
    _UPDATE_PROGRESS.update(
        {
            "stage": "downloading",
            "percent": 0,
            "downloaded_mb": 0.0,
            "total_mb": 0.0,
            "message": "Iniciando download da atualização no GitHub...",
        }
    )

    def _download_and_launch():
        try:
            with requests.get(GITHUB_DIRECT_EXE_URL, stream=True, timeout=180) as r:
                r.raise_for_status()
                total_bytes = int(r.headers.get("Content-Length") or 0)
                total_mb = round(total_bytes / (1024 * 1024), 1) if total_bytes else 97.5
                downloaded = 0
                with open(target_exe, "wb") as f:
                    for chunk in r.iter_content(chunk_size=131072):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        dl_mb = round(downloaded / (1024 * 1024), 1)
                        pct = min(99, int((downloaded * 100) / total_bytes)) if total_bytes else 50
                        _UPDATE_PROGRESS.update(
                            {
                                "stage": "downloading",
                                "percent": pct,
                                "downloaded_mb": dl_mb,
                                "total_mb": total_mb,
                                "message": f"Baixando atualização: {pct}% ({dl_mb} MB de {total_mb} MB)...",
                            }
                        )

            _UPDATE_PROGRESS.update(
                {
                    "stage": "installing",
                    "percent": 100,
                    "message": "Download 100% concluído! Abrindo instalador automático na tela e reiniciando o Neo...",
                }
            )
            print(f"[Updater] Download concluído em {target_exe}. Iniciando instalador /SILENT...")

            # Strip PyInstaller internal env vars so child installer & new NeoAssistente.exe start clean
            clean_env = {
                k: v
                for k, v in os.environ.items()
                if not k.startswith("_MEI") and k not in ("PYTHONPATH", "PYTHONHOME")
            }
            creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
                subprocess, "DETACHED_PROCESS", 0
            )
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "", target_exe, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                cwd=tempfile.gettempdir(),
                env=clean_env,
                creationflags=creation_flags,
                close_fds=True,
            )
            # Exit current NeoAssistente.exe after 1.5s so all file locks are released before Inno Setup copies files
            time.sleep(1.5)
            os._exit(0)
        except Exception as exc:
            print(f"[Updater] Erro na atualização: {exc}")
            _UPDATE_PROGRESS.update(
                {
                    "stage": "error",
                    "message": f"Falha ao atualizar: {str(exc)[:180]}",
                }
            )

    threading.Thread(target=_download_and_launch, daemon=True).start()
    return {"ok": True, "message": _UPDATE_PROGRESS["message"]}


_UPDATE_PROGRESS: dict = {
    "stage": "idle",
    "percent": 0,
    "downloaded_mb": 0.0,
    "total_mb": 0.0,
    "message": "",
}


@app.get("/setup/update-progress")
def setup_update_progress():
    """Return real-time download/install progress for the in-app updater."""
    return _UPDATE_PROGRESS


@app.get("/setup/logs")
def setup_logs():
    """Return the last 80 lines of neo-assistant.log and runtime diagnostics for easy remote monitoring."""
    import voice_listener

    log_path = os.path.join(_APP_DATA_DIR, "neo-assistant.log")
    lines: list[str] = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-80:]
        except Exception as exc:
            lines = [f"Erro ao ler log: {exc}"]
    else:
        lines = ["(Arquivo neo-assistant.log ainda vazio ou rodando em modo console)"]

    return {
        "ok": True,
        "commit": _get_local_build_commit() or "dev",
        "app_dir": _APP_DATA_DIR,
        "vosk_model_dir": voice_listener.DEFAULT_VOSK_MODEL_DIR,
        "vosk_model_present": os.path.isdir(voice_listener.DEFAULT_VOSK_MODEL_DIR),
        "update_progress": _UPDATE_PROGRESS,
        "log_tail": "".join(lines),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
