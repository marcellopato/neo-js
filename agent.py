import os
import asyncio
import json
import subprocess
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
import requests
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

from memory import store_memory, retrieve_context


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


# ── NeoAgent ──────────────────────────────────────────────────────────────────
class NeoAgent:
    """Wraps the Google Generative AI SDK with tool-calling + security policies."""

    def __init__(self, api_key: str | None = None):
        effective_key = api_key or os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=effective_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_PROMPT,
            tools=TOOLS,
        )
        self.chat = self.model.start_chat(history=[])
        print(f"[NeoAgent] Initialized (model=gemini-2.5-flash, api_key={'set' if effective_key else 'None'})")

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
        elif fn_name == "view_file":
            return view_file(**fn_args)
        elif fn_name == "edit_file":
            return edit_file(**fn_args)
        elif fn_name == "list_directory":
            return list_directory(**fn_args)
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

            # Fallback 2: Gemini 1.5 Flash via direct HTTP
            if gemini_key:
                print("[Agent] Tentando Fallback 2: Gemini 1.5 Flash...")
                try:
                    gemini_url = (
                        "https://generativelanguage.googleapis.com/v1beta/models/"
                        f"gemini-1.5-flash:generateContent?key={gemini_key}"
                    )
                    headers = {"Content-Type": "application/json"}
                    data = {
                        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                        "contents": [{"parts": [{"text": augmented_message}]}],
                    }
                    loop = asyncio.get_event_loop()
                    res = await loop.run_in_executor(
                        None, lambda: requests.post(gemini_url, json=data, headers=headers, timeout=60)
                    )
                    if res.status_code == 200:
                        try:
                            text_resp = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                            return "⚠️ *Aviso: Limite do modelo principal excedido. Usando Gemini 1.5 Flash.* ⚠️\n\n" + text_resp
                        except Exception:
                            pass
                    else:
                        print(f"[Agent] Gemini 1.5 Flash falhou com status {res.status_code}: {res.text}")
                except Exception as e:
                    print(f"[Agent] Erro na requisição do Gemini 1.5 Flash: {e}")

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
            genai.configure(api_key=api_key)

        audio_bytes = b64.b64decode(payload.data)

        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
        )

        prompt = "Por favor, transcreva o audio desta mensagem em portugues e retorne APENAS o texto da transcricao literal de forma limpa, sem comentarios ou explicacoes."

        response = model.generate_content([
            prompt,
            {"mime_type": payload.mimeType, "data": audio_bytes},
        ])

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
