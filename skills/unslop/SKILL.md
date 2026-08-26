---
name: unslop
description: Strip AI boilerplate, fluff words, and redundant single-use wrappers from code, text, analyses, and designs. Trigger via /unslop or when cleaning outputs.
---

# Unslop: Universal Anti-Bloat & Simplification Engine

Strip AI tells, defensive boilerplate, sterile prose, and unnecessary complexity across code, prose, system analyses, and visual designs.

---

## 🎯 Goal
Eliminate low-signal clutter while preserving 100% of functional behavior, meaning, and accuracy. Subtract before you add.

---

## 📋 Step-by-Step Workflow

1. **Detect AI Bloat**:
   * **In Code**: Paranoid internal type-checks, single-use wrapper classes, verbose restatement comments, over-nested conditionals.
   * **In Text / Prose**: Buzzwords (*delve*, *testament*, *tapestry*, *demystify*, *furthermore*), em-dashes (`—`), bolding the first 3 words of every bullet.
   * **In Analysis / Specs**: Fluffy pseudo-academic introductions, repetitive summaries, speculation without data.
   * **In Diagrams / UI**: Superfluous borders, excessive container nesting, gratuitous decorative shapes.
2. **Subtract First**: Delete or inline unnecessary abstractions, wrappers, and preamble before editing core logic.
3. **Flatten & Tighten**: Replace nested constructs with early returns; replace wordy sentences with direct statements.
4. **Verify Integrity**: Guarantee code tests pass, specs retain exact requirements, and prose retains factual substance.

---

## 💡 Concrete Examples Across Domains

### 1. Code Simplification
**Before (AI Slop):**
```typescript
class StringFormatterService {
  public static sanitizeAndTrim(input: string | null | undefined): string {
    if (input === null || input === undefined) return '';
    return input.trim().toLowerCase();
  }
}

export function processUsername(user: { name: string }) {
  const formatted = StringFormatterService.sanitizeAndTrim(user.name);
  return `user_${formatted}`;
}
```
**After (Unslopped):**
```typescript
export function processUsername(user: { name: string }) {
  return `user_${(user.name ?? '').trim().toLowerCase()}`;
}
```

### 2. Prose & Article Simplification
**Before (AI Slop):**
```markdown
In today's fast-paced digital landscape, it's crucial to delve into the tapestry of microservices. Furthermore, this innovative approach stands as a testament to modern architectural excellence.
```
**After (Unslopped):**
```markdown
Microservices separate system responsibilities into independently deployable units, reducing deployment blast radiuses.
```

### 3. Architecture & Analysis Simplification
**Before (AI Slop):**
```markdown
## Executive Strategic Overview
In this comprehensive analysis, we embark on a thorough exploration of database latency paradigms to unlock maximum synergies across our operational ecosystem...
```
**After (Unslopped):**
```markdown
## Problem & Metrics
Database p95 query latency currently spikes to 420ms under 1,000 req/s due to unindexed foreign keys on `orders.user_id`.
```

---

## 🚫 Hard Constraints

*   **NEVER** change public API signatures or return types.
*   **NEVER** delete security/validation checks at untrusted boundaries (HTTP inputs, user forms, file uploads).
*   **NEVER** remove comments explaining hardware quirks, non-obvious business rules, or concurrency locks.
*   **NEVER** alter the factual meaning or constraints of a specification or analysis.
