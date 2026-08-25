# Codelab Best Practices

When creating a codelab, you must adhere to these best practices derived from successful projects.

## 1. General Codelab Structure & Flow
-   **Introduction (Overview):** Always start with an engaging overview, a clear 'What you will learn' (including a high-level architecture diagram), and 'What you need'.
-   **Logical Progression:** Arrange steps in a natural, logical order (e.g., Setup -> Environment -> Backend -> Deploy Backend -> Frontend -> Deploy Frontend -> Conclusion -> Cleanup).
-   **Step Summaries:** End each major step with a 'Summary' that recaps what was accomplished and explicitly invites the user to the next step.

## 2. Pedagogical Approaches
-   **Active Learning:** Incorporate 'Challenge: Write it yourself!' sections to encourage users to code before revealing solutions.
-   **Tool Demonstration:** For AI-powered tools (like Gemini CLI for code generation, Antigravity for UI), provide clear prompts and show the power of delegation.
-   **Doc-Driven Vibe Coding:** When asking an AI to write code for a complex API (e.g., Antigravity connecting to ADK), **provide the URL to the official documentation** in the prompt instead of hardcoding the schema. This teaches users to leverage the AI's ability to "read the manual" and makes the prompt more resilient to version changes.
-   **Contextual Reminders:** Consistently remind users whether to use 'Cloud Shell terminal (or local terminal)' and 'Cloud Shell Editor (or local editor)'.

## 3. Image Handling & Generation
-   **Visual-First:** Use custom infographics and screenshots for key setup and conceptual steps to improve clarity and engagement.
-   **Logo Accuracy:** For official product logos, strive for pixel-perfect textual descriptions in prompts, or use actual image files as references if available.
-   **Consistent Sizing:** Use HTML `<img src="..." alt="..." width="624.00" />` tags for consistent image rendering width (624px is a good standard for codelabs).

## 4. Tooling Best Practices & Commands
-   **Dependency Management:** Use `uv` for managing dependencies and virtual environments in Python. Example: `uv venv` to create, `uv pip install -r requirements.txt` to install.
-   **Environment Configuration:** For codelabs using Google Cloud, ensure the correct project is configured using `gcloud config set project <PROJECT_ID>`.
-   **Verification:** Codelabs should include steps to verify deployments, for example by using `curl` or opening the URL in a browser.
-   **Cleanup:** A crucial final step is providing cleanup commands, like `gcloud run services delete`, and instructions for deleting the Google Cloud Project to avoid incurring costs.

## 5. Folder Structure Guidelines
Every codelab MUST be created inside a dedicated scoped folder (the `<codelab-slug>`) to prevent namespace collisions and maintain a clean separation between authoring context and distributable assets.

-   **`<codelab-slug>/` (Root):** The scoped parent folder for the individual codelab.
-   **`design-doc.md` & `context.md`:** Reside at the root of the scoped folder. These are author-facing documents used for thinking, planning, and unstructured notes. They are NOT part of the final distributable codelab.
-   **`codelab/` folder:** Contains ONLY the distributable codelab instructional content (`index.lab.md`) and its specific assets (`img/`). No application code or author context should be here.
-   **`app/` folder:** Contains the starter/supporting application code that the user will clone and work on. Resides at the scoped root.
-   **`app/solutions/` folder:** Contains the "answer key" sub-folders for each major step, plus a `final/` folder with the completed application state. Keep this in sync with the `index.lab.md` narrative.
-   **`tools/` folder:** Shared utilities and tools specific to this codelab, located at the scoped root.

## 6. Coding & Licensing Standards
To ensure legal compliance and maintainability, all code associated with codelabs must follow these standards.

### **6.1 License Headers**
Every script, code file, and snippet MUST include the following copyright header at the very top:
```
Copyright 2026 Google LLC.
SPDX-License-Identifier: Apache-2.0
```

### **6.2 Path Hygiene**
**Never use hardcoded absolute paths** (e.g., `/Users/yourname/...`). Hardcoded paths cause environments to break for other users and AI agents.
- **Prefer Relative Paths:** Use paths relative to the project root.
- **Use Environment Variables:** Use `process.env` (Node) or `os.environ` (Python) for dynamic locations.
- **Home Expansion:** Use `~` or platform-agnostic home directory lookups.

### **6.3 Code Quality & Style**
Follow the idiomatic standards for the language being used (e.g., PEP 8 for Python, Google Style Guide for TypeScript). Ensure code is self-documenting and includes meaningful comments for complex logic.

## 7. Reference Grounding & Hyperlinking Standards
To ensure codelabs are authoritative, educational, and grounded in primary sources:

- **Product Dual-Linking**: When introducing any product, service, SDK, or framework (e.g., Cloud Run, Fastify, Gemini API), provide both the **Product Landing Page** link and the **Official Documentation Landing Page** link:
  ```markdown
  In this step, we deploy our application to [Google Cloud Run](https://cloud.google.com/run) ([Docs](https://cloud.google.com/run/docs)).
  ```
- **Doc-Driven Vibe Coding**: In challenge steps and code-generation prompts, provide official documentation links directly in the prompt so the user (and AI model) grounds code in official schemas.
- **Knowledge Catalog Reference Indexing**: Use `knowledge-catalog` to harvest and aggregate all reference links into `.gemini/knowledge/<SHORT_ID>/scout/references.md` before authoring `index.lab.md`.
- **Mandatory "Further Reading" Sub-section**: Conclude the final step or each major module with a dedicated `### 📚 Further Reading & References` sub-section listing official docs, deep-dive articles, GitHub repos, and video tutorials.