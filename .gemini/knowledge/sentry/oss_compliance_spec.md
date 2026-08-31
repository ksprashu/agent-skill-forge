---
type: "Compliance Spec"
title: "Open Source Compliance & License Header Standard"
description: "Apache-2.0 licensing policies, SPDX copyright headers, repository hygiene, and Google OSS compliance automation."
resource: "file:///Users/ksprashanth/code/github/agent-skill-forge/skills/google-oss/SKILL.md"
tags: ["sentry", "compliance", "oss", "apache-2.0", "license-headers", "spdx"]
---

# 📜 Open Source Compliance & License Standards

Licensing standards, copyright header requirements, and repository governance for **Agent Skill Forge**.

---

## 1. Apache-2.0 License Governance

All code, scripts, and documentation in Agent Skill Forge are released under the **Apache License, Version 2.0**.
- Top-level `LICENSE` file present at root.
- Clear `CONTRIBUTING.md` outlining the Contributor License Agreement (CLA) process.
- `CODE_OF_CONDUCT.md` enforcing contributor community standards.
- `SECURITY.md` defining responsible vulnerability disclosure.

---

## 2. Standard Copyright & License Header

Every source script (`.py`, `.sh`, `.js`) must contain the official license header:

```python
# Copyright 2026 Agent Skill Forge Contributors
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

## 3. Automated Compliance Audit via `/google-oss`

The `google-oss` skill automates repo-wide compliance scans:
- **Header Verification**: Ensures all source files contain valid Apache-2.0 headers.
- **Path Sanitization**: Checks for and scrubs internal corporate hostnames or intranet links.
- **Dependency Audit**: Validates that all third-party dependencies carry compatible permissive open-source licenses (MIT, Apache-2.0, BSD).
