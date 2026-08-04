#!/bin/bash
# Reconstrói o GIF da instalação do Neo (assets/install-demo.gif).
#
# Cria um sandbox em /tmp, clona o repo, pré-aquece venv/node_modules
# (cópia local, sem rede) e roda o instalador REAL (`node install.js`)
# com stubs rápidos para pip/npm — o GIF mostra as mensagens do instalador
# sem esperar downloads.
#
# Uso:
#   scripts/record-install-demo.sh
# Env opcionais: SANDBOX=/caminho  REPO_URL=https://.../neo-js.git
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX="${SANDBOX:-/tmp/neo-install-demo}"
REPO_URL="${REPO_URL:-https://github.com/marcellopato/neo-js.git}"

echo "[record] Preparando sandbox em $SANDBOX ..."
rm -rf "$SANDBOX"
mkdir -p "$SANDBOX/home/bin"

echo "[record] Clonando $REPO_URL ..."
git clone --quiet --depth 1 "$REPO_URL" "$SANDBOX/demo"

echo "[record] Pré-aquecendo venv e node_modules (cópia local) ..."
cp -a "$ROOT/venv" "$SANDBOX/demo/venv"
cp -a "$ROOT/node_modules" "$SANDBOX/demo/node_modules"
rm -f "$SANDBOX/demo/.env"

# Sobrepõe arquivos LOCAIS do instalador (mesmo não commitados) sobre o clone
cp -a "$ROOT/install.js" "$ROOT/install-alias.js" "$ROOT/neo" "$SANDBOX/demo/"

# Stubs rápidos: o GIF mostra as mensagens do instalador, não o download.
cat > "$SANDBOX/demo/venv/bin/pip" <<'STUB'
#!/bin/bash
echo "Requirement already satisfied: pip in ./venv/lib/python3.12/site-packages (from pip)"
echo "Requirement already satisfied: fastapi, uvicorn, google-generativeai, requests, python-dotenv, qdrant-client[fastembed], gTTS, click (from -r requirements.txt)"
exit 0
STUB
chmod +x "$SANDBOX/demo/venv/bin/pip"

cat > "$SANDBOX/home/bin/npm" <<'STUB'
#!/bin/bash
echo "up to date in 1.234s"
echo "found 0 vulnerabilities"
exit 0
STUB
chmod +x "$SANDBOX/home/bin/npm"

echo "[record] Gravando e renderizando o GIF ..."
"$ROOT/venv/bin/python" -u "$ROOT/scripts/make-install-gif.py" \
    "$SANDBOX/demo" "$ROOT/assets/install-demo.gif" "$SANDBOX/home"

echo "[record] OK: $ROOT/assets/install-demo.gif"
