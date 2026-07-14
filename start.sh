#!/bin/bash
set -e
cd "$(dirname "$0")"
SCRIPT_DIR="$(pwd)"

echo "=========================================================="
echo "   Iniciando Neo.JS nativamente (sem Docker)              "
echo "=========================================================="

# Verifica e instala dependências Python
if [ ! -d "venv" ]; then
    echo "[Start] Criando ambiente virtual Python (venv)..."
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi

# Verifica e instala dependências Node.js
if [ ! -d "node_modules" ]; then
    echo "[Start] Instalando dependências do Node.js..."
    npm install
fi

# Encerra processos anteriores se existirem
if [ -f "$SCRIPT_DIR/backend.pid" ]; then
    OLD_PID=$(cat "$SCRIPT_DIR/backend.pid")
    kill "$OLD_PID" 2>/dev/null && echo "[Start] Backend anterior (PID $OLD_PID) encerrado." || true
    rm -f "$SCRIPT_DIR/backend.pid"
fi
if [ -f "$SCRIPT_DIR/bridge.pid" ]; then
    OLD_PID=$(cat "$SCRIPT_DIR/bridge.pid")
    kill "$OLD_PID" 2>/dev/null && echo "[Start] Bridge anterior (PID $OLD_PID) encerrada." || true
    rm -f "$SCRIPT_DIR/bridge.pid"
fi

# Inicia o backend Python com nohup (desvincula do terminal)
echo "[Start] Iniciando backend (agent.py)..."
nohup ./venv/bin/python agent.py >> backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$SCRIPT_DIR/backend.pid"

# Aguarda o backend subir
echo "[Start] Aguardando backend inicializar (porta 5000)..."
for i in $(seq 1 15); do
    sleep 1
    if ss -tlnp 2>/dev/null | grep -q ':5000'; then
        echo "[Start] ✅ Backend ativo na porta 5000 (PID: $BACKEND_PID)"
        break
    fi
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "[Start] ❌ ERRO: Backend falhou ao inicializar. Verifique backend.log:"
        tail -20 backend.log
        exit 1
    fi
    echo "[Start] Aguardando... ($i/15)"
done

if ! ss -tlnp 2>/dev/null | grep -q ':5000'; then
    echo "[Start] ❌ Timeout aguardando backend. Verifique backend.log"
    exit 1
fi

# Inicia a bridge Node.js com setsid
echo "[Start] Iniciando bridge (bridge.js)..."
nohup /home/marcello/.nvm/versions/node/v22.21.1/bin/node bridge.js >> output.log 2>&1 &
BRIDGE_PID=$!
echo $BRIDGE_PID > "$SCRIPT_DIR/bridge.pid"

echo ""
echo "=========================================================="
echo "   ✅ Neo está rodando em segundo plano!                   "
echo "   Backend PID: $BACKEND_PID  |  Bridge PID: $BRIDGE_PID  "
echo "   Logs: tail -f backend.log | tail -f output.log         "
echo "=========================================================="
