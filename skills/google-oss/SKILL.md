---
name: google-oss
description: Audit repositories for Open Source compliance, Apache-2.0 license headers, and clean boundaries. Trigger via /google-oss.
disable-model-invocation: true
---

# Google OSS: Open Source Compliance & License Auditor

Bring codebases into compliance with Google Open Source standards and license requirements.

---

## 🎯 Goal
Ensure repository contains required licensing (`LICENSE`, `CONTRIBUTING.md`), license headers on source files, and zero internal corp URLs or secrets.

---

## 📋 Step-by-Step Workflow

1. **Scrub Internal Artifacts**: Scan for internal hostnames (`.google.com`, `.corp.google.com`) and private employee usernames.
2. **Ensure Core Files Exist**: Verify `LICENSE` (Apache-2.0), `CONTRIBUTING.md`, and `CODE_OF_CONDUCT.md` are present.
3. **Apply License Headers**: Check that all source files (`.py`, `.ts`, `.go`, `.java`) contain the standard copyright header:
   ```bash
   addlicense -c "Google LLC" -l apache ./src
   ```
4. **Update README**: Add the standard "Not an officially supported Google product" disclaimer if applicable.

---

## 💡 Concrete Example

### Apache 2.0 Header Fixture (`src/main.py`)
```python
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
```

---

## 🚫 Hard Constraints

*   **NEVER** publish repositories containing internal corp hostnames or private employee email addresses.
*   **NEVER** skip license headers on new source code files.
