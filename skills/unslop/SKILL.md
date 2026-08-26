---
name: unslop
description: Strip AI boilerplate, fluff words, and redundant single-use wrappers from code and prose. Trigger via /unslop or when cleaning code.
---

# Unslop: Code & Prose Simplification

Strip AI tells, defensive boilerplate, ghost wrappers, and sterile prose from codebases and documents.

---

## 🎯 Goal
Eliminate unnecessary code and words while preserving 100% of functional behavior and keeping all tests green.

---

## 📋 Step-by-Step Workflow

1. **Scan for Bloat**: Identify single-use wrappers, paranoid internal checks, empty pass-through functions, or AI buzzwords.
2. **Subtract First**: Delete or inline redundant abstractions before modifying logic.
3. **Flatten Logic**: Replace nested conditionals with early return guard clauses.
4. **Clean Comments & Prose**: Remove comments that merely repeat code. Banish AI words (*delve*, *testament*, *tapestry*, *demystify*).
5. **Verify Tests**: Run test suite to guarantee zero regressions.

---

## 💡 Concrete Examples

### Example 1: Inlining Ghost Wrappers
**Before (AI Slop):**
```typescript
class StringFormatterService {
  public static sanitizeAndTrim(input: string | null | undefined): string {
    if (input === null || input === undefined) {
      return '';
    }
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

### Example 2: Prose Simplification
**Before (AI Slop):**
```markdown
In today's fast-paced digital landscape, it's crucial to delve into the tapestry of microservices. Furthermore, this innovative approach stands as a testament to modern architectural excellence.
```

**After (Unslopped):**
```markdown
Microservices separate system responsibilities into independently deployable services. This reduces deployment blast radiuses and lets teams scale components individually.
```

---

## 🚫 Hard Constraints

*   **NEVER** change public API signatures or return types.
*   **NEVER** delete validation checks at untrusted boundaries (network inputs, user forms, file uploads).
*   **NEVER** modify test assertions just to make an aggressive refactor pass.
*   **NEVER** remove comments explaining hardware quirks, non-obvious business rules, or concurrency locks.
