# Neo Assistente por Voz — Instalador Automatico para Windows (100% para leigos)
$ErrorActionPreference = "Stop"

$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectDir

Write-Host "[1/6] Verificando Python no Windows..." -ForegroundColor Cyan
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "Python nao encontrado. Tentando instalar automaticamente via winget..." -ForegroundColor Yellow
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    } else {
        Write-Host "Nao foi possivel instalar o Python automaticamente." -ForegroundColor Red
        Write-Host "Abra https://www.python.org/downloads/ , instale marcando 'Add Python to PATH' e clique em Instalar-Neo.bat novamente." -ForegroundColor Yellow
        Start-Process "https://www.python.org/downloads/"
        exit 1
    }
}

Write-Host "[2/6] Preparando ambiente virtual e instalando dependencias..." -ForegroundColor Cyan
$venvDir = Join-Path $ProjectDir "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPythonW = Join-Path $venvDir "Scripts\pythonw.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
    python -m venv $venvDir
}

& $venvPython -m pip install --upgrade pip --quiet
& $venvPip install -r (Join-Path $ProjectDir "requirements.txt") --quiet
& $venvPip install -r (Join-Path $ProjectDir "requirements-voice.txt") --quiet

Write-Host "[3/6] Baixando modelo de voz offline em portugues ('Ei Neo', ~31 MB)..." -ForegroundColor Cyan
$modelsDir = Join-Path $ProjectDir "models"
$voskTarget = Join-Path $modelsDir "vosk-pt"
if (-not (Test-Path $voskTarget)) {
    New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
    $zipPath = Join-Path $env:TEMP "vosk-model-small-pt-0.3.zip"
    $modelUrl = "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"
    Invoke-WebRequest -Uri $modelUrl -OutFile $zipPath -UseBasicParsing
    Expand-Archive -Path $zipPath -DestinationPath $modelsDir -Force
    $extracted = Join-Path $modelsDir "vosk-model-small-pt-0.3"
    if (Test-Path $extracted) {
        Rename-Item -Path $extracted -NewName "vosk-pt"
    }
    Remove-Item -Path $zipPath -Force -ErrorAction SilentlyContinue
}

Write-Host "[4/6] Preparando configuracao inicial (.env)..." -ForegroundColor Cyan
$envFile = Join-Path $ProjectDir ".env"
if (-not (Test-Path $envFile)) {
    $token = -join ((48..57) + (97..102) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
    @(
        "NEO_PROFILE=assistant"
        "NEO_VOICE_ENABLED=true"
        "NEO_TTS_VOICE=pt-BR-FranciscaNeural"
        "NEO_FOLLOWUP_SECONDS=8"
        "INTERNAL_API_KEY=$token"
    ) | Set-Content -Path $envFile -Encoding UTF8
}

Write-Host "[5/6] Criando atalho na Area de Trabalho e inicializacao automatica..." -ForegroundColor Cyan
$silentVbs = Join-Path $ProjectDir "scripts\start-assistant-silent.vbs"
$wsh = New-Object -ComObject WScript.Shell

# Startup shortcut (inicia silenciosamente ao ligar o Windows)
$startupDir = [Environment]::GetFolderPath("Startup")
$startupShortcut = $wsh.CreateShortcut((Join-Path $startupDir "Neo Assistente.lnk"))
$startupShortcut.TargetPath = "wscript.exe"
$startupShortcut.Arguments = "`"$silentVbs`""
$startupShortcut.WorkingDirectory = $ProjectDir
$startupShortcut.Description = "Neo Assistente por Voz"
$startupShortcut.Save()

# Desktop shortcut para abrir a configuracao visual
$desktopDir = [Environment]::GetFolderPath("Desktop")
$desktopShortcut = $wsh.CreateShortcut((Join-Path $desktopDir "Configurar Neo Assistente.lnk"))
$desktopShortcut.TargetPath = "http://127.0.0.1:5000/setup"
$desktopShortcut.Save()

Write-Host "[6/6] Iniciando o Neo e abrindo a tela de configuracao facil..." -ForegroundColor Green
Start-Process -FilePath "wscript.exe" -ArgumentList "`"$silentVbs`"" -WorkingDirectory $ProjectDir
Start-Sleep -Seconds 3

$edge = Get-Command msedge -ErrorAction SilentlyContinue
if ($edge) {
    Start-Process "msedge" -ArgumentList "--app=http://127.0.0.1:5000/setup"
} else {
    Start-Process "http://127.0.0.1:5000/setup"
}

Write-Host ""
Write-Host "Pronto! A janela de configuracao do Neo foi aberta." -ForegroundColor Green
Write-Host "Depois de colar sua chave do Gemini e seus e-mails, basta dizer 'Ei Neo'!" -ForegroundColor Green
