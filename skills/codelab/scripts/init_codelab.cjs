/**
 * Copyright 2026 Google LLC.
 * SPDX-License-Identifier: Apache-2.0
 */

const fs = require('fs');
const path = require('path');

const codelabSlug = process.argv[2];

if (!codelabSlug) {
    console.error('❌ Error: Please provide a codelab name/slug.');
    console.error('Usage: node scripts/init_codelab.cjs <codelab-slug>');
    process.exit(1);
}

const targetDir = path.resolve(process.cwd(), codelabSlug);

console.log(`Scaffolding Codelab structure in: ${targetDir}`);

const directories = [
    'codelab',
    'codelab/img',
    'app',
    'app/solutions',
    'app/solutions/final',
    'tools'
];

directories.forEach(dir => {
    const fullPath = path.join(targetDir, dir);
    if (!fs.existsSync(fullPath)) {
        fs.mkdirSync(fullPath, { recursive: true });
        console.log(`✅ Created: ${dir}/`);
    } else {
        console.log(`ℹ️ Already exists: ${dir}/`);
    }
});

const header = `<!--
Copyright 2026 Google LLC.
SPDX-License-Identifier: Apache-2.0
-->
`;

const defaultLabContent = `---
description: [The codelab description. E.g., "In this codelab you learn how to write a codelab."]
id: ${codelabSlug}
keywords: docType:Codelab, category:Cloud, skill:Intermediate
feedback link: https://github.com/googlecodelabs/feedback/issues/new?title=${codelabSlug}%20Feedback&labels=gemini,codelab&assignees=<github-handle>
authors: Prashanth Subrahmanyam
layout: paginated
---

${header}

# Title

## Overview
Duration: 02:00

What you will build...
`;

const labFile = path.join(targetDir, 'codelab', 'index.lab.md');
if (!fs.existsSync(labFile)) {
    fs.writeFileSync(labFile, defaultLabContent);
    console.log('✅ Created: codelab/index.lab.md');
} else {
    console.log('ℹ️ Already exists: codelab/index.lab.md');
}

const designDocContent = `${header}

# Design Doc

## Persona & Theme
- Persona:
- Theme:

## Logical Flow
1. Setup
2. Environment
3. Backend
4. Frontend
5. Deploy
6. Conclusion & Cleanup
`;

const designDocFile = path.join(targetDir, 'design-doc.md');
if (!fs.existsSync(designDocFile)) {
    fs.writeFileSync(designDocFile, designDocContent);
    console.log('✅ Created: design-doc.md');
} else {
    console.log('ℹ️ Already exists: design-doc.md');
}

const contextDocContent = `${header}

# Context

This file is used to store unstructured notes, references, and additional context for the codelab that shouldn't be part of the design doc or the final distributable.
`;

const contextDocFile = path.join(targetDir, 'context.md');
if (!fs.existsSync(contextDocFile)) {
    fs.writeFileSync(contextDocFile, contextDocContent);
    console.log('✅ Created: context.md');
} else {
    console.log('ℹ️ Already exists: context.md');
}

console.log('🎉 Scaffolding complete!');
