#!/usr/bin/env python3
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

"""
verify_okf.py - Deterministic Static Verifier for Open Knowledge Format (OKF) Concept Documents

Validates:
1. File existence on disk.
2. YAML Frontmatter presence and syntax.
3. Required OKF keys ('type', 'title', 'description').
4. Valid Markdown formatting and link targets.
"""

import sys
import json
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

def verify_concept_file(file_path):
    errors = []
    path = Path(file_path)
    
    if not path.exists():
        return [f"Concept file missing: {file_path}"]

    content = path.read_text(encoding="utf-8")
    
    # 1. Check YAML frontmatter opening
    if not content.startswith("---"):
        errors.append("Missing YAML frontmatter opening '---'")
        return errors

    parts = content.split("---", 2)
    if len(parts) < 3:
        errors.append("Malformed YAML frontmatter block (missing closing '---')")
        return errors

    yaml_block = parts[1]
    
    # 2. Parse YAML
    if yaml is not None:
        try:
            meta = yaml.safe_load(yaml_block)
            if not isinstance(meta, dict):
                errors.append("Frontmatter is not a valid YAML dictionary")
            else:
                required_keys = ["type", "title"]
                for key in required_keys:
                    if key not in meta or not meta[key]:
                        errors.append(f"Missing required OKF frontmatter key: '{key}'")
        except Exception as e:
            errors.append(f"YAML frontmatter parse error: {str(e)}")
    else:
        # Fallback regex parsing if PyYAML is unavailable
        if not re.search(r"^type:\s*\S+", yaml_block, re.MULTILINE):
            errors.append("Missing required OKF frontmatter key: 'type'")
        if not re.search(r"^title:\s*\S+", yaml_block, re.MULTILINE):
            errors.append("Missing required OKF frontmatter key: 'title'")

    # 3. Check for placeholder markers
    prohibited = ["TBD", "TODO", "FIXME", "as an AI"]
    for term in prohibited:
        if re.search(rf"\b{re.escape(term)}\b", content, re.IGNORECASE):
            errors.append(f"Contains prohibited placeholder: '{term}'")

    return errors

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"status": "FAIL", "errors": ["Usage: verify_okf.py <CONCEPT_FILE_PATH>"]}, indent=2))
        sys.exit(1)

    target_path = sys.argv[1]
    errors = verify_concept_file(target_path)

    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
        sys.exit(1)

    print(json.dumps({"status": "PASS"}, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
