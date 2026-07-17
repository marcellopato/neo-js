import os
import asyncio
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from contextlib import asynccontextmanager
import requests
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

from google.antigravity import Agent, LocalAgentConfig, types
from google.antigravity.hooks import policy
from memory import store_memory, retrieve_context
from tts_engine import generate_audio

class ChatPayload(BaseModel):
    message: str

# Global agent reference
agent_instance = None

def is_safe_command(args) -> bool:
    cmd = args.get("CommandLine", "")
    cmd_lower = cmd.lower()
    
    # If there is shell chaining or output writing/pipes, play safe
    for char in [">", "&&", ";", "|", "`", "$", "(", ")", "<", "&"]:
        if char in cmd_lower:
            return False
            
    if ".." in cmd or ".ssh" in cmd or "/etc" in cmd:
        return False
        
    safe_prefixes = [
        "ls", "git status", "git log", "git diff", "cat", 
        "docker ps", "docker logs", "grep", "find", 
        "pwd", "whoami", "date", "status", "node", "npm", "python", "python3"
    ]
    tokens = cmd.strip().split()
    if not tokens:
        return True
    first_word = tokens[0].lower()
    if first_word in ["ls", "cat", "grep", "find", "pwd", "whoami", "date", "node", "npm", "python", "python3"]:
        return True
    
    for prefix in ["git status", "git log", "git diff", "docker ps", "docker logs"]:
        if cmd.startswith(prefix):
            return True
            
    return False

async def whatsapp_approval_handler(tool_call):
    cmd = tool_call.arguments.get("CommandLine", "")
    print(f"[Agent Policy] Requesting approval for command: {cmd}")
    
    loop = asyncio.get_event_loop()
    def post():
        try:
            # We call the Node.js bridge to ask the user on WhatsApp
            headers = {"X-Neo-Token": os.getenv("INTERNAL_API_KEY", "")}
            bridge_host = os.getenv("BRIDGE_HOST", "localhost")
            res = requests.post(f"http://{bridge_host}:3303/ask", json={"command": cmd}, headers=headers, timeout=600)
            if res.status_code == 200:
                approved = res.json().get("approved", False)
                print(f"[Agent Policy] Approval result for '{cmd}': {approved}")
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
"""

policies = [
    # 1. Ask user via WhatsApp for unsafe commands
    policy.ask_user("run_command", handler=whatsapp_approval_handler, when=lambda args: not is_safe_command(args), name="ask_unsafe_commands"),
    # 2. Allow safe commands
    policy.allow("run_command", when=is_safe_command, name="allow_safe_commands"),
    # 3. Allow all other built-in tools (file view, edit, list_dir, etc.)
    policy.allow_all()
]

class AgentManager:
    MAX_MESSAGES_PER_SESSION = 10  # reset conversation context after this many turns

    def __init__(self):
        self.agent = None
        self.conversation_id = None
        self.api_key = None
        self.message_count = 0
        self.lock = asyncio.Lock()
        
    async def get_agent(self, api_key=None):
        async with self.lock:
            key_changed = self.api_key != api_key
            session_expired = self.message_count >= self.MAX_MESSAGES_PER_SESSION

            if self.agent is None or key_changed or session_expired:
                if session_expired:
                    print(f"[Agent] Session limit reached ({self.MAX_MESSAGES_PER_SESSION} msgs). Starting fresh context.")
                    self.conversation_id = None  # drop accumulated history
                    self.message_count = 0
                self.api_key = api_key
                await self._start_agent()

            self.message_count += 1
            return self.agent

    async def _start_agent(self):
        home_dir = os.path.expanduser("~")
        app_data_dir = os.path.join(home_dir, ".gemini", "antigravity", "brain")
        save_dir = os.path.join(app_data_dir, "conversations")
        os.makedirs(save_dir, exist_ok=True)
        
        config = LocalAgentConfig(
            model="gemini-2.5-flash",
            system_instructions=SYSTEM_PROMPT,
            policies=policies,
            app_data_dir=app_data_dir,
            save_dir=save_dir,
            conversation_id=self.conversation_id,
            api_key=self.api_key
        )
        
        print(f"Initializing new Agent instance (API Key present: {self.api_key is not None})...")
        new_agent = Agent(config)
        await new_agent.__aenter__()
        
        if self.agent is not None:
            try:
                await self.agent.__aexit__(None, None, None)
            except Exception as e:
                print(f"Error closing old agent: {e}")
                
        self.agent = new_agent
        self.conversation_id = new_agent.conversation_id
        print(f"Agent initialized successfully with conversation_id: {self.conversation_id}")

    async def recreate_agent(self):
        async with self.lock:
            if self.agent is not None:
                if self.agent.conversation_id:
                    self.conversation_id = self.agent.conversation_id
                print("Closing existing Agent instance due to connection issues...")
                try:
                    await self.agent.__aexit__(None, None, None)
                except Exception as e:
                    print(f"Error closing agent: {e}")
                self.agent = None
            
            # Restart agent
            await self._start_agent()

    async def close(self):
        async with self.lock:
            if self.agent is not None:
                print("Closing Agent instance...")
                try:
                    await self.agent.__aexit__(None, None, None)
                except Exception as e:
                    print(f"Error closing agent: {e}")
                self.agent = None

agent_manager = AgentManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Agent is initialized lazily on first /chat request
    # This allows the server to start immediately without blocking on WebSocket connection
    print("Neo backend starting up (agent will initialize on first request)...")
    yield
    print("Shutting down AgentManager...")
    await agent_manager.close()

app = FastAPI(title="Neo Antigravity Agent Backend", lifespan=lifespan)

@app.post("/chat")
async def chat_endpoint(
    payload: ChatPayload, 
    x_neo_token: str = Header(None),
    x_gemini_api_key: str = Header(None)
):
    if x_neo_token != os.getenv("INTERNAL_API_KEY"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        target_api_key = x_gemini_api_key
        if target_api_key:
            target_api_key = target_api_key.strip()
            if not target_api_key:
                target_api_key = None
        else:
            target_api_key = None

        is_first_init = agent_manager.agent is None
        if is_first_init:
            print("[Agent] First request: initializing Antigravity Agent...")
        agent_instance = await agent_manager.get_agent(api_key=target_api_key)
        if is_first_init:
            print("[Agent] Agent initialized successfully!")
        print(f"[Agent] Received message: {payload.message}")
        
        past_context = retrieve_context(payload.message)
        augmented_message = payload.message
        if past_context:
            augmented_message = f"{payload.message}\n{past_context}"
            
        try:
            response = await agent_instance.chat(augmented_message)
            reply_text = await response.text()
        except (types.AntigravityConnectionError, Exception) as chat_err:
            err_str = str(chat_err).lower()
            print(f"[Agent] Connection or WebSocket error during chat: {chat_err}")
            
            is_connection_error = (
                isinstance(chat_err, types.AntigravityConnectionError) or
                "connection" in err_str or
                "received 1000" in err_str or
                "closed" in err_str or
                "1006" in err_str or
                "1000" in err_str
            )
            
            if is_connection_error:
                print("[Agent] Recreating agent due to connection drop and retrying...")
                await agent_manager.recreate_agent()
                agent_instance = await agent_manager.get_agent(api_key=target_api_key)
                response = await agent_instance.chat(augmented_message)
                reply_text = await response.text()
            else:
                raise chat_err
        
        store_memory(payload.message, reply_text)
        
        # Gerar áudio
        audio_file = None
        try:
            audio_file = generate_audio(reply_text)
        except Exception as e:
            print(f"[Agent] Erro ao gerar áudio: {e}")
        
        print(f"[Agent] Response generated: {reply_text[:100]}...")
        return {"response": reply_text, "audio_file": audio_file}
    except Exception as e:
        print(f"[Agent] Error during chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
