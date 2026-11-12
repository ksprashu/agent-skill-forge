'use strict';

const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('node:child_process');
const test = require('node:test');

const SCRIPT = path.join(__dirname, '..', 'scripts', 'characters.cjs');
const {
    validateSpec,
    resolveBiblePath,
} = require(SCRIPT);

function character(id, extra) {
    return Object.assign({ id, name: 'Pip', role: 'builder' }, extra || {});
}

function spec(characters, extra) {
    return Object.assign({
        companion_theme: 'Pip',
        characters,
    }, extra || {});
}

function writePack(dir, body) {
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, 'characters.json'), JSON.stringify(body));
}

test('a lowercase id pack validates and a bible inside the pack resolves', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'chars-good-'));
    const bible = path.join(dir, 'notes');
    fs.mkdirSync(bible);
    fs.writeFileSync(path.join(bible, 'BIBLE.md'), '# bible\n');
    const body = spec([character('pip')], { character_bible: 'notes/BIBLE.md' });
    assert.deepEqual(validateSpec(body, dir), []);
    assert.equal(resolveBiblePath(dir, body), path.join(dir, 'notes', 'BIBLE.md'));
});

test('uppercase ids, path segments, and case-only duplicates are rejected', () => {
    const upper = validateSpec(spec([character('Pip')]));
    assert.ok(upper.some(err => err.includes('must match')));
    const escaped = validateSpec(spec([character('../secret')]));
    assert.ok(escaped.some(err => err.includes('must match')));
    const dup = validateSpec(spec([character('pip'), character('Pip')]));
    assert.ok(dup.some(err => /case-insensitive/.test(err)));
});

test('a missing configured bible is an error and is not replaced by the default name', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'chars-typo-'));
    fs.writeFileSync(path.join(dir, 'CHARACTER_BIBLE.md'), '# default\n');
    const body = spec([character('pip')], { character_bible: 'TYPO.md' });
    const errors = validateSpec(body, dir);
    assert.ok(errors.some(err => err.includes('TYPO.md')));
    assert.equal(resolveBiblePath(dir, body), null);
});

test('character_bible cannot escape the pack', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'chars-escape-'));
    const outside = path.join(path.dirname(dir), `secret-${path.basename(dir)}.md`);
    fs.writeFileSync(outside, 'secret\n');
    const body = spec([character('pip')], {
        character_bible: `../secret-${path.basename(dir)}.md`,
    });
    const errors = validateSpec(body, dir);
    assert.ok(errors.some(err => /character_bible/.test(err)));
    assert.equal(resolveBiblePath(dir, body), null);
    fs.unlinkSync(outside);
});

test('cli accepts a valid pack and rejects a bad id', () => {
    const good = fs.mkdtempSync(path.join(os.tmpdir(), 'chars-cli-good-'));
    const bad = fs.mkdtempSync(path.join(os.tmpdir(), 'chars-cli-bad-'));
    writePack(good, spec([character('pip')]));
    writePack(bad, spec([character('Pip')]));
    const run = dir => spawnSync(process.execPath, [SCRIPT, 'status'], {
        env: Object.assign({}, process.env, {
            CODELAB_CHARACTERS_DIR: dir,
            AGENT_PERSONA_DIR: path.join(os.tmpdir(), 'no-such-persona-dir'),
        }),
        encoding: 'utf8',
    });
    const ok = run(good);
    assert.equal(ok.status, 0, ok.stdout + ok.stderr);
    assert.match(ok.stdout, /tier: character-pack/);
    const fail = run(bad);
    assert.equal(fail.status, 2, fail.stdout + fail.stderr);
    assert.match(fail.stderr, /must match/);
});
