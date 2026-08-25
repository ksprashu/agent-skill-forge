#!/usr/bin/env node

/**
 * Copyright 2026 Google LLC.
 * SPDX-License-Identifier: Apache-2.0
 */

const fs = require('fs');
const path = require('path');

const filePath = process.argv[2];

if (!filePath) {
  console.error('❌ Error: Please specify the path to your codelab markdown file.');
  console.error('Usage: node scripts/validate_codelab.cjs <path-to-lab.md>');
  process.exit(1);
}

try {
  const content = fs.readFileSync(filePath, 'utf8');
  const errors = [];
  const warnings = [];

  console.log(`🔍 Analyzing Codelab syntax in: ${path.basename(filePath)}`);

  // 1. Check Metadata (Frontmatter)
  if (!content.startsWith('---')) {
    errors.push('CRITICAL: File must start with YAML frontmatter delimiters (---)');
  } else {
    const endFrontmatter = content.indexOf('---', 3);
    if (endFrontmatter === -1) {
      errors.push('CRITICAL: YAML frontmatter must be closed with ---');
    } else {
      const frontmatter = content.substring(3, endFrontmatter);
      const requiredKeys = ['id', 'description', 'authors', 'layout'];
      requiredKeys.forEach(key => {
        if (!frontmatter.includes(`${key}:`)) {
          errors.push(`METADATA: Missing required frontmatter property: '${key}:'`);
        }
      });
    }
  }

  // 2. Check Title (H1)
  const h1Match = content.match(/^#\s+(.+)/m);
  if (!h1Match) {
    errors.push('STRUCTURE: Missing Main Title (Heading 1). Add "# My Title" after your frontmatter.');
  }

  // 3. Check Steps (H2)
  const h2Matches = content.match(/^##\s+(.+)/gm);
  if (!h2Matches || h2Matches.length === 0) {
    errors.push('STRUCTURE: No action step divisions found (Heading 2: ## Step Name). A codelab requires at least one step.');
  } else {
    // Check for Duration placement
    const lines = content.split('\n');
    lines.forEach((line, i) => {
      if (line.trim().startsWith('## ')) {
        const nextLine1 = lines[i + 1] ? lines[i + 1].trim() : '';
        const nextLine2 = lines[i + 2] ? lines[i + 2].trim() : '';
        
        const hasDuration = nextLine1.startsWith('Duration:') || nextLine2.startsWith('Duration:');
        if (!hasDuration) {
          warnings.push(`STRUCTURE: Step "${line.replace('##', '').trim()}" (line ${i + 1}) does not declare a duration (e.g., "Duration: 05:00").`);
        }
      }
    });
  }

  // 4. Check Info Boxes
  const invalidAsides = content.match(/>\s*aside\s+(?!positive|negative)\w+/g);
  if (invalidAsides) {
    invalidAsides.forEach(match => {
      errors.push(`SYNTAX: Invalid aside formatting: '${match}'. Use strictly 'positive' or 'negative'.`);
    });
  }

  // 5. Stylistic Advisory
  const jargonWords = ['simply', 'just', 'obviously', 'easy', 'simple'];
  jargonWords.forEach(word => {
    const regex = new RegExp(`\\b${word}\\b`, 'gi');
    if (regex.test(content)) {
      warnings.push(`STYLE ADVISORY: Found passive modifier "${word}". Google documentation guidelines recommend active procedural verbs.`);
    }
  });

  // Report results
  if (errors.length > 0) {
    console.log('\n❌ Validation Failed with errors:');
    errors.forEach(err => console.log(`  - ${err}`));
    if (warnings.length > 0) {
      console.log('\n⚠️ Style Warnings:');
      warnings.forEach(warn => console.log(`  - ${warn}`));
    }
    process.exit(1);
  } else {
    console.log('\n✅ Validation Passed: Codelab structure complies with required guidelines!');
    if (warnings.length > 0) {
      console.log('\n⚠️ Style Advisories / Warnings:');
      warnings.forEach(warn => console.log(`  - ${warn}`));
    }
  }

} catch (err) {
  console.error(`❌ Error reading file: ${err.message}`);
  process.exit(1);
}
