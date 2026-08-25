# 📖 Agent Skill Forge User Guide

A practical handbook for using the **Agent Skill Forge** ecosystem in your everyday development workflows.

---

## 🎯 Global Action Verbs Walkthrough

### 1. Requirements & Intent Engineering
*   **`/prompt`**: Use whenever you have an underspecified or complex request. The prompt writer conducts a Socratic interview, builds a dependency DAG (`task_graph.json`), and generates modular intent directives.
*   **`/grill`**: Use when you need to align on a spec quickly. The agent asks strictly **one question at a time**, attaches its best guess/hypothesis, and automatically terminates when 95% confidence is reached, writing a clean `CONTEXT.md`.

### 2. Specification & Planning
*   **`/spec`** (Autonomous or manual): Generates structured specifications grounded in official documentation. Enforces non-goals, data contracts, and dual links before writing any code.
*   **`/plan`** (Autonomous or manual): Decomposes specifications into vertical, testable task slices with explicit dependency checkpoints.

### 3. Implementation & Testing
*   **`/test`** (Autonomous or manual): Enforces Test-Driven Development (TDD) and Prove-It bug reproduction loops. Tests must fail before implementation code is written.
*   **`/unslop`** (Autonomous or manual): Eliminates AI clichés (*delve*, *testament*, *tapestry*), inlines unnecessary single-use helper functions, removes ghost wrappers, and applies the Laziness Protocol ("Subtract before you add").

### 4. Verification & Review
*   **`/verify`** (Autonomous or manual): Runs the Expectation-Grounded Alignment (EGA) engine. Combines deterministic static check scripts with 6-persona blinded judge rubrics and doubt-driven adversarial disproof.
*   **`/review`** (Autonomous or manual): Conducts a rigorous 5-axis code review across correctness, readability, architecture, security, and performance.

### 5. Documentation & Presentation
*   **`/docs`**: Generates full SDLC documentation sheets and compiles them into interactive, single-file HTML presentations across 4 premium Stitch themes (`technical`, `obsidian`, `proscript`, `dynamics`).
*   **`/catalog`**: Scaffolds and indexes Google Open Knowledge Format (OKF) bundles for long-term codebase memory.

### 6. Creative & Compliance
*   **`/voice`**: Analyzes typing cadence and extracts linguistic style markers.
*   **`/copy-write`**: Technical drafting companion using Profile-Overlay personalization.
*   **`/google-oss`**: Runs Google Open Source compliance checks, adds license headers, and validates repo cleanliness.
*   **`/codelab`**: Scaffolds interactive, polyglot Google Codelab tutorials.
*   **`/image-gen`**: Generates architecture diagrams and blog assets using Gemini Flash Image.

---

## 🛠️ Project-Scoped JIT Workflow

Don't pollute your global agent instructions with every framework or tool. Bootstrap domain skills only into repositories that need them:

```bash
# 1. Navigate to your project directory
cd ~/code/my-awesome-app

# 2. Bootstrap the required skills
python3 ~/code/github/agent-skill-forge/scripts/sync_skills.py --project . --skills frontend-ui-engineering,performance-optimization

# 3. Your agent now automatically has access to those skills within this repo!
```
