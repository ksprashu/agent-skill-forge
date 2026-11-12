<!--
Copyright 2026 Google LLC.
SPDX-License-Identifier: Apache-2.0
-->

## Configuring Your AI Coding Harness

Duration: 05:00

Set up **[Google Antigravity](https://antigravity.google)** ([Docs](https://antigravity.google/docs)) (`agy`) so you can scaffold, build, and verify the project from natural-language prompts.

### **1. Install or Launch Google Antigravity**

Download the IDE or CLI from **[antigravity.google](https://antigravity.google)** and verify the CLI is on your `PATH`:

```bash
# Copyright 2026 Google LLC.
# SPDX-License-Identifier: Apache-2.0

agy --version
```

### **2. Authenticate Your Session**

Choose the sign-in method that matches your account:
- **Option A (Personal Gmail):** Sign in interactively with your `@gmail.com` account.
- **Option B (Google Workspace + Cloud Project):** Sign in with your Workspace identity and link your active Google Cloud project (`gcloud config set project <YOUR-PROJECT-ID>`).
- **Option C (Enterprise SSO / ADC):** Authenticate via `gcloud auth application-default login` when using federated enterprise credentials.

> aside positive
> **Tip:** Keep your coding agent open alongside a dedicated terminal tab for watching live server logs and running verification checks.

### Summary

Your AI coding environment is authenticated and ready to build the application.
