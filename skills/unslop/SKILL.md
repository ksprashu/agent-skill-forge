---
name: unslop
description: Code and content anti-bloat engine. Strips AI defensive boilerplate, removes redundant single-use wrappers, simplifies logic, and eliminates AI clichés while preserving exact behavior and green tests. Trigger via `/unslop`, `/deslop`, or `/simplify`.
---

# Unslop: Anti-AI Bloat & Code Simplification Engine

Prunes AI-generated over-engineering, defensive wrapper clutter, single-use helper functions, and sterile boilerplate from code and written artifacts.

---

## 🎯 The Laziness Protocol: "Subtract Before You Add"

AI models consistently produce "slop" by:
1. Adding unnecessary defensive `null` / `undefined` checks in trusted internal modules.
2. Wrapping simple 2-line standard library calls inside multi-layer helper classes.
3. Generating verbose boilerplate comments explaining obvious code.
4. Injecting repetitive error catch blocks that just rethrow generic errors.
5. In prose: overusing em-dashes (`—`), buzzwords (*delve, tapestry, demystify*), and emoji lists.

**Core Axiom**: The best code is code you didn't have to write. When refactoring or reviewing, actively seek opportunities to *delete* unnecessary lines while keeping tests completely green.

---

## 🛠️ Code Anti-Bloat Heuristics

1. **Inline Single-Use Helpers**: If a private function is only called in one place and does not isolate complex state or recursion, inline it.
2. **Remove Redundant Defensive Checks**: Trust type systems (TypeScript strict mode, Pydantic validated models) at internal module boundaries. Validate strictly at public boundaries; delete paranoid internal checks.
3. **Flatten Deeply Nested Control Flow**: Replace nested `if / else` ladders with early returns and guard clauses.
4. **Delete Ghost Abstractions**: Eliminate single-implementation interfaces, empty pass-through classes, and trivial builder wrappers.
5. **Strip Comment Clutter**: Delete comments that merely restate what the code clearly expresses. Preserve comments that explain non-obvious *why* or hardware/concurrency edge cases.

---

## ✍️ Content & Prose Anti-Bloat Heuristics

When run on markdown articles, blog posts, or PR summaries:
1. **Banish Em-Dashes**: Convert `—` to clean commas, semicolons, or separate sentences.
2. **Purge AI Clichés**: Banish *delve, testament, tapestry, demystify, furthermore, moreover, it's worth noting, in summary, pioneering, beacon, crucial*.
3. **Strip Excessive Bolding**: Remove mechanical bolding from the first 3 words of every bullet point. Let natural phrasing carry emphasis.

---

## 🚦 Verification Gate

Every `unslop` refactor MUST satisfy:
```
1. Existing automated test suites pass with ZERO modifications to assertions.
2. Public API surface, function signatures, and return contracts remain 100% identical.
3. Net line count decreases or remains equal while cognitive cyclomatic complexity drops.
```
