const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const bridgeSource = fs.readFileSync(path.join(__dirname, '..', 'bridge.js'), 'utf8');

test('bridge.js does not hardcode Linux /tmp/neo-bridge-audio path', () => {
    assert.equal(
        bridgeSource.includes("'/tmp/neo-bridge-audio'"),
        false,
        'bridge.js should use os.tmpdir() instead of /tmp/neo-bridge-audio'
    );
    assert.match(bridgeSource, /os\.tmpdir\(\)/);
});

test('bridge.js auto-healing prompt is platform-aware for Windows', () => {
    assert.match(bridgeSource, /process\.platform\s*===\s*['"]win32['"]/);
});
