/**
 * Neo CLI alias installer — automatiza a criação do atalho `neo` no terminal.
 *
 * Detecta os arquivos de configuração do shell do usuário (.zshrc, .bashrc,
 * .bash_profile, fish config — e, no Windows, o $PROFILE do PowerShell) e
 * insere o bloco de alias/atalho de forma IDEMPOTENTE: se o marcador
 * "# Neo CLI" já existir no arquivo, nada é alterado.
 *
 * Usado pelo instalador (install.js) e testável de forma isolada.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');

// Marcador usado para detectar se o alias já foi instalado em um arquivo.
const MARKER = '# Neo CLI';

/**
 * Constrói o bloco de alias para bash/zsh (sintaxe POSIX).
 * @param {string} launcherPath - caminho absoluto do script executável `neo`
 * @returns {string}
 */
function buildAliasBlock(launcherPath) {
    return `${MARKER}
if [ -x "${launcherPath}" ]; then
    alias neo="${launcherPath}"
fi`;
}

/**
 * Constrói o bloco de alias com a sintaxe do fish shell.
 * (fish não aceita `[ -x ... ]; then ... fi` nem `alias x="y"` — usa
 * `test`, `end` e `alias x y`.)
 * @param {string} launcherPath - caminho absoluto do script executável `neo`
 * @returns {string}
 */
function buildFishAliasBlock(launcherPath) {
    return `${MARKER}
if test -x "${launcherPath}"
    alias neo "${launcherPath}"
end`;
}

/**
 * Detecta se um arquivo de config pertence ao fish shell.
 * @param {string} file
 * @returns {boolean}
 */
function isFishConfig(file) {
    return path.basename(file) === 'config.fish'
        || file.includes(path.join('.config', 'fish'));
}

/**
 * Constrói o atalho `neo` para o PowerShell (Windows).
 *
 * No Windows não existe o launcher bash do projeto — a função chama
 * diretamente o Python do venv (venv\Scripts\python.exe, que é o layout
 * do Windows) com o neo-cli.py, repassando os argumentos via @args.
 *
 * @param {string} launcherPath - caminho do launcher (o dirname é o projeto)
 * @returns {string}
 */
function buildPowerShellFunction(launcherPath) {
    const projectDir = path.dirname(launcherPath);
    const pythonExe = path.join(projectDir, 'venv', 'Scripts', 'python.exe');
    const cliPath = path.join(projectDir, 'neo-cli.py');
    return `${MARKER}
function neo {
    & "${pythonExe}" "${cliPath}" @args
}`;
}

/**
 * Detecta se um arquivo é um perfil do PowerShell ($PROFILE).
 * @param {string} file
 * @returns {boolean}
 */
function isPowerShellProfile(file) {
    const lower = file.toLowerCase();
    return lower.includes('powershell') || lower.endsWith('_profile.ps1');
}

/**
 * Detecta os perfis do PowerShell no Windows ($PROFILE).
 *
 * Caminhos padrão:
 * - PowerShell 5.1: Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1
 * - PowerShell 7+:  Documents\PowerShell\Microsoft.PowerShell_profile.ps1
 *
 * A pasta Documents pode ser redirecionada (OneDrive Known Folder Move) —
 * nesse caso a pasta local `Documents` costuma existir vazia, então as
 * variantes do OneDrive são checadas ANTES (a redireção só existe quando
 * ativa); usuários sem OneDrive caem no padrão sem alteração.
 *
 * @returns {string[]} caminhos absolutos (podem ainda não existir)
 */
function detectPowerShellProfiles() {
    const home = os.homedir();
    const docsCandidates = [
        path.join(home, 'OneDrive', 'Documents'),
        path.join(home, 'OneDrive - Personal', 'Documents'),
        path.join(home, 'OneDrive - Pessoal', 'Documents'),
        path.join(home, 'OneDrive - Empresa', 'Documents'),
        path.join(home, 'OneDrive - Company', 'Documents'),
        path.join(home, 'Documents'),
    ];
    const docs = docsCandidates.find(fs.existsSync) || docsCandidates[0];
    return [
        path.join(docs, 'WindowsPowerShell', 'Microsoft.PowerShell_profile.ps1'),
        path.join(docs, 'PowerShell', 'Microsoft.PowerShell_profile.ps1'),
    ];
}

/**
 * Detecta os arquivos de configuração de shell do usuário.
 *
 * No Windows o shell nativo é o PowerShell — retorna os perfis $PROFILE.
 * Em Unix:
 * - .zshrc  → se o shell atual é zsh OU o arquivo já existe
 * - .bashrc / .bash_profile → se o shell atual é bash ou o arquivo existe
 * - fish config.fish → se o shell atual é fish ou o arquivo existe
 * - .profile → fallback quando nada foi detectado (shells de login)
 *
 * @returns {string[]} caminhos absolutos (podem ainda não existir)
 */
function detectShellConfigs() {
    if (os.platform() === 'win32') {
        return detectPowerShellProfiles();
    }

    const home = os.homedir();
    const shell = (process.env.SHELL || '').toLowerCase();
    const cfg = (name) => path.join(home, name);
    const exists = (p) => fs.existsSync(p);

    const configs = [];

    const zshrc = cfg('.zshrc');
    if (shell.includes('zsh') || exists(zshrc)) {
        configs.push(zshrc);
    }

    const bashrc = cfg('.bashrc');
    const bashProfile = cfg('.bash_profile');
    if (shell.includes('bash')) {
        configs.push(exists(bashrc) ? bashrc : (exists(bashProfile) ? bashProfile : bashrc));
    } else if (exists(bashrc)) {
        configs.push(bashrc);
    } else if (exists(bashProfile)) {
        configs.push(bashProfile);
    }

    const fishCfg = cfg('.config/fish/config.fish');
    if (shell.includes('fish') || exists(fishCfg)) {
        configs.push(fishCfg);
    }

    if (configs.length === 0) {
        configs.push(cfg('.profile'));
    }

    return [...new Set(configs)];
}

/**
 * Instala o alias `neo` nos arquivos de configuração do shell (idempotente).
 *
 * @param {string} launcherPath - caminho absoluto do script executável `neo`
 * @returns {{ added: string[], skipped: string[] }}
 */
function installAlias(launcherPath) {
    const configs = detectShellConfigs();
    const added = [];
    const skipped = [];

    for (const file of configs) {
        let content = '';
        if (fs.existsSync(file)) {
            content = fs.readFileSync(file, 'utf8');
        }
        if (content.includes(MARKER)) {
            skipped.push(file);
            continue;
        }

        const block = isFishConfig(file)
            ? buildFishAliasBlock(launcherPath)
            : isPowerShellProfile(file)
                ? buildPowerShellFunction(launcherPath)
                : buildAliasBlock(launcherPath);
        const body = content.length
            ? (content.endsWith('\n') ? content : content + '\n') + block + '\n'
            : block + '\n';

        fs.mkdirSync(path.dirname(file), { recursive: true });
        fs.writeFileSync(file, body, 'utf8');
        added.push(file);
    }

    return { added, skipped };
}

module.exports = {
    installAlias,
    buildAliasBlock,
    buildFishAliasBlock,
    buildPowerShellFunction,
    detectShellConfigs,
    detectPowerShellProfiles,
    MARKER,
};
