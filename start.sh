#!/bin/bash
cd "$(dirname "$0")"

echo "[Start] Neo Hybrid Service is starting up via Docker..."

# Verifica se o docker compose está disponível
if command -v docker-compose &> /dev/null; then
    docker-compose up -d --build
elif docker compose version &> /dev/null; then
    docker compose up -d --build
else
    echo "Erro: Docker e Docker Compose não encontrados. Por favor, instale-os primeiro."
    exit 1
fi

echo ""
echo "=========================================================="
echo "   O Neo está rodando em segundo plano!                   "
echo "                                                          "
echo "   Para ver o QR Code do WhatsApp, digite no terminal:    "
echo "   docker compose logs -f bridge                          "
echo "=========================================================="
echo ""
