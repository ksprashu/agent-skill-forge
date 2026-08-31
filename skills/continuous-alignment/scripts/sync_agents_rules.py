#!/usr/bin/env python3
"""Rule Synchronization & Token Budget Enforcer for Continuous Alignment

Syncs distilled memories from .gemini/knowledge/memories.jsonl into AGENTS.md
and path-scoped rules in .agents/rules/*.md. Enforces a strict 200-line budget
cap on the root AGENTS.md to prevent attention dilution and context rot.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MAX_ROOT_LINES = 200


def load_active_memories(memories_file: Path) -> List[Dict[str, Any]]:
    """Loads all active, non-superseded memory entries."""
    if not memories_file.exists():
        return []

    active = []
    superseded_ids = set()
    raw_entries = []

    try:
        with open(memories_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    raw_entries.append(obj)
                    if obj.get("supersedes"):
                        superseded_ids.add(obj["supersedes"])
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        sys.stderr.write(f"[sync_agents_rules] Error reading memories: {e}\n")
        return []

    for obj in raw_entries:
        if obj.get("status") == "active" and obj.get("memory_id") not in superseded_ids:
            active.append(obj)

    return active


def categorize_rules(memories: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Sorts memories into functional categories."""
    categories: Dict[str, List[Dict[str, Any]]] = {
        "command": [],
        "constraint": [],
        "architecture": [],
        "troubleshooting": [],
        "user_preference": []
    }
    for m in memories:
        cat = m.get("category", "constraint")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(m)
    return categories


def build_root_agents_content(
    project_name: str,
    categories: Dict[str, List[Dict[str, Any]]],
    overflow_rules: List[Dict[str, Any]]
) -> str:
    """Constructs the root AGENTS.md text adhering strictly to the line budget."""
    lines = [
        f"# {project_name} - Agent Invariants & Operations Guide",
        "",
        "> [!IMPORTANT]",
        "> This document contains hot invariants distilled continuously by the `continuous-alignment` engine.",
        "> Keep all modifications within the 200-line budget limit.",
        "",
        "---",
        "",
        "## 1. Fast-Path Verification & Operational Commands",
        ""
    ]

    # Section 1: Commands
    if categories["command"]:
        for item in categories["command"]:
            lines.append(f"- {item['statement']}")
    else:
        lines.append("- `pytest -v`: Run all repository test suites.")
        lines.append("- `python scripts/validate_skills.py`: Run frontmatter and PII linter.")

    lines.extend([
        "",
        "---",
        "",
        "## 2. Critical Negative Constraints & Architectural Invariants",
        ""
    ])

    # Section 2: Negative Constraints
    if categories["constraint"]:
        for item in categories["constraint"]:
            lines.append(f"- {item['statement']}")
    else:
        lines.append("- **Zero Third-Party Dependencies in Hooks**: Hook scripts must use Python stdlib only.")
        lines.append("- **Zero PII Leaks**: Never commit API keys, personal tokens, or real user email addresses.")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Verified Troubleshooting & Gotchas",
        ""
    ])

    # Section 3: Troubleshooting
    if categories["troubleshooting"]:
        for item in categories["troubleshooting"][:10]: # Cap to top 10
            lines.append(f"- {item['statement']}")
    else:
        lines.append("- No active troubleshooting gotchas recorded.")

    # Overflow notice if path-scoped rules exist
    if overflow_rules:
        lines.extend([
            "",
            "---",
            "",
            "## 4. Path-Scoped Subsystem Rules",
            "",
            "Detailed rules for individual subsystems are progressively loaded from `.agents/rules/`:",
            "- See [`.agents/rules/`](file:///.agents/rules/) for component-specific rules."
        ])

    lines.append("")
    return "\n".join(lines)


def sync_path_scoped_rules(workspace_path: Path, overflow_rules: List[Dict[str, Any]]) -> None:
    """Generates scoped rule files under .agents/rules/ for path-specific entries."""
    rules_dir = workspace_path / ".agents" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    grouped_by_scope: Dict[str, List[Dict[str, Any]]] = {}
    for r in overflow_rules:
        target = r.get("target_path_glob") or "general"
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", target).strip("_")
        if slug not in grouped_by_scope:
            grouped_by_scope[slug] = []
        grouped_by_scope[slug].append(r)

    for slug, rules in grouped_by_scope.items():
        file_path = rules_dir / f"{slug}.md"
        content = [
            f"# Path-Scoped Rules: {slug}",
            "",
            "> Auto-generated by `continuous-alignment` engine.",
            "",
            "---",
            ""
        ]
        for r in rules:
            content.append(f"### {r['statement']}")
            content.append(f"- **Rationale**: {r.get('rationale', 'Recorded project invariant')}")
            content.append(f"- **Confidence**: {r.get('confidence', 0.90)}")
            content.append("")

        with tempfile.NamedTemporaryFile("w", dir=str(rules_dir), delete=False, encoding="utf-8") as tf:
            tf.write("\n".join(content))
            temp_path = tf.name
        os.replace(temp_path, str(file_path))


def write_file_atomically(target_path: Path, content: str) -> None:
    """Safely writes a file using atomic renaming."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=str(target_path.parent), delete=False, encoding="utf-8") as tf:
        tf.write(content)
        temp_name = tf.name
    os.replace(temp_name, str(target_path))


def sync_rules(workspace_dir: str) -> Dict[str, Any]:
    """Synchronizes all distilled rules into AGENTS.md and path rules."""
    ws = Path(workspace_dir)
    memories_file = ws / ".gemini" / "knowledge" / "memories.jsonl"
    agents_file = ws / "AGENTS.md"

    memories = load_active_memories(memories_file)
    project_name = ws.name

    root_memories = []
    overflow_memories = []

    for m in memories:
        if m.get("scope") == "path_scoped" or m.get("target_path_glob"):
            overflow_memories.append(m)
        else:
            root_memories.append(m)

    categories = categorize_rules(root_memories)
    content = build_root_agents_content(project_name, categories, overflow_memories)

    # Check line count budget
    content_lines = content.splitlines()
    if len(content_lines) > MAX_ROOT_LINES:
        # Move excess troubleshooting & architecture into overflow
        while len(content_lines) > MAX_ROOT_LINES and (categories["troubleshooting"] or categories["architecture"]):
            if categories["troubleshooting"]:
                overflow_memories.append(categories["troubleshooting"].pop())
            elif categories["architecture"]:
                overflow_memories.append(categories["architecture"].pop())
            content = build_root_agents_content(project_name, categories, overflow_memories)
            content_lines = content.splitlines()

    write_file_atomically(agents_file, content)

    if overflow_memories:
        sync_path_scoped_rules(ws, overflow_memories)

    return {
        "status": "success",
        "root_lines": len(content.splitlines()),
        "root_rules": len(root_memories),
        "overflow_rules": len(overflow_memories)
    }


def output_pre_invocation_pulse(workspace_dir: str) -> None:
    """Emits compact workspace context pulse for PreInvocation hook."""
    ws = Path(workspace_dir)
    memories_file = ws / ".gemini" / "knowledge" / "memories.jsonl"
    memories = load_active_memories(memories_file)

    constraints = [m['statement'] for m in memories if m.get('category') == 'constraint'][:3]
    commands = [m['statement'] for m in memories if m.get('category') == 'command'][:2]

    pulse = {
        "workspace": ws.name,
        "active_constraints": constraints,
        "recommended_commands": commands,
        "total_active_memories": len(memories)
    }
    print(json.dumps(pulse, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Synchronize and budget AGENTS.md rules")
    parser.add_argument("--workspace", default=os.getcwd(), help="Workspace directory")
    parser.add_argument("--pulse", action="store_true", help="Output compact PreInvocation context pulse")
    args = parser.parse_args()

    if args.pulse:
        output_pre_invocation_pulse(args.workspace)
    else:
        res = sync_rules(args.workspace)
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
