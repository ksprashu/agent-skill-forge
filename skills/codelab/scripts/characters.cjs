#!/usr/bin/env node
/**
 * Copyright 2026 Google LLC.
 * SPDX-License-Identifier: Apache-2.0
 *
 * characters.cjs - Resolve and validate an optional codelab character pack.
 *
 * Resolution precedence:
 *   1. process.env.CODELAB_CHARACTERS_DIR (when set)
 *   2. path.join(process.env.AGENT_PERSONA_DIR || path.join(os.homedir(), '.gemini', 'personas'), 'default', 'characters')
 *   3. None (neutral mascot-free codelab default)
 *
 * CLI:
 *   node scripts/characters.cjs status [--json]
 *
 * Exit codes:
 *   0  Valid character pack resolved
 *   1  No character pack installed (tier: neutral)
 *   2  Invalid arguments, unreadable JSON, or schema validation failure
 */

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

function defaultPersonaRoot() {
    const override = process.env.AGENT_PERSONA_DIR;
    if (override && override.trim()) {
        if (override.startsWith('~/') || override === '~') {
            return path.join(os.homedir(), override.slice(1));
        }
        return path.resolve(override);
    }
    return path.join(os.homedir(), '.gemini', 'personas');
}

function expandHome(p) {
    if (p === '~') return os.homedir();
    if (p.startsWith('~/') || p.startsWith('~\\')) {
        return path.join(os.homedir(), p.slice(2));
    }
    return p;
}

function locateCharactersFile(baseDir) {
    const resolvedBase = path.resolve(expandHome(baseDir));
    if (!fs.existsSync(resolvedBase)) {
        return null;
    }
    const stat = fs.statSync(resolvedBase);
    if (stat.isFile() && path.basename(resolvedBase) === 'characters.json') {
        return { dir: path.dirname(resolvedBase), file: resolvedBase };
    }
    if (!stat.isDirectory()) {
        return null;
    }
    const direct = path.join(resolvedBase, 'characters.json');
    if (fs.existsSync(direct) && fs.statSync(direct).isFile()) {
        return { dir: resolvedBase, file: direct };
    }
    // Support single-pack subdirectory layout: default/characters/<pack-slug>/characters.json
    const entries = fs.readdirSync(resolvedBase, { withFileTypes: true })
        .filter(d => d.isDirectory() && !d.name.startsWith('.'))
        .map(d => d.name)
        .sort();
    for (const sub of entries) {
        const nestedDir = path.join(resolvedBase, sub);
        const nestedFile = path.join(nestedDir, 'characters.json');
        if (fs.existsSync(nestedFile) && fs.statSync(nestedFile).isFile()) {
            return { dir: nestedDir, file: nestedFile };
        }
    }
    return null;
}

function resolveCandidate() {
    const envDir = process.env.CODELAB_CHARACTERS_DIR;
    if (envDir && envDir.trim()) {
        return locateCharactersFile(envDir.trim());
    }
    const personaChars = path.join(defaultPersonaRoot(), 'default', 'characters');
    return locateCharactersFile(personaChars);
}

function isNonEmptyString(val) {
    return typeof val === 'string' && val.trim().length > 0;
}

function validateSpec(spec) {
    const errors = [];
    if (!spec || typeof spec !== 'object' || Array.isArray(spec)) {
        return ['Root value of characters.json must be a JSON object.'];
    }
    if (!isNonEmptyString(spec.companion_theme)) {
        errors.push("Missing or empty required string field 'companion_theme'.");
    }
    if (!Array.isArray(spec.characters) || spec.characters.length === 0) {
        errors.push("Required field 'characters' must be a non-empty array.");
    } else {
        const seenIds = new Set();
        spec.characters.forEach((ch, idx) => {
            if (!ch || typeof ch !== 'object' || Array.isArray(ch)) {
                errors.push(`characters[${idx}] must be an object.`);
                return;
            }
            for (const reqField of ['id', 'name', 'role']) {
                if (!isNonEmptyString(ch[reqField])) {
                    errors.push(`characters[${idx}] missing required non-empty string '${reqField}'.`);
                }
            }
            if (isNonEmptyString(ch.id)) {
                if (seenIds.has(ch.id)) {
                    errors.push(`Duplicate character id '${ch.id}'.`);
                }
                seenIds.add(ch.id);
            }
            if (ch.icons !== undefined) {
                const validArray = Array.isArray(ch.icons) && ch.icons.every(isNonEmptyString);
                const validObj = typeof ch.icons === 'object' && ch.icons !== null && !Array.isArray(ch.icons) &&
                    Object.values(ch.icons).every(isNonEmptyString);
                if (!validArray && !validObj) {
                    errors.push(`characters[${idx}].icons must be a string map or array of strings when provided.`);
                }
            }
        });
    }
    if (spec.comics !== undefined) {
        const validComics = typeof spec.comics === 'object' && spec.comics !== null && !Array.isArray(spec.comics) &&
            Object.values(spec.comics).every(isNonEmptyString);
        if (!validComics) {
            errors.push("'comics' must be an object mapping comic keys to relative asset paths.");
        }
    }
    return errors;
}

function discoverFilesInSubdir(packDir, subdirName) {
    const target = path.join(packDir, subdirName);
    if (!fs.existsSync(target) || !fs.statSync(target).isDirectory()) {
        return [];
    }
    return fs.readdirSync(target)
        .filter(f => !f.startsWith('.') && /\.(png|svg|jpg|jpeg|webp)$/i.test(f))
        .sort()
        .map(f => path.posix.join(subdirName, f));
}

function resolveBiblePath(packDir, spec) {
    if (isNonEmptyString(spec.character_bible)) {
        const candidate = path.resolve(packDir, spec.character_bible);
        if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
            return candidate;
        }
    }
    for (const name of ['CHARACTER_BIBLE.md', 'character-bible.md']) {
        const candidate = path.join(packDir, name);
        if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
            return candidate;
        }
    }
    return null;
}

function buildComicsMap(packDir, spec) {
    if (spec.comics && Object.keys(spec.comics).length > 0) {
        return spec.comics;
    }
    const discovered = [
        ...discoverFilesInSubdir(packDir, 'common-comics'),
        ...discoverFilesInSubdir(packDir, 'comics'),
    ];
    const map = {};
    for (const rel of discovered) {
        const key = path.basename(rel, path.extname(rel));
        map[key] = rel;
    }
    return map;
}

function resolveCharacterIcons(packDir, ch, sharedIcons) {
    if (ch.icons) {
        return ch.icons;
    }
    const prefix = `${ch.id.toLowerCase()}-`;
    const matched = sharedIcons.filter(rel => path.basename(rel).toLowerCase().startsWith(prefix));
    return matched;
}

function runStatus(asJson) {
    const located = resolveCandidate();
    if (!located) {
        if (asJson) {
            console.log(JSON.stringify({
                tier: 'neutral',
                characters_dir: null,
                companion_theme: null,
                characters: [],
                comics: {}
            }, null, 2));
        } else {
            console.log('tier: neutral');
            console.log('characters_dir: (none)');
        }
        return 1;
    }

    let raw;
    try {
        raw = fs.readFileSync(located.file, 'utf8');
    } catch (err) {
        console.error(`characters.cjs error: cannot read ${located.file}: ${err.message}`);
        return 2;
    }

    let spec;
    try {
        spec = JSON.parse(raw);
    } catch (err) {
        console.error(`characters.cjs error: invalid JSON in ${located.file}: ${err.message}`);
        return 2;
    }

    const errors = validateSpec(spec);
    if (errors.length > 0) {
        console.error(`characters.cjs schema error in ${located.file}:`);
        for (const e of errors) {
            console.error(`  - ${e}`);
        }
        return 2;
    }

    const sharedIcons = discoverFilesInSubdir(located.dir, 'icons');
    const biblePath = resolveBiblePath(located.dir, spec);
    const comicsMap = buildComicsMap(located.dir, spec);
    const charactersSummary = spec.characters.map(ch => ({
        id: ch.id,
        name: ch.name,
        role: ch.role,
        callout_label: ch.callout_label || null,
        icons: resolveCharacterIcons(located.dir, ch, sharedIcons)
    }));

    if (asJson) {
        console.log(JSON.stringify({
            tier: 'character-pack',
            characters_dir: located.dir,
            characters_file: located.file,
            character_bible: biblePath,
            companion_theme: spec.companion_theme,
            characters: charactersSummary,
            comics: comicsMap
        }, null, 2));
        return 0;
    }

    console.log('tier: character-pack');
    console.log(`characters_dir: ${located.dir}`);
    console.log(`characters_file: ${located.file}`);
    console.log(`character_bible: ${biblePath || '(none)'}`);
    console.log(`companion_theme: ${spec.companion_theme}`);
    console.log('characters:');
    for (const ch of charactersSummary) {
        const iconStr = Array.isArray(ch.icons)
            ? (ch.icons.length > 0 ? ch.icons.join(', ') : '(none)')
            : JSON.stringify(ch.icons);
        console.log(`  - ${ch.id}: ${ch.name} (${ch.role}) | icons: ${iconStr}`);
    }
    const comicEntries = Object.entries(comicsMap);
    if (comicEntries.length === 0) {
        console.log('comics: (none)');
    } else {
        console.log('comics:');
        for (const [key, val] of comicEntries) {
            console.log(`  - ${key}: ${val}`);
        }
    }
    return 0;
}

function main(argv) {
    const args = argv.slice(2);
    const sub = args[0];
    if (sub !== 'status') {
        console.error('Usage: node scripts/characters.cjs status [--json]');
        process.exit(2);
    }
    const rest = args.slice(1);
    let asJson = false;
    for (const flag of rest) {
        if (flag === '--json') {
            asJson = true;
        } else {
            console.error(`Unknown option: ${flag}`);
            process.exit(2);
        }
    }
    process.exit(runStatus(asJson));
}

if (require.main === module) {
    main(process.argv);
}

module.exports = { locateCharactersFile, resolveCandidate, validateSpec, runStatus };
