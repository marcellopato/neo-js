@echo off
chcp 65001 >nul
title Instalador Neo Assistente por Voz
echo.
echo =========================================================
echo       NEO ASSISTENTE POR VOZ - INSTALACAO FACIL
echo =========================================================
echo.
echo Aguarde... preparando tudo automaticamente para voce.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [AVISO] Algo precisou de atencao durante a instalacao.
    echo Leia a mensagem acima ou peca ajuda antes de fechar.
    pause
)
