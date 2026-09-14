/**
 * Neo.JS - Gerador e utilitários para instalação do serviço systemd.
 *
 * Garante portabilidade entre diferentes usuários Linux, respeita diretórios
 * com espaços e permite testes unitários desacoplados da execução com sudo.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

/**
 * Detecta o usuário e diretório HOME de forma portátil.
 * Suporta execuções regulares e ambientes com sudo (via SUDO_USER).
 *
 * @returns {{ user: string, homeDir: string }}
 */
function detectUserAndHome() {
    const user = process.env.SUDO_USER || (os.userInfo && os.userInfo().username) || process.env.USER || 'root';
    let homeDir = os.homedir();

    if (process.env.SUDO_USER && process.env.SUDO_USER !== 'root') {
        const candidate = path.join('/home', process.env.SUDO_USER);
        if (fs.existsSync(candidate)) {
            homeDir = candidate;
        }
    }

    return { user, homeDir };
}

/**
 * Gera o script bash da diretiva ExecStop com caminhos protegidos contra espaços e aspas.
 *
 * @param {string} projectDir
 * @returns {string}
 */
function buildExecStop(projectDir) {
    const escaped = projectDir.replace(/'/g, "'\\''");
    return `/bin/bash -c 'kill $(cat "${escaped}/backend.pid" 2>/dev/null) 2>/dev/null; kill $(cat "${escaped}/bridge.pid" 2>/dev/null) 2>/dev/null; rm -f "${escaped}/backend.pid" "${escaped}/bridge.pid"'`;
}

/**
 * Formata a diretiva ExecStart para o systemd.
 * Se o caminho contiver espaços, envolve em aspas duplas (requisito da sintaxe systemd).
 *
 * @param {string} startPath
 * @returns {string}
 */
function formatExecStart(startPath) {
    return startPath.includes(' ') ? `"${startPath}"` : startPath;
}

/**
 * Gera o conteúdo do serviço systemd substituindo dinamicamente as variáveis de ambiente.
 *
 * @param {string} templateContent - Conteúdo do arquivo de modelo (ex: neo.service)
 * @param {{ user: string, homeDir: string, projectDir: string }} options
 * @returns {string}
 */
function generateServiceContent(templateContent, { user, homeDir, projectDir }) {
    const startScript = path.join(projectDir, 'start.sh');
    const execStart = formatExecStart(startScript);
    const execStop = buildExecStop(projectDir);

    let content = templateContent;

    if (/^User=.*/m.test(content)) {
        content = content.replace(/^User=.*/m, `User=${user}`);
    } else {
        content = content.replace(/\[Service\]/i, `[Service]\nUser=${user}`);
    }

    if (/^Environment=HOME=.*/m.test(content)) {
        content = content.replace(/^Environment=HOME=.*/m, `Environment=HOME=${homeDir}`);
    } else {
        content = content.replace(/\[Service\]/i, `[Service]\nEnvironment=HOME=${homeDir}`);
    }

    if (/^WorkingDirectory=.*/m.test(content)) {
        content = content.replace(/^WorkingDirectory=.*/m, `WorkingDirectory=${projectDir}`);
    } else {
        content = content.replace(/\[Service\]/i, `[Service]\nWorkingDirectory=${projectDir}`);
    }

    if (/^ExecStart=.*/m.test(content)) {
        content = content.replace(/^ExecStart=.*/m, `ExecStart=${execStart}`);
    } else {
        content = content.replace(/\[Service\]/i, `[Service]\nExecStart=${execStart}`);
    }

    if (/^ExecStop=.*/m.test(content)) {
        content = content.replace(/^ExecStop=.*/m, `ExecStop=${execStop}`);
    } else {
        content = content.replace(/\[Service\]/i, `[Service]\nExecStop=${execStop}`);
    }

    return content;
}

module.exports = {
    detectUserAndHome,
    buildExecStop,
    formatExecStart,
    generateServiceContent,
};
