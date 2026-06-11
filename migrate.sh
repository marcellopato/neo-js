#!/bin/bash
cd "$(dirname "$0")"

echo "=================================================="
echo "    NEO.JS - ASSISTENTE DE MIGRAÇÃO (DOCKER)      "
echo "=================================================="
echo "A arquitetura do Neo mudou para 100% Docker."
echo "Limpando o cache antigo da sessão do WhatsApp (que incompatibiliza com a nova versão)..."

# Usa o docker temporário para deletar arquivos que possam ter ficado com permissão de root
docker run --rm -v $(pwd):/app -w /app alpine rm -rf .wwebjs_auth .wwebjs_cache
# Limpa arquivos com permissões locais também
rm -rf .wwebjs_auth .wwebjs_cache

echo "[Sucesso] Cache limpo! Agora você precisará escanear o QR Code mais uma vez."
echo "Iniciando a nova arquitetura..."

chmod +x start.sh
./start.sh
