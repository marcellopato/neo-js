const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const os = require('os');
const {
    detectUserAndHome,
    buildExecStop,
    formatExecStart,
    generateServiceContent,
} = require('../install-service');

const templatePath = path.join(__dirname, '..', 'neo.service');
const sampleTemplate = fs.readFileSync(templatePath, 'utf8');

test('detectUserAndHome returns non-empty user and homeDir', () => {
    const { user, homeDir } = detectUserAndHome();
    assert.ok(user && typeof user === 'string', 'user should be a non-empty string');
    assert.ok(homeDir && typeof homeDir === 'string', 'homeDir should be a non-empty string');
});

test('formatExecStart wraps in quotes only when path contains spaces', () => {
    assert.strictEqual(
        formatExecStart('/opt/neo/start.sh'),
        '/opt/neo/start.sh'
    );
    assert.strictEqual(
        formatExecStart('/home/user/Meus Projetos/Neo.JS/start.sh'),
        '"/home/user/Meus Projetos/Neo.JS/start.sh"'
    );
});

test('buildExecStop protects against spaces and quotes in directory path', () => {
    const dir = '/home/user/Meus Projetos/Neo.JS';
    const stopCmd = buildExecStop(dir);
    assert.match(stopCmd, /cat "\/home\/user\/Meus Projetos\/Neo\.JS\/backend\.pid"/);
    assert.match(stopCmd, /cat "\/home\/user\/Meus Projetos\/Neo\.JS\/bridge\.pid"/);
    assert.match(stopCmd, /rm -f "\/home\/user\/Meus Projetos\/Neo\.JS\/backend\.pid" "\/home\/user\/Meus Projetos\/Neo\.JS\/bridge\.pid"/);
});

test('generateServiceContent generates correct service for arbitrary Linux user without hardcoded marcello', () => {
    const result = generateServiceContent(sampleTemplate, {
        user: 'igor',
        homeDir: '/home/igor',
        projectDir: '/home/igor/neo-js',
    });

    assert.match(result, /^User=igor$/m);
    assert.match(result, /^Environment=HOME=\/home\/igor$/m);
    assert.match(result, /^WorkingDirectory=\/home\/igor\/neo-js$/m);
    assert.match(result, /^ExecStart=\/home\/igor\/neo-js\/start\.sh$/m);
    assert.doesNotMatch(result, /marcello/, 'Output must not have any remaining reference to marcello');
});

test('generateServiceContent correctly handles project paths containing spaces', () => {
    const result = generateServiceContent(sampleTemplate, {
        user: 'linuxuser',
        homeDir: '/home/linuxuser',
        projectDir: '/home/linuxuser/Meus Projetos/Neo.JS',
    });

    assert.match(result, /^User=linuxuser$/m);
    assert.match(result, /^WorkingDirectory=\/home\/linuxuser\/Meus Projetos\/Neo\.JS$/m);
    assert.match(result, /^ExecStart="\/home\/linuxuser\/Meus Projetos\/Neo\.JS\/start\.sh"$/m);
    assert.match(result, /cat "\/home\/linuxuser\/Meus Projetos\/Neo\.JS\/backend\.pid"/);
});

test('generateServiceContent preserves existing valid service for author marcello', () => {
    const result = generateServiceContent(sampleTemplate, {
        user: 'marcello',
        homeDir: '/home/marcello',
        projectDir: '/home/marcello/Documentos/www/Neo.JS',
    });

    assert.match(result, /^User=marcello$/m);
    assert.match(result, /^Environment=HOME=\/home\/marcello$/m);
    assert.match(result, /^WorkingDirectory=\/home\/marcello\/Documentos\/www\/Neo\.JS$/m);
    assert.match(result, /^ExecStart=\/home\/marcello\/Documentos\/www\/Neo\.JS\/start\.sh$/m);
});

test('generateServiceContent injects User and Environment when missing from template', () => {
    const minimalTemplate = `[Unit]
Description=Test
[Service]
Type=oneshot
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
`;

    const result = generateServiceContent(minimalTemplate, {
        user: 'customuser',
        homeDir: '/home/customuser',
        projectDir: '/opt/neo',
    });

    assert.match(result, /^User=customuser$/m);
    assert.match(result, /^Environment=HOME=\/home\/customuser$/m);
    assert.match(result, /^WorkingDirectory=\/opt\/neo$/m);
    assert.match(result, /^ExecStart=\/opt\/neo\/start\.sh$/m);
});

test('systemd-analyze validates generated unit file when tool is available', () => {
    const { execSync } = require('child_process');
    try {
        execSync('which systemd-analyze', { stdio: 'ignore' });
    } catch {
        return; // Pula se systemd-analyze não estiver presente
    }

    const tmpDir = path.join(os.tmpdir(), 'neo test space dir');
    fs.mkdirSync(tmpDir, { recursive: true });
    const dummyStart = path.join(tmpDir, 'start.sh');
    fs.writeFileSync(dummyStart, '#!/bin/bash\nexit 0\n');
    fs.chmodSync(dummyStart, 0o755);

    const tmpServiceFile = path.join(os.tmpdir(), 'test-neo.service');
    const content = generateServiceContent(sampleTemplate, {
        user: os.userInfo().username,
        homeDir: os.homedir(),
        projectDir: tmpDir,
    });
    fs.writeFileSync(tmpServiceFile, content);

    try {
        execSync(`systemd-analyze verify ${tmpServiceFile}`, { stdio: 'pipe' });
    } finally {
        try { fs.unlinkSync(tmpServiceFile); } catch {}
        try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch {}
    }
});

