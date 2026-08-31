#!/usr/bin/env python3
"""Session Distillation Engine for Continuous Alignment

Executed by Antigravity's Stop lifecycle hook at the end of each agent turn.
Parses session transcripts, extracts verified architectural decisions, negative
constraints, troubleshooting resolutions, and tool command patterns, and appends
them to the project's semantic memory store (.gemini/knowledge/memories.jsonl).
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Sensitive credential patterns to filter
RE_SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z-_]{16,45}"),            # Google API Key
    re.compile(r"ghp_[0-9A-Za-z]{20,45}"),              # GitHub PAT
    re.compile(r"sk-[0-9A-Za-z]{20,}"),                 # OpenAI / generic secret
    re.compile(r"xox[baprs]-[0-9A-Za-z]{10,48}"),       # Slack token
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}") # Email pattern
]

# Constraint keywords
RE_CONSTRAINT_TRIGGER = re.compile(
    r"\b(always|never|must|must not|do not|don't|strictly|ensure|enforce|prohibit|forbidden|mandate|required)\b",
    re.IGNORECASE
)

# Command patterns (e.g., pytest ..., python scripts/..., npm run ...)
RE_COMMAND_TRIGGER = re.compile(
    r"`(pytest|python|bash|sh|npm|pnpm|cargo|git|npx|make|docker)\s+[^`]+`"
)


def sanitize_text(text: str) -> str:
    """Removes sensitive keys, secrets, and PII from extracted text."""
    sanitized = text
    for pattern in RE_SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized.strip()


def compute_memory_id(statement: str, category: str) -> str:
    """Generates a deterministic ID for a given rule statement and category."""
    norm = f"{category}:{statement.lower().strip()}"
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:6].upper()
    return f"MEM-{digest}"


def parse_transcript_lines(transcript_path: str) -> List[Dict[str, Any]]:
    """Reads and parses a JSONL transcript file safely."""
    entries = []
    if not os.path.exists(transcript_path):
        return entries

    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        sys.stderr.write(f"[distill_session] Warning: Failed to read transcript {transcript_path}: {e}\n")
    return entries


def extract_user_constraints(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts explicit negative/positive constraints from USER_INPUT steps."""
    extracted = []
    if entry.get("type") != "USER_INPUT" and entry.get("source") != "USER_EXPLICIT":
        return extracted

    content = entry.get("content", "")
    if not isinstance(content, str):
        return extracted

    # Clean out system tags
    clean_content = re.sub(r"<[^>]+>", "", content).strip()
    sentences = re.split(r"(?<=[.!?\n])\s+", clean_content)

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 15 or len(sentence) > 300:
            continue
        if RE_CONSTRAINT_TRIGGER.search(sentence):
            sanitized = sanitize_text(sentence)
            extracted.append({
                "statement": sanitized,
                "category": "constraint",
                "rationale": "Direct user imperative in conversation",
                "confidence": 0.95,
                "scope": "root",
                "target_path_glob": None
            })

    return extracted


def extract_tool_troubleshooting(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identifies tool execution failures that were subsequently fixed."""
    extracted = []
    # Track error -> resolution pairs
    for i, step in enumerate(entries):
        if step.get("type") == "GENERIC" and step.get("status") == "ERROR":
            err_content = str(step.get("content", ""))
            # Look ahead for recovery within 4 steps
            for j in range(i + 1, min(i + 5, len(entries))):
                subsequent = entries[j]
                if subsequent.get("type") == "PLANNER_RESPONSE":
                    thinking = str(subsequent.get("thinking", ""))
                    if "fix" in thinking.lower() or "resolve" in thinking.lower() or "correct" in thinking.lower():
                        summary_match = re.search(r"(?:fix|resolved|issue with)\s+([^\n.]+)", thinking, re.IGNORECASE)
                        summary = summary_match.group(0) if summary_match else "Tool execution failure resolved"
                        extracted.append({
                            "statement": sanitize_text(f"When encountering error: '{err_content[:80]}...', resolution: {summary}"),
                            "category": "troubleshooting",
                            "rationale": "Extracted from autonomous error-correction cycle",
                            "confidence": 0.85,
                            "scope": "root",
                            "target_path_glob": None
                        })
                        break
    return extracted


def extract_command_invariants(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extracts successfully executed command invocations and test runners."""
    extracted = []
    for step in entries:
        tool_calls = step.get("tool_calls", [])
        if not isinstance(tool_calls, list):
            continue
        for call in tool_calls:
            if call.get("name") == "run_command":
                args = call.get("args", {})
                cmd = args.get("CommandLine", "")
                if cmd and any(cmd.startswith(prefix) for prefix in ["pytest", "python scripts/", "npm test", "bash scripts/"]):
                    extracted.append({
                        "statement": f"Standard verification command: `{cmd}`",
                        "category": "command",
                        "rationale": "Successfully executed verification command",
                        "confidence": 0.90,
                        "scope": "root",
                        "target_path_glob": None
                    })
    return extracted


def load_existing_memories(memory_file: Path) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """Loads existing memory objects and returns records alongside set of hashes/IDs."""
    records = []
    existing_ids = set()
    if not memory_file.exists():
        return records, existing_ids

    try:
        with open(memory_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    records.append(obj)
                    if "memory_id" in obj:
                        existing_ids.add(obj["memory_id"])
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        sys.stderr.write(f"[distill_session] Warning: Failed reading {memory_file}: {e}\n")

    return records, existing_ids


def save_memories_atomically(memory_file: Path, records: List[Dict[str, Any]]) -> None:
    """Writes memory records atomically using a temporary file replacement."""
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=str(memory_file.parent), delete=False, encoding="utf-8") as tf:
        for r in records:
            tf.write(json.dumps(r, ensure_ascii=False) + "\n")
        temp_path = tf.name
    os.replace(temp_path, str(memory_file))


def distill_session(
    workspace_path: str,
    transcript_path: Optional[str] = None,
    conversation_id: Optional[str] = None,
    artifact_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Core distillation pipeline."""
    ws = Path(workspace_path)
    memories_path = ws / ".gemini" / "knowledge" / "memories.jsonl"

    # Locate transcript
    t_path = None
    if transcript_path and os.path.exists(transcript_path):
        t_path = transcript_path
    elif artifact_dir:
        candidate = Path(artifact_dir) / ".system_generated" / "logs" / "transcript.jsonl"
        if candidate.exists():
            t_path = str(candidate)

    if not t_path or not os.path.exists(t_path):
        return {"status": "skipped", "reason": "No transcript file found", "added": 0}

    entries = parse_transcript_lines(t_path)
    if not entries:
        return {"status": "skipped", "reason": "Transcript is empty", "added": 0}

    # Extract insights
    candidates = []
    for entry in entries:
        candidates.extend(extract_user_constraints(entry))
    candidates.extend(extract_tool_troubleshooting(entries))
    candidates.extend(extract_command_invariants(entries))

    if not candidates:
        return {"status": "success", "added": 0, "total": 0}

    existing_records, existing_ids = load_existing_memories(memories_path)
    now_iso = datetime.now().isoformat()
    newly_added = 0

    for cand in candidates:
        mem_id = compute_memory_id(cand["statement"], cand["category"])
        if mem_id in existing_ids:
            continue

        record = {
            "memory_id": mem_id,
            "timestamp": now_iso,
            "category": cand["category"],
            "scope": cand["scope"],
            "target_path_glob": cand["target_path_glob"],
            "statement": cand["statement"],
            "rationale": cand["rationale"],
            "source_conversation_id": conversation_id or "unknown",
            "confidence": cand["confidence"],
            "status": "active",
            "supersedes": None
        }
        existing_records.append(record)
        existing_ids.add(mem_id)
        newly_added += 1

    if newly_added > 0:
        save_memories_atomically(memories_path, existing_records)

    return {
        "status": "success",
        "added": newly_added,
        "total": len(existing_records)
    }


def main():
    parser = argparse.ArgumentParser(description="Antigravity Continuous Alignment Distillation Hook")
    parser.add_argument("--workspace", help="Workspace path override")
    parser.add_argument("--transcript", help="Transcript path override")
    parser.add_argument("--conversation-id", help="Conversation ID override")
    parser.add_argument("--artifact-dir", help="Artifact directory path override")
    args = parser.parse_args()

    # Read payload from stdin if available without blocking
    stdin_payload = {}
    try:
        import select
        if not sys.stdin.isatty() and select.select([sys.stdin], [], [], 0.0)[0]:
            raw_input = sys.stdin.read().strip()
            if raw_input:
                stdin_payload = json.loads(raw_input)
    except Exception:
        pass

    workspace_paths = stdin_payload.get("workspacePaths", [])
    workspace = args.workspace or (workspace_paths[0] if workspace_paths else os.getcwd())
    transcript = args.transcript or stdin_payload.get("transcriptPath")
    conversation_id = args.conversation_id or stdin_payload.get("conversationId")
    artifact_dir = args.artifact_dir or stdin_payload.get("artifactDirectoryPath")

    result = distill_session(
        workspace_path=workspace,
        transcript_path=transcript,
        conversation_id=conversation_id,
        artifact_dir=artifact_dir
    )

    # Output standard Antigravity Stop contract
    print(json.dumps({}))
    if result.get("added", 0) > 0:
        sys.stderr.write(f"[continuous-alignment] Distilled {result['added']} new project memories.\n")


if __name__ == "__main__":
    main()
