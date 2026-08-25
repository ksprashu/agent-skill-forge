#!/usr/bin/env node

/**
 * Copyright 2026 Google LLC.
 * SPDX-License-Identifier: Apache-2.0
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { execSync } = require('child_process');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

// Helper: Ask a single-line question
function ask(query) {
  return new Promise(resolve => rl.question(query, resolve));
}

// Helper: Ask for multiline content
function askMultiline(promptText) {
  return new Promise(resolve => {
    console.log(promptText);
    console.log('✏️  Type or paste your content. Type "END" on a new line by itself to finish:');
    let lines = [];
    
    const onLine = line => {
      if (line.trim() === 'END') {
        rl.off('line', onLine);
        resolve(lines.join('\n'));
      } else {
        lines.push(line);
      }
    };
    
    rl.on('line', onLine);
  });
}

// Find existing codelab projects in current workspace
function scanForCodelabs() {
  const dirs = fs.readdirSync(process.cwd(), { withFileTypes: true })
    .filter(dirent => dirent.isDirectory())
    .map(dirent => dirent.name)
    .filter(name => !['node_modules', '.git', 'references', 'scripts', 'assets', 'tools'].includes(name));

  const codelabs = [];
  dirs.forEach(dir => {
    const labFile = path.join(process.cwd(), dir, 'codelab', 'index.lab.md');
    if (fs.existsSync(labFile)) {
      codelabs.push({ slug: dir, filePath: labFile });
    }
  });
  return codelabs;
}

// Parse index.lab.md into a structured object
function parseCodelab(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  
  // 1. Extract frontmatter
  let frontmatter = '';
  let bodyStartIndex = 0;
  if (content.startsWith('---')) {
    const endFrontmatter = content.indexOf('---', 3);
    if (endFrontmatter !== -1) {
      frontmatter = content.substring(0, endFrontmatter + 3);
      bodyStartIndex = endFrontmatter + 3;
    }
  }
  
  const bodyText = content.substring(bodyStartIndex);
  
  // 2. Parse main title (H1)
  const h1Match = bodyText.match(/^#\s+(.+)/m);
  const title = h1Match ? h1Match[1].trim() : 'Untitled Codelab';
  
  // 3. Segment steps (by H2: ## )
  const steps = [];
  const rawSteps = bodyText.split(/^##\s+/m);
  const preamble = rawSteps[0] || '';
  
  for (let i = 1; i < rawSteps.length; i++) {
    const rawStep = rawSteps[i];
    const stepLines = rawStep.split('\n');
    const titleLine = stepLines[0].trim();
    
    let duration = '';
    let contentStartIndex = 1;
    
    for (let j = 1; j < Math.min(stepLines.length, 5); j++) {
      const line = stepLines[j].trim();
      if (line.startsWith('Duration:')) {
        duration = line.replace('Duration:', '').trim();
        contentStartIndex = j + 1;
        break;
      }
    }
    
    const body = stepLines.slice(contentStartIndex).join('\n').trim();
    steps.push({
      title: titleLine,
      duration: duration,
      body: body
    });
  }
  
  return {
    frontmatter,
    preamble,
    title,
    steps
  };
}

// Stringify parsed structure back to markdown
function stringifyCodelab(parsed) {
  let content = parsed.frontmatter ? parsed.frontmatter + '\n' : '';
  content += parsed.preamble.trim() + '\n\n';
  
  parsed.steps.forEach(step => {
    content += `## ${step.title}\n`;
    if (step.duration) {
      content += `Duration: ${step.duration}\n`;
    }
    content += `\n${step.body.trim()}\n\n`;
  });
  
  // Clean up consecutive excessive blank lines
  return content.replace(/\n{3,}/g, '\n\n');
}

// Render total duration string (MM:SS sum)
function calculateTotalDuration(steps) {
  let totalMin = 0;
  let totalSec = 0;
  
  steps.forEach(step => {
    if (step.duration) {
      const parts = step.duration.split(':');
      const min = parseInt(parts[0], 10) || 0;
      const sec = parseInt(parts[1], 10) || 0;
      totalMin += min;
      totalSec += sec;
    }
  });
  
  totalMin += Math.floor(totalSec / 60);
  totalSec = totalSec % 60;
  
  return `${totalMin.toString().padStart(2, '0')}:${totalSec.toString().padStart(2, '0')}`;
}

// Run external scripts (linter and fog index)
function runDiagnostics(filePath) {
  console.log('\n==================================================');
  console.log('🔍 RUNNING DETAILED QUALITY CHECKLIST DIAGNOSTICS');
  console.log('==================================================');
  
  try {
    const validatePath = path.join(process.cwd(), 'scripts', 'validate_codelab.cjs');
    const fogPath = path.join(process.cwd(), 'scripts', 'fog.cjs');
    
    if (fs.existsSync(validatePath)) {
      console.log(execSync(`node ${validatePath} "${filePath}"`, { encoding: 'utf8' }));
    } else {
      console.log('⚠️  validate_codelab.cjs script not found.');
    }
    
    if (fs.existsSync(fogPath)) {
      console.log(execSync(`node ${fogPath} "${filePath}"`, { encoding: 'utf8' }));
    } else {
      console.log('⚠️  fog.cjs script not found.');
    }
  } catch (err) {
    // If command fails (exits with code 1), execSync throws. Capture output from the error.
    if (err.stdout) console.log(err.stdout);
    if (err.stderr) console.error(err.stderr);
  }
  console.log('==================================================\n');
}

// Main Interactive Console Loop
async function main() {
  console.clear();
  console.log('==================================================');
  console.log('🚀  WELCOME TO THE INTERACTIVE CODELAB AUTHORING SYSTEM');
  console.log('==================================================');
  
  let codelabs = scanForCodelabs();
  let selectedLab = null;
  
  if (codelabs.length > 0) {
    console.log('\n📂 Found the following existing Codelabs in your workspace:');
    codelabs.forEach((lab, index) => {
      console.log(`  [${index + 1}] ${lab.slug} (${lab.filePath})`);
    });
    console.log(`  [N] Create / Initialize a brand new Codelab`);
    
    const choice = await ask('\n👉 Select a codelab index, or type "N" to create a new one: ');
    
    if (choice.trim().toUpperCase() === 'N') {
      selectedLab = await createNewCodelabFlow();
    } else {
      const idx = parseInt(choice, 10) - 1;
      if (idx >= 0 && idx < codelabs.length) {
        selectedLab = codelabs[idx];
      } else {
        console.log('❌ Invalid selection. Exiting.');
        rl.close();
        process.exit(1);
      }
    }
  } else {
    console.log('\n📂 No existing codelabs found in your workspace.');
    const initNew = await ask('👉 Do you want to initialize a new one? (Y/n): ');
    if (initNew.trim().toLowerCase() === 'n') {
      console.log('Exiting.');
      rl.close();
      process.exit(0);
    }
    selectedLab = await createNewCodelabFlow();
  }
  
  if (!selectedLab || !selectedLab.filePath) {
    console.log('❌ Error: No valid file selected. Exiting.');
    rl.close();
    process.exit(1);
  }
  
  // Load and parse the selected file
  let codelabState = parseCodelab(selectedLab.filePath);
  let isDirty = false;
  
  while (true) {
    console.log('\n==================================================');
    console.log(`📝 CURRENT ACTIVE: ${selectedLab.slug}`);
    console.log(`📌 Title:          ${codelabState.title}`);
    console.log(`🔢 Total Steps:     ${codelabState.steps.length}`);
    console.log(`⏳ Est. Duration:   ${calculateTotalDuration(codelabState.steps)} mins`);
    console.log(`💾 Pending Saves:  ${isDirty ? '🔴 YES (Unsaved changes)' : '🟢 NO (Up to date)'}`);
    console.log('==================================================');
    console.log('  [1] List/Show Codelab Outline');
    console.log('  [2] Add a Step (to the end)');
    console.log('  [3] Insert a Step (at specific index)');
    console.log('  [4] Edit an Existing Step (non-destructive)');
    console.log('  [5] Delete an Existing Step');
    console.log('  [6] Run Quality Linter & Readability Score');
    console.log('  [7] Save Changes and Sync Markdown');
    console.log('  [8] Exit Authoring Tool');
    console.log('==================================================');
    
    const option = await ask('\n👉 Choose an action (1-8): ');
    
    switch (option.trim()) {
      case '1':
        showOutline(codelabState);
        break;
        
      case '2':
        codelabState.steps.push(await askStepData(codelabState.steps.length + 1));
        isDirty = true;
        console.log('\n✅ Step successfully added to the end!');
        break;
        
      case '3':
        showOutline(codelabState);
        const insIdxStr = await ask(`\n👉 Enter the step number before which to insert (1-${codelabState.steps.length + 1}): `);
        const insIdx = parseInt(insIdxStr, 10) - 1;
        if (insIdx >= 0 && insIdx <= codelabState.steps.length) {
          const newStep = await askStepData(insIdx + 1);
          codelabState.steps.splice(insIdx, 0, newStep);
          isDirty = true;
          console.log(`\n✅ Step successfully inserted at position ${insIdx + 1}!`);
        } else {
          console.log('❌ Invalid index. Operation cancelled.');
        }
        break;
        
      case '4':
        showOutline(codelabState);
        const editIdxStr = await ask(`\n👉 Enter the step number to edit (1-${codelabState.steps.length}): `);
        const editIdx = parseInt(editIdxStr, 10) - 1;
        if (editIdx >= 0 && editIdx < codelabState.steps.length) {
          await editStepFlow(codelabState.steps[editIdx]);
          isDirty = true;
          console.log('\n✅ Step modified successfully!');
        } else {
          console.log('❌ Invalid step number. Operation cancelled.');
        }
        break;
        
      case '5':
        showOutline(codelabState);
        const delIdxStr = await ask(`\n👉 Enter the step number to DELETE (1-${codelabState.steps.length}): `);
        const delIdx = parseInt(delIdxStr, 10) - 1;
        if (delIdx >= 0 && delIdx < codelabState.steps.length) {
          const confirm = await ask(`⚠️ Are you sure you want to delete step ${delIdx + 1}: "${codelabState.steps[delIdx].title}"? (y/N): `);
          if (confirm.trim().toLowerCase() === 'y') {
            codelabState.steps.splice(delIdx, 1);
            isDirty = true;
            console.log('\n🗑️ Step deleted successfully!');
          } else {
            console.log('\n❌ Deletion cancelled.');
          }
        } else {
          console.log('❌ Invalid step number. Operation cancelled.');
        }
        break;
        
      case '6':
        // To run diagnostics on unsaved edits, we write a quick shadow/tmp sync first
        const tempPath = selectedLab.filePath;
        const currentContent = stringifyCodelab(codelabState);
        fs.writeFileSync(tempPath, currentContent);
        isDirty = false; // Synchronized for now
        runDiagnostics(tempPath);
        break;
        
      case '7':
        const finalContent = stringifyCodelab(codelabState);
        fs.writeFileSync(selectedLab.filePath, finalContent);
        isDirty = false;
        console.log('\n💾 Codelab synced and written to file successfully!');
        break;
        
      case '8':
        if (isDirty) {
          const leave = await ask('⚠️ You have unsaved changes! Do you want to save them before exiting? (Y/n/cancel): ');
          const lChoice = leave.trim().toLowerCase();
          if (lChoice === 'y' || lChoice === '') {
            fs.writeFileSync(selectedLab.filePath, stringifyCodelab(codelabState));
            console.log('💾 Saved. Goodbye!');
            rl.close();
            process.exit(0);
          } else if (lChoice === 'n') {
            console.log('Exiting without saving. Goodbye!');
            rl.close();
            process.exit(0);
          } else {
            console.log('Cancelled. Returning to menu.');
          }
        } else {
          console.log('Goodbye!');
          rl.close();
          process.exit(0);
        }
        break;
        
      default:
        console.log('❌ Invalid action. Choose an option from 1 to 8.');
    }
  }
}

// Flow for creating and scaffolding a new Codelab
async function createNewCodelabFlow() {
  console.log('\n==================================================');
  console.log('✨ INITIALIZE A NEW CODELAB');
  console.log('==================================================');
  const slug = await ask('👉 Enter a unique slug name (e.g., build-fastify-api): ');
  const safeSlug = slug.trim().toLowerCase().replace(/[^a-z0-9\-]/g, '-');
  
  if (!safeSlug) {
    console.log('❌ Invalid slug name.');
    return null;
  }
  
  const initScriptPath = path.join(process.cwd(), 'scripts', 'init_codelab.cjs');
  if (!fs.existsSync(initScriptPath)) {
    console.log('❌ Scaffolding utility scripts/init_codelab.cjs not found.');
    return null;
  }
  
  console.log(`\n🏗️  Running scaffolding CLI for: ${safeSlug}...`);
  try {
    console.log(execSync(`node ${initScriptPath} ${safeSlug}`, { encoding: 'utf8' }));
    return {
      slug: safeSlug,
      filePath: path.join(process.cwd(), safeSlug, 'codelab', 'index.lab.md')
    };
  } catch (err) {
    console.error('❌ Failed to run scaffolding script:', err.message);
    return null;
  }
}

// Show the step-by-step outline of the codelab
function showOutline(state) {
  console.log('\n==================================================');
  console.log(`📌 CODELAB STRUCTURE: "${state.title}"`);
  console.log('==================================================');
  if (state.steps.length === 0) {
    console.log('  (No steps added yet. Choose [2] to add your first step!)');
  } else {
    state.steps.forEach((step, index) => {
      console.log(`  [Step ${index + 1}]  Title:     "${step.title}"`);
      console.log(`             Duration:  ${step.duration || 'Not declared'}`);
      console.log(`             Content:   ${step.body.substring(0, 80).replace(/\n/g, ' ')}...`);
      console.log('  ------------------------------------------------');
    });
  }
  console.log(`⏱️  Total Duration sum: ${calculateTotalDuration(state.steps)} mins`);
  console.log('==================================================\n');
}

// Gather information for a new step
async function askStepData(stepNumber) {
  console.log(`\n==================================================`);
  console.log(`➕ ADD STEP DATA (POSITION ${stepNumber})`);
  console.log(`==================================================`);
  const title = await ask('👉 Step Title (e.g., Download starter code): ');
  const duration = await ask('👉 Step Duration (e.g., 05:00): ');
  const body = await askMultiline('\n👉 Enter Step Body (use Markdown syntax)');
  
  return {
    title: title.trim() || `Step ${stepNumber}`,
    duration: duration.trim() || '05:00',
    body: body.trim()
  };
}

// Non-destructively edit an existing step
async function editStepFlow(step) {
  console.log(`\n==================================================`);
  console.log(`✏️  EDITING STEP: "${step.title}"`);
  console.log(`==================================================`);
  console.log(`  [1] Edit Title (Currently: "${step.title}")`);
  console.log(`  [2] Edit Duration (Currently: "${step.duration}")`);
  console.log(`  [3] Edit Body Content (Currently: ${step.body.length} characters)`);
  console.log(`  [4] Done editing`);
  console.log(`==================================================`);
  
  while (true) {
    const editOpt = await ask('\n👉 Select edit parameter (1-4): ');
    
    if (editOpt.trim() === '1') {
      const newTitle = await ask(`👉 Enter new title (Press Enter to keep: "${step.title}"): `);
      if (newTitle.trim()) step.title = newTitle.trim();
      console.log('✅ Title updated!');
    } else if (editOpt.trim() === '2') {
      const newDuration = await ask(`👉 Enter new duration (Press Enter to keep: "${step.duration}"): `);
      if (newDuration.trim()) step.duration = newDuration.trim();
      console.log('✅ Duration updated!');
    } else if (editOpt.trim() === '3') {
      console.log('\n--- Current Body ---');
      console.log(step.body);
      console.log('--------------------');
      const newBody = await askMultiline('👉 Enter new step content:');
      if (newBody.trim()) step.body = newBody.trim();
      console.log('✅ Body content updated!');
    } else if (editOpt.trim() === '4') {
      break;
    } else {
      console.log('❌ Invalid choice.');
    }
  }
}

// Execute CLI
main().catch(err => {
  console.error('Fatal CLI Error:', err);
  rl.close();
  process.exit(1);
});
