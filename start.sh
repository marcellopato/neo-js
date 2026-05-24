#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

echo "[Start] Neo Hybrid Service is starting up..."

# Define cleanup function
cleanup() {
    echo "[Start] Shutting down subprocesses..."
    kill "$AGENT_PID" "$BRIDGE_PID" 2>/dev/null
    exit 0
}

# Trap signals
trap cleanup SIGINT SIGTERM EXIT

# Start Python Agent
echo "[Start] Starting Python Agent Backend..."
./venv/bin/python3 agent.py &
AGENT_PID=$!

# Wait a couple of seconds for FastAPI to bind
sleep 2

# Find node dynamically, check standard location first, and fallback to NVM
NODE_EXEC=$(which node)
if [ -z "$NODE_EXEC" ]; then
    if [ -f "$HOME/.nvm/nvm.sh" ]; then
        . "$HOME/.nvm/nvm.sh"
        NODE_EXEC=$(which node)
    fi
fi

if [ -z "$NODE_EXEC" ]; then
    # Fallback default if absolutely not found
    NODE_EXEC="node"
fi

$NODE_EXEC bridge.js &
BRIDGE_PID=$!

# Wait for subprocesses to exit
wait "$AGENT_PID" "$BRIDGE_PID"
