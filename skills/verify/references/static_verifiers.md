# Static Verifiers: Deterministic Check Engineering

Static verifiers are deterministic, programmatic checks executed locally on disk during the **Dual-Verification Gate** phase of Expectation-Grounded Alignment (EGA).

They provide immediate, zero-cost, non-flaky verification without relying on non-deterministic LLM evaluation.

---

## 1. Verifiers for Coding Tasks

When the task involves software development, data pipelines, or infrastructure scripts, the Orchestrator generates a suite of deterministic static checks:

```python
# Pattern: verify_static_code.py
import sys
import subprocess
import json
from pathlib import Path

def run_cmd(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def main():
    errors = []
    
    # 1. Syntax Check / Compilation
    code, stdout, stderr = run_cmd("python -m py_compile src/*.py")
    if code != 0:
        errors.append(f"Syntax Error:\n{stderr}")
        
    # 2. Type Checking & Linters
    code, stdout, stderr = run_cmd("flake8 src/ --max-line-length=120")
    if code != 0:
        errors.append(f"Linter Violations:\n{stdout}")
        
    # 3. Unit Test Execution
    code, stdout, stderr = run_cmd("pytest tests/ -v")
    if code != 0:
        errors.append(f"Test Failures:\n{stdout}\n{stderr}")

    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
        sys.exit(1)
    
    print(json.dumps({"status": "PASS"}, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## 2. Verifiers for Non-Coding Tasks

For non-coding tasks (research dossiers, strategy documents, architecture specs, user guides), static checks evaluate structural integrity, link health, citation density, and constraint compliance.

### A. Document Structural AST Verifier (`verify_static_doc.py`)
```python
import sys
import re
import json
from pathlib import Path

def check_markdown_document(filepath, required_sections, min_words, max_words, min_tables):
    path = Path(filepath)
    if not path.exists():
        return False, [f"File not found: {filepath}"]
    
    content = path.read_text(encoding="utf-8")
    errors = []
    
    # Word Count Check
    words = len(content.split())
    if words < min_words:
        errors.append(f"Word count ({words}) below minimum ({min_words})")
    elif max_words and words > max_words:
        errors.append(f"Word count ({words}) exceeds maximum ({max_words})")
        
    # Section Heading Check
    for section in required_sections:
        pattern = re.compile(rf"^#+\s+.*{re.escape(section)}.*", re.IGNORECASE | re.MULTILINE)
        if not pattern.search(content):
            errors.append(f"Missing mandatory section: '{section}'")
            
    # Table Count Check
    table_matches = re.findall(r"^\|.*\|$", content, re.MULTILINE)
    # Estimate table count based on divider lines (|---|)
    table_dividers = [m for m in table_matches if "---" in m]
    if len(table_dividers) < min_tables:
        errors.append(f"Found {len(table_dividers)} tables, minimum required is {min_tables}")
        
    # Prohibited Phrases Check
    prohibited = ["TBD", "TODO", "as an AI", "in conclusion", "various factors"]
    for phrase in prohibited:
        if re.search(rf"\b{re.escape(phrase)}\b", content, re.IGNORECASE):
            errors.append(f"Contains prohibited placeholder/phrase: '{phrase}'")

    # File / Link Resolution Check
    file_links = re.findall(r"\[.*?\]\((file:///[^\)]+)\)", content)
    for link in file_links:
        clean_path = link.replace("file://", "").split("#")[0]
        if not Path(clean_path).exists():
            errors.append(f"Broken file link detected: {link}")

    return len(errors) == 0, errors

def main():
    target_file = sys.argv[1] if len(sys.argv) > 1 else "output.md"
    passed, errors = check_markdown_document(
        target_file,
        required_sections=["Executive Summary", "Risk Matrix", "Roadmap"],
        min_words=500,
        max_words=5000,
        min_tables=1
    )
    if not passed:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
        sys.exit(1)
    
    print(json.dumps({"status": "PASS"}, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## 3. Schema & Constraint Assertions (`rubric.json`)

Along with `verify_static_doc.py`, the Orchestrator generates a machine-readable schema specifying target parameters:

```json
{
  "short_id": "PRMT-8F21",
  "target_artifact": "docs/architecture_spec.md",
  "static_constraints": {
    "min_word_count": 800,
    "max_word_count": 3000,
    "mandatory_headings": [
      "System Context & Boundaries",
      "Data Model & Contracts",
      "Security Threat Matrix",
      "Deployment Topology"
    ],
    "mandatory_mermaid_diagrams": 1,
    "mandatory_data_tables": 2,
    "prohibited_terms": ["TBD", "TODO", "as an AI"]
  }
}
```
