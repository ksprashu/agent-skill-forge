#!/usr/bin/env node

/**
 * Copyright 2026 Google LLC.
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Calculates the Gunning Fog Index for a given text file.
 * Formula: 0.4 * ( (words / sentences) + 100 * (complexWords / words) )
 */

const fs = require('fs');
const path = require('path');

const filename = process.argv[2];

if (!filename) {
  console.error("❌ Error: Please specify the path to your codelab markdown file.");
  console.error("Usage: node scripts/fog.cjs <filename>");
  process.exit(1);
}

try {
  const text = fs.readFileSync(filename, 'utf8');
  
  // Sentence Counting: Matches Speedgrapher's simple punctuation check
  const sentences = (text.match(/[.!?]+/g) || []).length || 1;

  // Word Counting: Remove punctuation, then split on whitespace
  const cleanText = text.replace(/[!"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]/g, ''); 
  const words = cleanText.split(/\s+/).filter(w => w.length > 0);
  const wordCount = words.length;
  
  if (wordCount === 0) {
    console.log("Gunning Fog Index: 0 (No words found)");
    process.exit(0);
  }

  // Complex Words: 3+ syllables
  // Simple heuristic counting vowel groups [aeiouy]+
  const complexWordCount = words.filter(w => {
    const vowelGroups = w.match(/[aeiouy]+/gi);
    const syllables = vowelGroups ? vowelGroups.length : 1;
    return syllables >= 3;
  }).length;

  const avgSentenceLength = wordCount / sentences;
  const percentComplexWords = (complexWordCount / wordCount) * 100;
  
  const fogIndex = 0.4 * (avgSentenceLength + percentComplexWords);
  
  console.log(`🔍 Analyzing Readability Metrics for: ${path.basename(filename)}`);
  console.log(`--------------------------------------------------`);
  console.log(`📝 Total Words:     ${wordCount}`);
  console.log(`📝 Sentences:       ${sentences}`);
  console.log(`📝 Complex Words:   ${complexWordCount} (${percentComplexWords.toFixed(1)}%)`);
  console.log(`📊 Gunning Fog:     ${fogIndex.toFixed(2)}`);
  console.log(`--------------------------------------------------`);
  
  // Target: index < 12 (General Audience)
  if (fogIndex >= 18) {
     console.log("🔴 Readability: Hard to Read (Try shortening sentences and using simpler words)");
     process.exit(1); // Exit with code 1 if it's too complex, or let it pass with warning? Let's just output
  } else if (fogIndex >= 13) {
     console.log("🟡 Readability: Professional Audiences (Acceptable but could be simplified)");
  } else if (fogIndex >= 9) {
     console.log("🟢 Readability: General Audiences (Ideal for developer codelabs)");
  } else {
     console.log("🟢 Readability: Simplistic");
  }

} catch (err) {
  console.error(`❌ Error reading file: ${err.message}`);
  process.exit(1);
}
