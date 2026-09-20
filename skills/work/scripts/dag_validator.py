#!/usr/bin/env python3
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

"""
Lightweight Markdown DAG Validator & Mermaid Visualization Harness
Part of the Google Antigravity Work Swarm Engine (skills/work).

Parses Markdown DAG task tables and specification blocks into an in-memory graph,
validates graph integrity (cycle detection via 3-color DFS, topological sorting
via Kahn's algorithm, missing dependencies, artifact paths), computes ready frontier,
and generates/updates embedded Mermaid flowchart diagrams with CSS status styles.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from enum import Enum
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

if sys.platform == "win32":
    import io
    if hasattr(sys.stdout, "buffer") and getattr(sys.stdout, "encoding", "").lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer") and getattr(sys.stderr, "encoding", "").lower() != "utf-8":
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"

    @classmethod
    def normalize(cls, val: str) -> Optional[TaskStatus]:
        v = val.strip().upper()
        # Direct match
        for member in cls:
            if member.value == v:
                return member
        # Common aliases
        aliases = {
            "IN_PROGRESS": cls.RUNNING,
            "COMPLETED": cls.PASSED,
            "SUCCESS": cls.PASSED,
            "DONE": cls.PASSED,
            "WAITING": cls.PENDING,
            "QUEUED": cls.PENDING,
            "FAIL": cls.FAILED,
            "ERROR": cls.FAILED,
            "BLOCK": cls.BLOCKED,
        }
        return aliases.get(v)


class ExecutionMode(str, Enum):
    SERIES = "series"
    PARALLEL = "parallel"
    ASYNC_BACKGROUND = "async_background"

    @classmethod
    def normalize(cls, val: str) -> Optional[ExecutionMode]:
        v = val.strip().lower().replace("-", "_")
        for member in cls:
            if member.value == v:
                return member
        aliases = {
            "seq": cls.SERIES,
            "sequential": cls.SERIES,
            "par": cls.PARALLEL,
            "async": cls.ASYNC_BACKGROUND,
            "background": cls.ASYNC_BACKGROUND,
        }
        return aliases.get(v)


@dataclass
class TaskNode:
    id: str
    title: str
    mode: ExecutionMode
    depends_on: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    gate: str = "none"
    status: TaskStatus = TaskStatus.PENDING
    line_number: Optional[int] = None
    raw_attributes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "mode": self.mode.value,
            "depends_on": self.depends_on,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "gate": self.gate,
            "status": self.status.value,
            "line_number": self.line_number,
        }


@dataclass
class ValidationIssue:
    severity: str  # "ERROR" or "WARNING"
    code: str
    task_id: Optional[str]
    message: str
    line_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "task_id": self.task_id,
            "message": self.message,
            "line_number": self.line_number,
        }


@dataclass
class ValidationReport:
    valid: bool
    nodes: Dict[str, TaskNode]
    topological_order: List[str]
    ready_frontier: List[str]
    cycle: List[str]
    issues: List[ValidationIssue]
    errors: List[str]
    warnings: List[str]
    mermaid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "tasks": [node.to_dict() for node in self.nodes.values()],
            "topological_order": self.topological_order,
            "ready_frontier": self.ready_frontier,
            "cycle": self.cycle,
            "errors": self.errors,
            "warnings": self.warnings,
            "issues": [issue.to_dict() for issue in self.issues],
            "mermaid": self.mermaid,
        }


class MermaidSyncResult:
    """
    Result of verifying 1:1 synchronization between Mermaid diagram and task table.
    Supports boolean evaluation, tuple unpacking, index access, and attribute access.
    """
    def __init__(
        self,
        valid: bool,
        errors: List[str],
        mermaid_nodes: Set[str],
        table_nodes: Set[str],
        issues: Optional[List[ValidationIssue]] = None,
    ):
        self.valid = valid
        self.errors = errors
        self.mermaid_nodes = mermaid_nodes
        self.table_nodes = table_nodes
        self.issues = issues or []

    def __bool__(self) -> bool:
        return self.valid

    def __iter__(self):
        yield self.valid
        yield self.errors

    def __getitem__(self, index: int):
        return [self.valid, self.errors][index]

    def __len__(self) -> int:
        return 2

    def __repr__(self) -> str:
        return f"MermaidSyncResult(valid={self.valid}, errors={self.errors}, mermaid_nodes={self.mermaid_nodes}, table_nodes={self.table_nodes})"


VIRTUAL_ARTIFACT_TOKENS = {
    "", "none", "null", "nil", "-", "[]", "n/a", "stdout", "stderr", "stdin",
    "git:diff", "git:branch", "git:commit", "git:head", "git:workspace", "git:patch"
}

ILLEGAL_PATH_CHARS = set('<>"|?*')


class DAGValidator:
    """Core parser, validator, and Mermaid generator for Markdown DAGs."""

    def __init__(self, check_artifacts: bool = False, base_dir: str = ".", check_mermaid: bool = False):
        self.check_artifacts = check_artifacts
        self.base_dir = base_dir
        self.check_mermaid = check_mermaid

    @classmethod
    def _is_virtual_artifact(cls, token: str) -> bool:
        cleaned = cls._clean_token(token).lower()
        if not cleaned or cleaned in VIRTUAL_ARTIFACT_TOKENS or cleaned.startswith("git:"):
            return True
        return False

    @staticmethod
    def _clean_token(token: str) -> str:
        t = token.strip()
        if t.startswith("[") and t.endswith("]") and len(t) >= 2:
            t = t[1:-1].strip()
        if t.startswith("`") and t.endswith("`") and len(t) >= 2:
            t = t[1:-1].strip()
        return t

    @classmethod
    def _parse_list_cell(cls, cell: str) -> List[str]:
        raw = cell.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]") and len(raw) >= 2:
            raw = raw[1:-1].strip()
        cleaned_whole = cls._clean_token(raw)
        if cls._is_virtual_artifact(cleaned_whole):
            return []
        items = []
        for part in re.split(r"[,;]", raw):
            item = cls._clean_token(part)
            if item and not cls._is_virtual_artifact(item):
                items.append(item)
        return items

    @staticmethod
    def _split_table_row(row_line: str) -> List[str]:
        """Splits a markdown table row into cell strings, respecting escaped pipes (\\|)."""
        line = row_line.strip()
        if line.startswith("|"):
            line = line[1:]
        if re.search(r"(?<!\\)\|$", line):
            line = re.sub(r"(?<!\\)\|$", "", line)
        parts = re.split(r"(?<!\\)\|", line)
        return [p.strip() for p in parts]

    def parse_markdown(self, content: str) -> Tuple[Dict[str, TaskNode], List[ValidationIssue], Optional[Tuple[int, int, Dict[str, int]]]]:
        """
        Parses Markdown DAG tables or task blocks into TaskNode objects.
        Returns:
            (nodes_dict, issues_list, table_meta)
            where table_meta is (start_line, end_line, col_indices) for in-place table edits.
        """
        nodes: Dict[str, TaskNode] = {}
        issues: List[ValidationIssue] = []
        lines = content.splitlines()

        # 1. Look for GFM Table
        table_meta = None
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("|") and line.endswith("|") and lines[i].count("|") >= 3:
                # Potential table header
                raw_cols = [c.strip() for c in self._split_table_row(line)]
                norm_cols = {}
                for idx, col in enumerate(raw_cols):
                    col_clean = re.sub(r"[_\s\-]+", "", col.lower())
                    if re.match(r"^(task)?id|#$", col_clean):
                        norm_cols["id"] = idx
                    elif re.match(r"^(task)?(title|name)$", col_clean):
                        norm_cols["title"] = idx
                    elif re.match(r"^(execution)?mode|type$", col_clean):
                        norm_cols["mode"] = idx
                    elif re.match(r"^depends(on)?|dependencies|deps|prerequisites$", col_clean):
                        norm_cols["depends_on"] = idx
                    elif re.match(r"^(required)?inputs?$", col_clean):
                        norm_cols["inputs"] = idx
                    elif re.match(r"^(produced)?outputs?|artifacts?$", col_clean):
                        norm_cols["outputs"] = idx
                    elif re.match(r"^(barrier)?gates?|preconditions?$", col_clean):
                        norm_cols["gate"] = idx
                    elif re.match(r"^status|state$", col_clean):
                        norm_cols["status"] = idx

                # Must have at least 'id' and either 'depends_on' or 'mode' to be considered a DAG table
                if "id" in norm_cols and ("depends_on" in norm_cols or "mode" in norm_cols):
                    # Check next line for separator
                    if i + 1 < len(lines) and re.match(r"^\|?(\s*:?-+:?\s*\|)+\s*$", lines[i + 1].strip()):
                        table_start_line = i
                        i += 2  # skip header and separator
                        while i < len(lines):
                            row_line = lines[i].strip()
                            if not row_line or not row_line.startswith("|") or row_line.count("|") < 2:
                                break
                            cells = self._split_table_row(row_line)
                            task_id_idx = norm_cols.get("id")
                            if task_id_idx is not None and task_id_idx < len(cells):
                                raw_id = self._clean_token(cells[task_id_idx])
                                if raw_id and raw_id.lower() not in {"---", "id", "#"}:
                                    task_id = raw_id
                                    line_num = i + 1

                                    if task_id in nodes:
                                        issues.append(ValidationIssue(
                                            severity="ERROR",
                                            code="DUPLICATE_TASK_ID",
                                            task_id=task_id,
                                            message=f"Duplicate task ID '{task_id}' declared on line {line_num}",
                                            line_number=line_num
                                        ))

                                    # Title
                                    title = task_id
                                    if "title" in norm_cols and norm_cols["title"] < len(cells):
                                        t_val = self._clean_token(cells[norm_cols["title"]])
                                        if t_val:
                                            title = t_val

                                    # Mode
                                    mode = ExecutionMode.SERIES
                                    if "mode" in norm_cols and norm_cols["mode"] < len(cells):
                                        m_val = self._clean_token(cells[norm_cols["mode"]])
                                        parsed_mode = ExecutionMode.normalize(m_val)
                                        if parsed_mode:
                                            mode = parsed_mode
                                        elif m_val:
                                            issues.append(ValidationIssue(
                                                severity="ERROR",
                                                code="INVALID_MODE",
                                                task_id=task_id,
                                                message=f"Task '{task_id}' has invalid execution mode '{m_val}'",
                                                line_number=line_num
                                            ))

                                    # Depends On
                                    deps = []
                                    if "depends_on" in norm_cols and norm_cols["depends_on"] < len(cells):
                                        deps = self._parse_list_cell(cells[norm_cols["depends_on"]])

                                    # Inputs
                                    inputs = []
                                    if "inputs" in norm_cols and norm_cols["inputs"] < len(cells):
                                        inputs = self._parse_list_cell(cells[norm_cols["inputs"]])

                                    # Outputs
                                    outputs = []
                                    if "outputs" in norm_cols and norm_cols["outputs"] < len(cells):
                                        outputs = self._parse_list_cell(cells[norm_cols["outputs"]])

                                    # Gate
                                    gate = "none"
                                    if "gate" in norm_cols and norm_cols["gate"] < len(cells):
                                        g_val = self._clean_token(cells[norm_cols["gate"]])
                                        if g_val:
                                            gate = g_val

                                    # Status
                                    status = TaskStatus.PENDING
                                    if "status" in norm_cols and norm_cols["status"] < len(cells):
                                        s_val = self._clean_token(cells[norm_cols["status"]])
                                        parsed_status = TaskStatus.normalize(s_val)
                                        if parsed_status:
                                            status = parsed_status
                                        elif s_val:
                                            issues.append(ValidationIssue(
                                                severity="ERROR",
                                                code="INVALID_STATUS",
                                                task_id=task_id,
                                                message=f"Task '{task_id}' has invalid status '{s_val}'",
                                                line_number=line_num
                                            ))

                                    nodes[task_id] = TaskNode(
                                        id=task_id,
                                        title=title,
                                        mode=mode,
                                        depends_on=deps,
                                        inputs=inputs,
                                        outputs=outputs,
                                        gate=gate,
                                        status=status,
                                        line_number=line_num,
                                    )
                            i += 1
                        table_end_line = i - 1
                        table_meta = (table_start_line, table_end_line, norm_cols)
                        break
            i += 1

        # 2. If no table nodes found, look for Task Blocks (Format B)
        if not nodes:
            block_pattern = re.compile(r"^#{3,4}\s+Task:?\s*[`\"']?([a-zA-Z0-9_\-]+)[`\"']?", re.MULTILINE)
            for match in block_pattern.finditer(content):
                task_id = match.group(1)
                start_pos = match.end()
                line_num = content[:match.start()].count("\n") + 1

                if task_id in nodes:
                    issues.append(ValidationIssue(
                        severity="ERROR",
                        code="DUPLICATE_TASK_ID",
                        task_id=task_id,
                        message=f"Duplicate task ID '{task_id}' in task block on line {line_num}",
                        line_number=line_num
                    ))

                # Extract content until next header or end
                rest = content[start_pos:]
                next_header = re.search(r"^#{1,4}\s+", rest, re.MULTILINE)
                block_text = rest[:next_header.start()] if next_header else rest

                title = task_id
                mode = ExecutionMode.SERIES
                deps = []
                inputs = []
                outputs = []
                gate = "none"
                status = TaskStatus.PENDING

                for b_line in block_text.splitlines():
                    b_line = b_line.strip()
                    m_field = re.match(r"^-\s*\*\*([a-zA-Z0-9_\s]+)\*\*:\s*(.*)$", b_line)
                    if m_field:
                        key = re.sub(r"[_\s\-]+", "", m_field.group(1).lower())
                        val = m_field.group(2).strip()
                        if key in {"title", "name"}:
                            title = self._clean_token(val) or title
                        elif key in {"mode", "executionmode"}:
                            parsed_mode = ExecutionMode.normalize(self._clean_token(val))
                            if parsed_mode:
                                mode = parsed_mode
                            elif val:
                                issues.append(ValidationIssue(
                                    severity="ERROR",
                                    code="INVALID_MODE",
                                    task_id=task_id,
                                    message=f"Task '{task_id}' has invalid mode '{val}'",
                                    line_number=line_num
                                ))
                        elif key in {"dependson", "dependencies", "deps"}:
                            deps = self._parse_list_cell(val)
                        elif key in {"inputs", "requiredinputs"}:
                            inputs = self._parse_list_cell(val)
                        elif key in {"outputs", "producedoutputs", "artifacts"}:
                            outputs = self._parse_list_cell(val)
                        elif key in {"gate", "barrier", "barriergate"}:
                            gate = self._clean_token(val) or gate
                        elif key in {"status", "state"}:
                            parsed_status = TaskStatus.normalize(self._clean_token(val))
                            if parsed_status:
                                status = parsed_status
                            elif val:
                                issues.append(ValidationIssue(
                                    severity="ERROR",
                                    code="INVALID_STATUS",
                                    task_id=task_id,
                                    message=f"Task '{task_id}' has invalid status '{val}'",
                                    line_number=line_num
                                ))

                nodes[task_id] = TaskNode(
                    id=task_id,
                    title=title,
                    mode=mode,
                    depends_on=deps,
                    inputs=inputs,
                    outputs=outputs,
                    gate=gate,
                    status=status,
                    line_number=line_num,
                )

        return nodes, issues, table_meta

    def detect_cycle_3color(self, nodes: Dict[str, TaskNode]) -> Tuple[Optional[List[str]], List[ValidationIssue]]:
        """
        Detects directed cycles using 3-color DFS traversal (0=white, 1=gray, 2=black).
        Traverses dependency edges: dep -> dependent (meaning dep must precede dependent).
        Returns:
            (cycle_path_list, issues_list)
        """
        issues: List[ValidationIssue] = []
        # Build adjacency: dep -> dependent
        adj: Dict[str, List[str]] = {nid: [] for nid in nodes}
        for nid, node in nodes.items():
            for dep in node.depends_on:
                if dep in nodes:
                    if dep == nid:
                        # Self-cycle
                        path = [nid, nid]
                        cycle_str = " -> ".join(path)
                        issues.append(ValidationIssue(
                            severity="ERROR",
                            code="CYCLE_DETECTED",
                            task_id=nid,
                            message=f"Cyclic dependency detected: {cycle_str}",
                            line_number=node.line_number
                        ))
                        return path, issues
                    adj[dep].append(nid)

        # 3-color DFS
        color: Dict[str, int] = {nid: 0 for nid in nodes}  # 0=white, 1=gray, 2=black
        parent: Dict[str, Optional[str]] = {nid: None for nid in nodes}

        for start_node in sorted(nodes.keys()):
            if color[start_node] == 0:
                stack: List[Tuple[str, int]] = [(start_node, 0)]
                current_path: List[str] = [start_node]
                color[start_node] = 1

                while stack:
                    curr, neighbor_idx = stack[-1]
                    neighbors = adj[curr]

                    if neighbor_idx < len(neighbors):
                        stack[-1] = (curr, neighbor_idx + 1)
                        nxt = neighbors[neighbor_idx]

                        if color[nxt] == 1:
                            # Cycle detected! Reconstruct path from nxt to curr to nxt
                            if nxt in current_path:
                                cycle_start = current_path.index(nxt)
                                cycle_path = current_path[cycle_start:] + [nxt]
                            else:
                                cycle_path = [nxt, curr, nxt]
                            cycle_str = " -> ".join(cycle_path)
                            issues.append(ValidationIssue(
                                severity="ERROR",
                                code="CYCLE_DETECTED",
                                task_id=curr,
                                message=f"Cyclic dependency detected: {cycle_str}",
                                line_number=nodes[curr].line_number
                            ))
                            return cycle_path, issues

                        if color[nxt] == 0:
                            color[nxt] = 1
                            parent[nxt] = curr
                            current_path.append(nxt)
                            stack.append((nxt, 0))
                    else:
                        color[curr] = 2
                        stack.pop()
                        if current_path and current_path[-1] == curr:
                            current_path.pop()

        return None, issues

    def topological_sort_kahn(self, nodes: Dict[str, TaskNode]) -> Tuple[List[str], List[ValidationIssue]]:
        """
        Topological sorting via Kahn's algorithm.
        Returns:
            (topological_order, issues_list)
        """
        issues: List[ValidationIssue] = []
        in_degree: Dict[str, int] = {nid: 0 for nid in nodes}
        adj: Dict[str, List[str]] = {nid: [] for nid in nodes}

        for nid, node in nodes.items():
            for dep in node.depends_on:
                if dep in nodes:
                    adj[dep].append(nid)
                    in_degree[nid] += 1

        # Queue nodes with in_degree 0
        queue = [nid for nid in sorted(nodes.keys()) if in_degree[nid] == 0]
        order: List[str] = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for succ in adj[curr]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        if len(order) < len(nodes):
            unresolved = [nid for nid in sorted(nodes.keys()) if nid not in order]
            issues.append(ValidationIssue(
                severity="ERROR",
                code="TOPOLOGICAL_SORT_FAILED",
                task_id=unresolved[0] if unresolved else None,
                message=f"Topological sort failed: {len(unresolved)} tasks have unresolved dependencies: {', '.join(unresolved)}"
            ))

        return order, issues

    def validate_dependencies(self, nodes: Dict[str, TaskNode]) -> List[ValidationIssue]:
        """Validates that all depends_on references point to declared tasks."""
        issues: List[ValidationIssue] = []
        for nid, node in sorted(nodes.items()):
            for dep in node.depends_on:
                if dep not in nodes:
                    issues.append(ValidationIssue(
                        severity="ERROR",
                        code="MISSING_DEPENDENCY",
                        task_id=nid,
                        message=f"Task '{nid}' depends on undefined task '{dep}'",
                        line_number=node.line_number
                    ))
        return issues

    def validate_artifact_paths(self, nodes: Dict[str, TaskNode]) -> List[ValidationIssue]:
        """
        Validates syntax of artifact paths and checks for disallowed absolute roots.
        When check_artifacts is True, asserts physical file presence on disk.
        """
        issues: List[ValidationIssue] = []

        for nid, node in sorted(nodes.items()):
            all_paths = [("input", p) for p in node.inputs] + [("output", p) for p in node.outputs]

            for p_type, path_str in all_paths:
                if self._is_virtual_artifact(path_str):
                    continue

                # Check for illegal characters
                if any(ch in path_str for ch in ILLEGAL_PATH_CHARS):
                    issues.append(ValidationIssue(
                        severity="ERROR",
                        code="ILLEGAL_PATH_CHARS",
                        task_id=nid,
                        message=f"Task '{nid}' declared {p_type} path '{path_str}' containing illegal characters",
                        line_number=node.line_number
                    ))
                    continue

                # Check for disallowed absolute roots
                is_abs = False
                if path_str.startswith("/") or path_str.startswith("\\") or path_str.startswith("~"):
                    is_abs = True
                elif re.match(r"^[a-zA-Z]:", path_str):
                    is_abs = True

                if is_abs:
                    issues.append(ValidationIssue(
                        severity="ERROR",
                        code="ABSOLUTE_PATH_DISALLOWED",
                        task_id=nid,
                        message=f"Task '{nid}' declared absolute {p_type} path '{path_str}'. Paths must be relative to repository root.",
                        line_number=node.line_number
                    ))
                    continue

                # Check for directory traversal escaping workspace
                clean_norm = Path(path_str).as_posix()
                is_traversal = ".." in clean_norm.split("/")
                if not is_traversal and self.base_dir:
                    try:
                        clean_rel = path_str.replace("/", os.sep).replace("\\", os.sep)
                        target_abs = os.path.abspath(os.path.join(self.base_dir, clean_rel))
                        base_abs = os.path.abspath(self.base_dir)
                        if os.path.commonpath([base_abs, target_abs]) != base_abs:
                            is_traversal = True
                    except Exception:
                        is_traversal = True

                if is_traversal:
                    issues.append(ValidationIssue(
                        severity="ERROR",
                        code="DIRECTORY_TRAVERSAL_DISALLOWED",
                        task_id=nid,
                        message=f"Task '{nid}' declared {p_type} path '{path_str}' attempting directory traversal outside workspace.",
                        line_number=node.line_number
                    ))
                    continue

                # Physical check if requested
                if self.check_artifacts:
                    clean_rel = path_str.replace("/", os.sep).replace("\\", os.sep)
                    full_path = os.path.join(self.base_dir, clean_rel)

                    if p_type == "input" and node.status in (TaskStatus.RUNNING, TaskStatus.PASSED):
                        if not os.path.exists(full_path):
                            issues.append(ValidationIssue(
                                severity="ERROR",
                                code="MISSING_INPUT_ARTIFACT",
                                task_id=nid,
                                message=f"Task '{nid}' ({node.status.value}) requires missing input artifact: '{path_str}'",
                                line_number=node.line_number
                            ))

                    if p_type == "output" and node.status == TaskStatus.PASSED:
                        if not os.path.exists(full_path):
                            issues.append(ValidationIssue(
                                severity="ERROR",
                                code="MISSING_OUTPUT_ARTIFACT",
                                task_id=nid,
                                message=f"Task '{nid}' (PASSED) missing produced output artifact: '{path_str}'",
                                line_number=node.line_number
                            ))

        return issues

    def validate_state_consistency(self, nodes: Dict[str, TaskNode]) -> List[ValidationIssue]:
        """Checks for invalid state combinations (e.g. task PASSED or RUNNING while prerequisite FAILED, BLOCKED, or PENDING)."""
        issues: List[ValidationIssue] = []
        for nid, node in sorted(nodes.items()):
            for dep_id in node.depends_on:
                if dep_id in nodes:
                    dep_node = nodes[dep_id]
                    if node.status == TaskStatus.PASSED and dep_node.status in (
                        TaskStatus.FAILED,
                        TaskStatus.BLOCKED,
                        TaskStatus.PENDING,
                        TaskStatus.RUNNING,
                    ):
                        issues.append(ValidationIssue(
                            severity="ERROR",
                            code="STATE_INCONSISTENCY",
                            task_id=nid,
                            message=f"Task '{nid}' is PASSED but upstream dependency '{dep_id}' is {dep_node.status.value}",
                            line_number=node.line_number
                        ))
                    elif node.status == TaskStatus.RUNNING and dep_node.status in (
                        TaskStatus.FAILED,
                        TaskStatus.BLOCKED,
                        TaskStatus.PENDING,
                        TaskStatus.RUNNING,
                    ):
                        issues.append(ValidationIssue(
                            severity="ERROR",
                            code="STATE_INCONSISTENCY",
                            task_id=nid,
                            message=f"Task '{nid}' is RUNNING but upstream dependency '{dep_id}' is {dep_node.status.value}",
                            line_number=node.line_number
                        ))
        return issues

    def compute_ready_frontier(self, nodes: Dict[str, TaskNode]) -> List[str]:
        """
        Resolves the Ready Frontier: all PENDING tasks whose dependencies
        are fully PASSED and whose physical inputs exist (if check_artifacts is True).
        """
        frontier = []
        for nid in sorted(nodes.keys()):
            node = nodes[nid]
            if node.status != TaskStatus.PENDING:
                continue

            # Check if all dependencies are satisfied
            deps_satisfied = True
            for dep in node.depends_on:
                if dep not in nodes or nodes[dep].status != TaskStatus.PASSED:
                    deps_satisfied = False
                    break

            if not deps_satisfied:
                continue

            # Check physical input artifacts if check_artifacts is enabled
            if self.check_artifacts:
                inputs_exist = True
                for inp in node.inputs:
                    if self._is_virtual_artifact(inp):
                        continue
                    clean_rel = inp.replace("/", os.sep).replace("\\", os.sep)
                    full_path = os.path.join(self.base_dir, clean_rel)
                    if not os.path.exists(full_path):
                        inputs_exist = False
                        break
                if not inputs_exist:
                    continue

            frontier.append(nid)

        return frontier

    def generate_mermaid(self, nodes: Dict[str, TaskNode]) -> str:
        """
        Generates Mermaid flowchart TD diagram with CSS status classes.
        Classes: status-passed, status-running, status-pending, status-blocked, status-failed.
        """
        lines = ["```mermaid", "graph TD"]

        # 1. Node definitions
        lines.append("    %% Task Nodes")
        for nid in sorted(nodes.keys()):
            node = nodes[nid]
            status_cls = f"status-{node.status.value.lower()}"
            title_escaped = node.title.replace('"', "'")
            lines.append(f'    {node.id}["{node.id}<br/>[{node.mode.value}] <b>{node.status.value}</b>"]:::{status_cls}')

        # 2. Dependency Edges (dep --> dependent)
        has_edges = False
        edge_lines = []
        for nid in sorted(nodes.keys()):
            node = nodes[nid]
            for dep in sorted(node.depends_on):
                if dep in nodes:
                    edge_lines.append(f"    {dep} --> {nid}")
                    has_edges = True

        if has_edges:
            lines.append("\n    %% Dependency Edges")
            lines.extend(edge_lines)

        # 3. Class Definitions
        lines.append("\n    %% Node Status Styling")
        lines.append("    classDef status-pending fill:#2d3748,stroke:#4a5568,color:#cbd5e0;")
        lines.append("    classDef status-running fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#93c5fd;")
        lines.append("    classDef status-passed fill:#14532d,stroke:#22c55e,color:#86efac;")
        lines.append("    classDef status-blocked fill:#78350f,stroke:#f59e0b,color:#fde68a;")
        lines.append("    classDef status-failed fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fca5a5;")
        # Short alias definitions for backwards compatibility
        lines.append("    classDef pending fill:#2d3748,stroke:#4a5568,color:#cbd5e0;")
        lines.append("    classDef running fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#93c5fd;")
        lines.append("    classDef passed fill:#14532d,stroke:#22c55e,color:#86efac;")
        lines.append("    classDef blocked fill:#78350f,stroke:#f59e0b,color:#fde68a;")
        lines.append("    classDef failed fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fca5a5;")

        lines.append("```")
        return "\n".join(lines)

    def validate(self, content: str) -> ValidationReport:
        """Runs the full validation suite on Markdown content."""
        nodes, issues, _ = self.parse_markdown(content)

        if not nodes:
            issues.append(ValidationIssue(
                severity="ERROR",
                code="NO_TASKS_FOUND",
                task_id=None,
                message="No valid DAG tasks or tables found in markdown content"
            ))

        # Check missing dependencies
        dep_issues = self.validate_dependencies(nodes)
        issues.extend(dep_issues)

        # Check artifact paths
        path_issues = self.validate_artifact_paths(nodes)
        issues.extend(path_issues)

        # Check state consistency
        state_issues = self.validate_state_consistency(nodes)
        issues.extend(state_issues)

        # Check Mermaid synchronization if requested
        if self.check_mermaid:
            sync_res = validate_mermaid_sync(content)
            issues.extend(sync_res.issues)

        # Cycle detection
        cycle_path, cycle_issues = self.detect_cycle_3color(nodes)
        issues.extend(cycle_issues)

        # Topological sort
        topological_order = []
        if not cycle_path:
            topological_order, sort_issues = self.topological_sort_kahn(nodes)
            issues.extend(sort_issues)

        # Ready frontier
        ready_frontier = self.compute_ready_frontier(nodes)

        # Mermaid representation
        mermaid = self.generate_mermaid(nodes)

        errors = [iss.message for iss in issues if iss.severity == "ERROR"]
        warnings = [iss.message for iss in issues if iss.severity == "WARNING"]
        is_valid = len(errors) == 0

        return ValidationReport(
            valid=is_valid,
            nodes=nodes,
            topological_order=topological_order,
            ready_frontier=ready_frontier,
            cycle=cycle_path or [],
            issues=issues,
            errors=errors,
            warnings=warnings,
            mermaid=mermaid,
        )

    def update_markdown_content(self, content: str, status_updates: Optional[Dict[str, str]] = None) -> str:
        """
        Updates task statuses and Mermaid block in-place within the Markdown text.
        """
        status_updates = status_updates or {}
        lines = content.splitlines()

        nodes, _, table_meta = self.parse_markdown(content)

        # Apply status updates to nodes
        for tid, new_st in status_updates.items():
            if tid in nodes:
                norm_st = TaskStatus.normalize(new_st)
                if norm_st:
                    nodes[tid].status = norm_st

        # If table was found, update status cells in the table lines
        if table_meta:
            start_l, end_l, col_map = table_meta
            st_col = col_map.get("status")
            id_col = col_map.get("id")

            if st_col is not None and id_col is not None:
                for idx in range(start_l + 2, end_l + 1):
                    row = lines[idx]
                    if row.strip().startswith("|"):
                        raw_cells = self._split_table_row(row)
                        if id_col < len(raw_cells) and st_col < len(raw_cells):
                            tid = self._clean_token(raw_cells[id_col])
                            if tid in status_updates:
                                norm_st = TaskStatus.normalize(status_updates[tid])
                                if norm_st:
                                    raw_cells[st_col] = f"{norm_st.value}"
                                    lines[idx] = "| " + " | ".join(c.strip() for c in raw_cells) + " |"

        updated_text = "\n".join(lines)

        # Generate updated Mermaid block
        new_mermaid = self.generate_mermaid(nodes)

        # Replace existing Mermaid block or insert after table / at end
        mermaid_block_regex = re.compile(r"```mermaid[\s\S]*?```", re.MULTILINE)
        if mermaid_block_regex.search(updated_text):
            updated_text = mermaid_block_regex.sub(new_mermaid, updated_text, count=1)
        else:
            # If table was present, insert right after table
            if table_meta:
                table_end = table_meta[1]
                t_lines = updated_text.splitlines()
                t_lines.insert(table_end + 1, "\n" + new_mermaid + "\n")
                updated_text = "\n".join(t_lines)
            else:
                updated_text = updated_text.rstrip() + "\n\n" + new_mermaid + "\n"

        return updated_text


def extract_mermaid_node_ids(mermaid_code: str) -> Set[str]:
    """
    Extracts all declared task node IDs from a Mermaid graph/flowchart diagram string.
    Correctly ignores comments (%%), graph/flowchart directives, subgraphs, end blocks,
    class definitions, style directives, and edge labels.
    """
    node_ids: Set[str] = set()

    # Strip code fences if present
    code = mermaid_code.strip()
    if code.startswith("```mermaid"):
        code = code[len("```mermaid"):].strip()
    if code.startswith("```"):
        code = code[len("```"):].strip()
    if code.endswith("```"):
        code = code[:-3].strip()

    lines = code.splitlines()

    # Edge regex patterns for Mermaid
    edge_pattern = re.compile(r'-->\|[^|]*\||--\s*[^-\n]+\s*-->|-->|---|-.->|-.-|==>|==|->')

    keywords_to_ignore = {
        "graph", "flowchart", "subgraph", "end", "classdef", "class",
        "style", "click", "linkstyle", "direction", "sequencediagram",
        "autonumber", "participant", "actor"
    }

    for raw_line in lines:
        # Strip inline comments (%% ...)
        line = re.sub(r'%%.*$', '', raw_line).strip()
        if not line:
            continue

        first_token = line.split()[0].lower() if line.split() else ""
        if first_token in keywords_to_ignore:
            continue

        if edge_pattern.search(line):
            segments = edge_pattern.split(line)
            for seg in segments:
                seg = seg.strip()
                if not seg:
                    continue
                sub_segs = [s.strip() for s in seg.split("&")]
                for s in sub_segs:
                    m = re.match(r'^([a-zA-Z0-9_\-]+)', s)
                    if m:
                        cand = m.group(1)
                        if cand.lower() not in keywords_to_ignore:
                            node_ids.add(cand)
        else:
            m = re.match(r'^([a-zA-Z0-9_\-]+)', line)
            if m:
                cand = m.group(1)
                if cand.lower() not in keywords_to_ignore:
                    node_ids.add(cand)

    return node_ids


def validate_mermaid_sync(content: str) -> MermaidSyncResult:
    """
    Verifies 1:1 synchronization between the Mermaid execution topology
    and the declarative GFM task table within the given Markdown content.
    Extracts all node IDs from both representations and detects drift.
    """
    validator = DAGValidator()
    nodes, parse_issues, _ = validator.parse_markdown(content)
    table_ids = set(nodes.keys())

    if not table_ids:
        return MermaidSyncResult(
            valid=False,
            errors=["No valid DAG tasks found in markdown content to synchronize with Mermaid"],
            mermaid_nodes=set(),
            table_nodes=set(),
            issues=[ValidationIssue(
                severity="ERROR",
                code="NO_TASKS_FOUND",
                task_id=None,
                message="No valid DAG tasks found in markdown content to synchronize with Mermaid"
            )]
        )

    # Extract all ```mermaid blocks
    mermaid_blocks = re.findall(r'```mermaid\s*([\s\S]*?)\s*```', content)
    if not mermaid_blocks:
        return MermaidSyncResult(
            valid=False,
            errors=["No Mermaid diagram block found in markdown content"],
            mermaid_nodes=set(),
            table_nodes=table_ids,
            issues=[ValidationIssue(
                severity="ERROR",
                code="MISSING_MERMAID_DIAGRAM",
                task_id=None,
                message="No Mermaid diagram block found in markdown content"
            )]
        )

    # Filter for flowchart / graph blocks (ignoring sequenceDiagram, etc.)
    candidate_node_sets: List[Tuple[int, Set[str]]] = []
    for block in mermaid_blocks:
        lines = [l.strip().lower() for l in block.strip().splitlines() if l.strip()]
        first_line = lines[0] if lines else ""
        if first_line.startswith(("graph", "flowchart")):
            n_ids = extract_mermaid_node_ids(block)
            overlap = len(n_ids.intersection(table_ids))
            candidate_node_sets.append((overlap, n_ids))

    if not candidate_node_sets:
        # Fallback to any mermaid block
        for block in mermaid_blocks:
            n_ids = extract_mermaid_node_ids(block)
            overlap = len(n_ids.intersection(table_ids))
            candidate_node_sets.append((overlap, n_ids))

    # Pick the block with highest overlap with table_ids
    candidate_node_sets.sort(key=lambda x: x[0], reverse=True)
    best_mermaid_nodes = candidate_node_sets[0][1] if candidate_node_sets else set()

    missing_in_mermaid = table_ids - best_mermaid_nodes
    extra_in_mermaid = best_mermaid_nodes - table_ids

    errors: List[str] = []
    issues: List[ValidationIssue] = []

    if missing_in_mermaid:
        missing_sorted = sorted(missing_in_mermaid)
        msg = f"Task table contains task(s) missing from Mermaid diagram: {', '.join(missing_sorted)}"
        errors.append(msg)
        for tid in missing_sorted:
            issues.append(ValidationIssue(
                severity="ERROR",
                code="MERMAID_MISSING_TASK",
                task_id=tid,
                message=f"Task '{tid}' is declared in task table but missing from Mermaid diagram"
            ))

    if extra_in_mermaid:
        extra_sorted = sorted(extra_in_mermaid)
        msg = f"Mermaid diagram contains node(s) not declared in task table: {', '.join(extra_sorted)}"
        errors.append(msg)
        for nid in extra_sorted:
            issues.append(ValidationIssue(
                severity="ERROR",
                code="MERMAID_EXTRA_NODE",
                task_id=nid,
                message=f"Node '{nid}' exists in Mermaid diagram but is not declared in task table"
            ))

    is_valid = len(errors) == 0
    return MermaidSyncResult(
        valid=is_valid,
        errors=errors,
        mermaid_nodes=best_mermaid_nodes,
        table_nodes=table_ids,
        issues=issues
    )


def print_human_report(report: ValidationReport, quiet: bool = False) -> None:
    if quiet:
        return
    status_sym = "✅ VALID" if report.valid else "❌ INVALID"
    print("=" * 65)
    print(f"📊 DAG Validation Report — {status_sym}")
    print("=" * 65)
    print(f"Total Tasks: {len(report.nodes)}")

    if report.topological_order:
        print(f"Topological Execution Order: {' -> '.join(report.topological_order)}")

    print(f"Ready Frontier (Ready to Dispatch): {', '.join(report.ready_frontier) if report.ready_frontier else 'None (Dormant/Waiting)'}")

    if report.cycle:
        print(f"\n🚨 Cycle Detected: {' -> '.join(report.cycle)}")

    if report.errors:
        print(f"\n❌ Validation Errors ({len(report.errors)}):")
        for err in report.errors:
            print(f"   • {err}")

    if report.warnings:
        print(f"\n⚠️  Validation Warnings ({len(report.warnings)}):")
        for warn in report.warnings:
            print(f"   • {warn}")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lightweight Markdown DAG Validator & Mermaid Harness (skills/work)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", nargs="?", default=None, help="Path to Markdown DAG file (e.g., DAG.md, PROJECT.md)")
    parser.add_argument("--stdin", action="store_true", help="Read Markdown content from stdin")
    parser.add_argument("--check-artifacts", action="store_true", help="Verify physical on-disk file existence for artifacts")
    parser.add_argument("--check-mermaid", action="store_true", help="Verify 1:1 synchronization between Mermaid diagram and task table")
    parser.add_argument("--base-dir", default=".", help="Base directory for relative artifact paths (default: .)")
    parser.add_argument("--mermaid", action="store_true", help="Print generated Mermaid diagram to stdout")
    parser.add_argument("--update-file", action="store_true", help="Update the Markdown file in-place with new statuses and Mermaid diagram")
    parser.add_argument("--set-status", action="append", default=[], metavar="TASK=STATUS", help="Set task status (e.g., --set-status worker_alpha=PASSED)")
    parser.add_argument("--ready-frontier", action="store_true", help="Print only ready frontier task IDs (space-separated)")
    parser.add_argument("--json", action="store_true", help="Output validation report as structured JSON")
    parser.add_argument("--format", choices=["text", "json", "mermaid"], default="text", help="Output format (default: text)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress human report; rely on exit code")

    args = parser.parse_args()

    # Read content
    content = ""
    file_path = args.file

    if args.stdin:
        content = sys.stdin.read()
    elif file_path:
        if not os.path.exists(file_path):
            if not args.quiet:
                print(f"Error: Specified file not found: {file_path}", file=sys.stderr)
            sys.exit(2)
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except Exception as ex:
            if not args.quiet:
                print(f"Error reading {file_path}: {ex}", file=sys.stderr)
            sys.exit(2)
    else:
        parser.print_help(sys.stderr)
        sys.exit(2)

    # Parse status updates if any
    status_updates = {}
    for item in args.set_status:
        if "=" in item:
            tid, st = item.split("=", 1)
            status_updates[tid.strip()] = st.strip()
        else:
            if not args.quiet:
                print(f"Error: Invalid --set-status format '{item}'. Expected TASK=STATUS", file=sys.stderr)
            sys.exit(2)

    validator = DAGValidator(
        check_artifacts=args.check_artifacts,
        base_dir=args.base_dir,
        check_mermaid=args.check_mermaid
    )

    # In-place file update
    if args.update_file:
        if not file_path:
            if not args.quiet:
                print("Error: --update-file requires a target file path (cannot update stdin in-place)", file=sys.stderr)
            sys.exit(2)
        try:
            updated_content = validator.update_markdown_content(content, status_updates)
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(updated_content)
            content = updated_content
        except Exception as ex:
            if not args.quiet:
                print(f"Error updating {file_path}: {ex}", file=sys.stderr)
            sys.exit(2)
    elif status_updates:
        # Apply in-memory status updates prior to validation if --update-file is not specified
        content = validator.update_markdown_content(content, status_updates)

    # Run validation
    report = validator.validate(content)

    # Format output
    if args.json or args.format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    elif args.mermaid or args.format == "mermaid":
        print(report.mermaid)
    elif args.ready_frontier:
        print(" ".join(report.ready_frontier))
    else:
        print_human_report(report, quiet=args.quiet)

    # Exit code: 0 if valid, 1 if invalid
    sys.exit(0 if report.valid else 1)


if __name__ == "__main__":
    main()
