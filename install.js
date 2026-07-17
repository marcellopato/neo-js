/**
 * Neo.JS - Interactive Installer Wizard 🚀
 * Uses ONLY built-in Node.js modules so it can be run before npm install.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const readline = require('readline');
const os = require('os');

// UI Colors (ANSI Escape Codes)
const C = {
    reset: '\x1b[0m',
    bold: '\x1b[1m',
    green: '\x1b[32m',
    cyan: '\x1b[36m',
    yellow: '\x1b[33m',
    red: '\x1b[31m',
    magenta: '\x1b[35m'
};

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

const question = (query) => new Promise((resolve) => rl.question(query, resolve));

function log(msg, color = C.reset) {
    console.log(`${color}${msg}${C.reset}`);
}

function bold(msg, color = C.reset) {
    console.log(`${C.bold}${color}${msg}${C.reset}`);
}

async function runCommand(cmd, desc) {
    log(`\n[Processando] ${desc}...`, C.cyan);
    try {
        execSync(cmd, { stdio: 'inherit' });
        log(`[Sucesso] ${desc} concluído.`, C.green);
        return true;
    } catch (err) {
        log(`[Erro] Falha ao executar: ${cmd}. Detalhes: ${err.message}`, C.red);
        return false;
    }
}

async function main() {
    console.clear();
    bold('==================================================', C.magenta);
    bold('        NEO.JS - ASSISTENTE DE BACKPOCKET         ', C.magenta);
    bold('             INSTALADOR INTERATIVO 🚀             ', C.magenta);
    bold('==================================================', C.magenta);
    log('Bem-vindo ao configurador inteligente do Neo. Vamos deixar tudo pronto.', C.cyan);

    const platform = os.platform();
    const isMac = platform === 'darwin';
    const isLinux = platform === 'linux';

    log(`\nPlataforma identificada: ${C.bold}${platform === 'darwin' ? 'macOS (Darwin)' : platform === 'linux' ? 'Linux' : platform}${C.reset}`);

    // Step 0: Check for existing installation
    bold('\nStep 0: Verificando instalações anteriores...', C.yellow);
    if (fs.existsSync(path.join(__dirname, '.wwebjs_auth'))) {
        log('⚠ ATENÇÃO: Detectamos uma sessão anterior do WhatsApp nesta pasta.', C.yellow);
        log('Sua sessão será preservada — você não precisará escanear o QR Code novamente.', C.green);
    }

    // Step 1: Check environment dependencies
    bold('\nStep 1: Verificando dependências do sistema...', C.yellow);
    try {
        const nodeVer = execSync('node --version').toString().trim();
        log(`✓ Node.js detectado: ${nodeVer}`, C.green);
    } catch (e) {
        log('✗ Node.js não foi encontrado no PATH. Por favor, instale o Node.js primeiro.', C.red);
        process.exit(1);
    }

    let pythonCmd = 'python3';
    try {
        const pyVer = execSync('python3 --version').toString().trim();
        log(`✓ Python detectado: ${pyVer}`, C.green);
    } catch (e) {
        try {
            const pyVer = execSync('python --version').toString().trim();
            log(`✓ Python detectado (via alias python): ${pyVer}`, C.green);
            pythonCmd = 'python';
        } catch (err2) {
            log('✗ Python 3 não foi encontrado. Por favor, instale o Python 3 primeiro.', C.red);
            process.exit(1);
        }
    }

    // Step 2: Configure environment variables (.env)
    bold('\nStep 2: Configurando arquivo de ambiente (.env)...', C.yellow);
    const envPath = path.join(__dirname, '.env');
    let geminiKey = '';
    let internalApiKey = 'neo_internal_secret_token_' + Math.random().toString(36).substring(2, 15);
    let neoPassword = 'neo_password_' + Math.random().toString(36).substring(2, 15);

    if (fs.existsSync(envPath)) {
        log('O arquivo .env já existe nesta pasta.', C.cyan);
        const choiceEnv = await question('Deseja sobrescrevê-lo com uma nova chave API? (s/n): ');
        if (choiceEnv.trim().toLowerCase() === 's') {
            geminiKey = await question('Digite sua nova GEMINI_API_KEY: ');
            
            // Read existing keys to preserve them if they exist
            try {
                const currentContent = fs.readFileSync(envPath, 'utf8');
                const lines = currentContent.split('\n');
                for (const line of lines) {
                    if (line.startsWith('INTERNAL_API_KEY=')) {
                        const val = line.substring('INTERNAL_API_KEY='.length).trim();
                        if (val) internalApiKey = val;
                    }
                    if (line.startsWith('NEO_PASSWORD=')) {
                        const val = line.substring('NEO_PASSWORD='.length).trim();
                        if (val) neoPassword = val;
                    }
                }
            } catch (err) {
                // Ignore reading errors, use generated defaults
            }
        }
    } else {
        geminiKey = await question('Digite sua GEMINI_API_KEY (Gemini 2.0 Flash): ');
    }

    if (geminiKey) {
        fs.writeFileSync(envPath, `GEMINI_API_KEY=${geminiKey.trim()}\nINTERNAL_API_KEY=${internalApiKey}\nNEO_PASSWORD=${neoPassword}\n`);
        log('✓ Arquivo .env criado e salvo com sucesso!', C.green);
    } else {
        log('Mantendo o arquivo .env existente ou pulando configuração.', C.cyan);
    }

    // Step 3: Set up Python Virtual Environment (venv)
    bold('\nStep 3: Configurando ambiente Python (venv)...', C.yellow);
    const venvDir = path.join(__dirname, 'venv');
    let venvExists = fs.existsSync(venvDir);

    if (venvExists) {
        log('Pasta venv já encontrada.', C.cyan);
        const recreate = await question('Deseja recriar o ambiente virtual Python? (s/n): ');
        if (recreate.trim().toLowerCase() === 's') {
            fs.rmSync(venvDir, { recursive: true, force: true });
            venvExists = false;
        }
    }

    if (!venvExists) {
        const pyVenvSuccess = await runCommand(`${pythonCmd} -m venv venv`, 'Criando ambiente virtual (venv)');
        if (!pyVenvSuccess) {
            log('✗ Falha ao criar venv. Verifique se o pacote python3-venv está instalado.', C.red);
            process.exit(1);
        }
    }

    // Install/update python requirements
    const pipPath = isMac || isLinux ? './venv/bin/pip' : '.\\venv\\Scripts\\pip';
    await runCommand(`${pipPath} install --upgrade pip`, 'Atualizando gerenciador pip');
    const requirementsPath = path.join(__dirname, 'requirements.txt');
    if (fs.existsSync(requirementsPath)) {
        await runCommand(`${pipPath} install -r requirements.txt`, 'Instalando bibliotecas do Python (incluindo Antigravity SDK)');
    } else {
        log('⚠ requirements.txt não encontrado. Pulando etapa de pacotes Python.', C.yellow);
    }

    // Step 4: Install Node.js packages
    bold('\nStep 4: Instalando dependências e bibliotecas em Node...', C.yellow);
    await runCommand('npm install', 'Instalando pacotes npm (incluindo whatsapp-web.js)');

    // Step 5: Configure persistence / service
    bold('\nStep 5: Opções de inicialização automática (Persistência)...', C.yellow);
    if (isMac) {
        log('Recomendado no macOS: usar PM2 para gerenciar o Neo em segundo plano.', C.cyan);
        const installPM2 = await question('Deseja configurar a inicialização com o PM2 agora? (s/n): ');
        if (installPM2.trim().toLowerCase() === 's') {
            let hasPM2 = false;
            try {
                execSync('pm2 --version');
                hasPM2 = true;
                log('✓ PM2 já está instalado globalmente.', C.green);
            } catch (e) {
                log('PM2 não detectado globalmente.', C.yellow);
                const installGlobal = await question('Deseja instalar o PM2 globalmente usando npm? (Exige permissões de administrador) (s/n): ');
                if (installGlobal.trim().toLowerCase() === 's') {
                    try {
                        execSync('sudo npm install -g pm2', { stdio: 'inherit' });
                        hasPM2 = true;
                    } catch (err) {
                        log('⚠ Não foi possível instalar o PM2 com root. Tentando sem sudo...', C.yellow);
                        try {
                            execSync('npm install -g pm2', { stdio: 'inherit' });
                            hasPM2 = true;
                        } catch (e) {
                            log('✗ Falha ao instalar o PM2. Siga as instruções manuais do README.', C.red);
                        }
                    }
                }
            }

            if (hasPM2) {
                try {
                    execSync('pm2 start start.sh --name "neo-assistant"', { stdio: 'inherit' });
                    log('\n✓ Neo foi registrado com sucesso no PM2!', C.green);
                    log('Para fazer o Neo iniciar junto com o macOS, execute:', C.cyan);
                    log('  pm2 startup && pm2 save', C.bold);
                } catch (errStart) {
                    log(`✗ Falha ao iniciar no PM2: ${errStart.message}`, C.red);
                }
            }
        }
    } else if (isLinux) {
        log('No Linux, você pode usar o systemd (neo.service) para iniciar o Neo automaticamente.', C.cyan);
        const installService = await question('Deseja configurar o neo.service no systemd agora? (Requer sudo) (s/n): ');
        if (installService.trim().toLowerCase() === 's') {
            const projectDir = __dirname;
            // Atualiza o WorkingDirectory e ExecStart com o caminho real do projeto
            let serviceContent = fs.readFileSync(path.join(projectDir, 'neo.service'), 'utf8');
            serviceContent = serviceContent
                .replace(/WorkingDirectory=.*/g, `WorkingDirectory=${projectDir}`)
                .replace(/ExecStart=.*/g, `ExecStart=${projectDir}/start.sh`)
                .replace(/ExecStop=.*\n/g, `ExecStop=/bin/bash -c 'kill $(cat ${projectDir}/backend.pid 2>/dev/null) 2>/dev/null; kill $(cat ${projectDir}/bridge.pid 2>/dev/null) 2>/dev/null; rm -f ${projectDir}/backend.pid ${projectDir}/bridge.pid'\n`);
            const tmpService = `/tmp/neo-install.service`;
            fs.writeFileSync(tmpService, serviceContent);
            try {
                execSync(`sudo cp ${tmpService} /etc/systemd/system/neo.service && sudo systemctl daemon-reload && sudo systemctl enable neo && sudo systemctl start neo`, { stdio: 'inherit' });
                log('\n✅ Neo configurado como serviço systemd e iniciado!', C.green);
                log('Comandos úteis:', C.cyan);
                log('  sudo systemctl status neo    # Ver status', C.bold);
                log('  sudo systemctl restart neo   # Reiniciar', C.bold);
                log('  sudo systemctl stop neo      # Parar', C.bold);
            } catch (err) {
                log(`✗ Falha ao configurar o serviço: ${err.message}`, C.red);
                log('Execute manualmente: sudo cp neo.service /etc/systemd/system/ && sudo systemctl enable --now neo', C.yellow);
            }
        }
    }

    // End Installer
    bold('\n==================================================', C.magenta);
    bold('        INSTALAÇÃO DO NEO CONCLUÍDA! 🎉           ', C.magenta);
    bold('==================================================', C.magenta);
    log('O Neo está configurado e pronto para decolar.', C.green);
    log(`\n${C.bold}Como iniciar manualmente e escanear o QR Code:${C.reset}`);
    log('  1. Execute o comando:  ./start.sh');
    log('  2. Abra seu WhatsApp e escaneie o QR Code exibido no terminal.');
    log('  3. Envie uma mensagem no seu chat privado (contato "Você") para começar!');
    console.log();

    rl.close();
}

main().catch(err => {
    console.error('Ocorreu um erro crítico durante a instalação:', err);
    rl.close();
});
