# Google Cloud Trial Credit Redemption & Antigravity Sign-In Guidelines

When a codelab requires users to redeem Google Cloud credits via a **Trial Billing Account** or the **Google Developer Program (GDP)** banner, follow these rules:

1. **Always Add `Enable_GDP_Credits_Banner: True` in Frontmatter:**
   Include `Enable_GDP_Credits_Banner: True` in the YAML frontmatter of `index.lab.md` so the codelab renderer displays the top credit claim banner automatically.
2. **Use "Gemini Platform" (Never "Vertex AI"):**
   Refer to Google Cloud's enterprise AI offering as **[Gemini Platform](https://cloud.google.com/products/gemini-enterprise-agent-platform)** (`https://cloud.google.com/products/gemini-enterprise-agent-platform`).
3. **Cover All Three Antigravity (`agy`) Sign-In Flows:**
   When authenticating Google Antigravity (`agy`), document:
   - **Option A: Personal Gmail Login (`@gmail.com`)** for personal Pro/Ultra subscriptions.
   - **Option B: Google Workspace / Business Plan + Google Cloud Project** (`gcloud config set project <PROJECT_ID>`) for Gemini Platform credits and quota.
   - **Option C: Custom Enterprise SSO / Application Default Credentials (ADC)** (`gcloud auth application-default login`) for federated corporate identities.

## Reusable Snippets

These mascot-free setup snippets handle standard Google Cloud onboarding cleanly out of the box:

1.  **Project Setup & Credits:** Use `references/snippets/setup-project.md`. Handles trial credit redemption, project creation, and billing verification.
2.  **Environment Setup:** Use `references/snippets/setup-environment.md`. Covers Google Cloud Shell and local terminal options.
3.  **CLI / Harness Intro:** Use `references/snippets/intro-gemini-cli.md`. Introduces terminal setup and verification.

## Optional Setup Comic Slots

When an optional character pack resolves (`node <skill-dir>/scripts/characters.cjs status` exits `0`) and declares a `comics` map (or `common-comics/*.png`), copy those comics into the codelab's `img/` folder for the corresponding setup steps (`activate_billing`, `create_project`, `verify_billing`, `environment_setup`). When no character pack is installed (`exit 1`), use clean annotated console screenshots or architecture diagrams instead.
