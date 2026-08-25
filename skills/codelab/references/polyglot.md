# Polyglot and Multi-Language Codelab Design

When designing codelabs that support multiple programming languages, follow these structures.

## 1. Modular Code Blocks (Preferred)

Rather than maintaining separate codelabs for each language, use a single codelab and structure code samples with clear file extensions or language-specific tabs in the rendering platform.

```md
### Write the solution code

Choose your preferred programming language below to see the implementation:

> aside positive
> Ensure you run this inside the correct language environment directory (either `app/python` or `app/node`).

**Python**
```python
# python code
```

**Node.js (TypeScript)**
```typescript
// node code
```
```

## 2. Directory Layout for Polyglot Projects

When initializing polyglot codelabs, adjust the scaffold directory structure to separate environments clearly:

```
<codelab-slug>/
  ├── codelab/
  │     └── index.lab.md
  ├── app/
  │     ├── python/           <-- Python environment
  │     ├── node/             <-- Node environment
  │     └── solutions/
  │           ├── python/     <-- Python step solutions
  │           └── node/       <-- Node step solutions
  └── design-doc.md
```

## 3. Keep Explanations Language-Agnostic

Keep the textual descriptions focused on the conceptual, architectural, or API flows (e.g. "Create an HTTP GET endpoint that queries Firestore..."). Let the code snippets themselves handle language-specific syntax variations. This avoids redundant prose.
