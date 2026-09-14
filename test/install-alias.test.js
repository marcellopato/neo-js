const test = require('node:test');
const assert = require('node:assert/strict');
const {
    buildAliasBlock,
    buildFishAliasBlock,
    buildPowerShellFunction,
    detectShellConfigs,
    MARKER,
} = require('../install-alias');

test('buildAliasBlock generates valid bash/zsh alias block with marker', () => {
    const block = buildAliasBlock('/home/user/neo');
    assert.ok(block.includes(MARKER));
    assert.ok(block.includes('alias neo="/home/user/neo"'));
});

test('buildFishAliasBlock generates valid fish syntax', () => {
    const block = buildFishAliasBlock('/home/user/neo');
    assert.ok(block.includes(MARKER));
    assert.ok(block.includes('alias neo "/home/user/neo"'));
});

test('buildPowerShellFunction generates valid powershell function block', () => {
    const block = buildPowerShellFunction('/home/user/neo');
    assert.ok(block.includes(MARKER));
    assert.ok(block.includes('function neo {'));
});

test('detectShellConfigs returns non-empty array of candidate files', () => {
    const configs = detectShellConfigs();
    assert.ok(Array.isArray(configs));
    assert.ok(configs.length > 0);
});
