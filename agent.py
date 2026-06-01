import os
import asyncio
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from contextlib import asynccontextmanager
import requests
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.hooks import policy

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
        "pwd", "whoami", "date", "status"
    ]
    tokens = cmd.strip().split()
    if not tokens:
        return True
    first_word = tokens[0].lower()
    if first_word in ["ls", "cat", "grep", "find", "pwd", "whoami", "date"]:
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
            res = requests.post("http://localhost:3303/ask", json={"command": cmd}, headers=headers, timeout=600)
            if res.status_code == 200:
                approved = res.json().get("approved", False)
                print(f"[Agent Policy] Approval result for '{cmd}': {approved}")
                return approved
        except Exception as e:
            print(f"[Agent Policy] Error requesting WhatsApp approval: {e}")
        return False
        
    return await loop.run_in_executor(None, post)

# System Prompt for Neo
SYSTEM_PROMPT = """Você é o Neo, o assistente pessoal de IA do Marcello.
Você vive no Zorin OS dele e tem acesso ao terminal.

PERSONALIDADE:
- Parceiro, sênior e descontraído. Use emojis como 🚀, 🐳 ou 💻 ocasionalmente.
- Seu foco principal é ajudar Marcello com seus projetos em ~/Documentos/www.
- Você é expert em PHP, Node.js, Python e Docker.

Você responderá no chat privado do Marcello consigo mesmo.
Você tem ferramentas disponíveis para visualizar/editar arquivos e rodar comandos no terminal. Use-as sempre que necessário para resolver os problemas de programação dele.
"""

policies = [
    # 1. Ask user via WhatsApp for unsafe commands
    policy.ask_user("run_command", handler=whatsapp_approval_handler, when=lambda args: not is_safe_command(args), name="ask_unsafe_commands"),
    # 2. Allow safe commands
    policy.allow("run_command", when=is_safe_command, name="allow_safe_commands"),
    # 3. Allow all other built-in tools (file view, edit, list_dir, etc.)
    policy.allow_all()
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_instance
    home_dir = os.path.expanduser("~")
    app_data_dir = os.path.join(home_dir, ".gemini", "antigravity", "brain")
    config = LocalAgentConfig(
        system_instructions=SYSTEM_PROMPT,
        policies=policies,
        app_data_dir=app_data_dir,
    )
    print("Starting Antigravity Agent...")
    async with Agent(config) as active_agent:
        agent_instance = active_agent
        print("Antigravity Agent is ready!")
        yield
    print("Antigravity Agent shut down.")

app = FastAPI(title="Neo Antigravity Agent Backend", lifespan=lifespan)

@app.post("/chat")
async def chat_endpoint(payload: ChatPayload, x_neo_token: str = Header(None)):
    if x_neo_token != os.getenv("INTERNAL_API_KEY"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    global agent_instance
    if not agent_instance:
        raise HTTPException(status_code=503, detail="Agent is not ready yet")
    try:
        print(f"[Agent] Received message: {payload.message}")
        response = await agent_instance.chat(payload.message)
        reply_text = await response.text()
        print(f"[Agent] Response generated: {reply_text[:100]}...")
        return {"response": reply_text}
    except Exception as e:
        print(f"[Agent] Error during chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
