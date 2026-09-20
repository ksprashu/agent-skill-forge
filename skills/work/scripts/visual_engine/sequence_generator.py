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
Lifecycle Sequence & Dataflow Diagram Generator.
Adheres to DESIGN.md § 1.3, § 2.2, and § 3.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Union

from .c4_generator import sanitize_c4_label, sanitize_node_id


def sanitize_sequence_message(text: str) -> str:
    """
    Sanitizes message labels for Mermaid sequence diagrams.
    Strips dangerous HTML/script tags, normalizes newlines, and escapes quotes.
    """
    if not text:
        return ""
    # Strip script/style
    clean = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', clean, flags=re.IGNORECASE)
    # Escape quotes
    clean = clean.replace('"', '#quot;')
    # Replace newlines with <br/>
    clean = re.sub(r'\r\n|\r|\n', '<br/>', clean)
    return clean.strip()


def render_sequence_diagram(
    participants: List[Union[Dict[str, Any], str]],
    steps: List[Dict[str, Any]],
    autonumber: bool = True,
    fenced: bool = True,
) -> str:
    """
    Renders a lifecycle sequence diagram with automated numbering and par/alt/loop blocks.

    Args:
        participants: List of dicts with 'id' and 'label' (or plain strings).
        steps: List of dicts with 'source', 'target', 'message', and optional 'block'.
        autonumber: Whether to include 'autonumber' directive.
        fenced: Whether to wrap output in ```mermaid ... ``` code fences.

    Returns:
        Formatted Mermaid sequence diagram markdown string.
    """
    lines: List[str] = ["sequenceDiagram"]
    if autonumber:
        lines.append("  autonumber")

    # 1. Render participants
    for p in participants:
        if isinstance(p, str):
            p_id = sanitize_node_id(p)
            lines.append(f"  participant {p_id}")
        elif isinstance(p, dict):
            raw_id = p.get("id", p.get("name", ""))
            p_id = sanitize_node_id(raw_id)
            label = p.get("label", p.get("name", p_id))
            sanitized_label = sanitize_c4_label(label)
            is_actor = p.get("actor", False)
            keyword = "actor" if is_actor else "participant"
            if sanitized_label and sanitized_label != p_id:
                lines.append(f"  {keyword} {p_id} as {sanitized_label}")
            else:
                lines.append(f"  {keyword} {p_id}")

    lines.append("")

    # 2. Render steps with dynamic indentation
    indent_level = 1
    block_keywords = {"par", "alt", "opt", "loop", "critical", "rect"}

    for step in steps:
        prefix = "  " * indent_level

        # Handle raw block strings, e.g. {"block": "par Parallel Processing"}
        block_text = step.get("block", "")
        block_type = step.get("type", "")

        if block_text:
            first_word = block_text.strip().split()[0] if block_text.strip() else ""
            rest = block_text.strip()[len(first_word):].strip()
            clean_rest = sanitize_c4_label(rest)
            clean_line = f"{first_word} {clean_rest}".strip() if clean_rest else first_word
            if first_word == "end":
                indent_level = max(1, indent_level - 1)
                prefix = "  " * indent_level
                lines.append(f"{prefix}end")
            elif first_word == "else":
                else_prefix = "  " * max(1, indent_level - 1)
                lines.append(f"{else_prefix}{clean_line}")
            elif first_word in block_keywords:
                lines.append(f"{prefix}{clean_line}")
                indent_level += 1
            else:
                lines.append(f"{prefix}{clean_line}")
            continue

        if block_type:
            label = step.get("label", "")
            sanitized_block_label = sanitize_c4_label(label)
            if block_type == "end":
                indent_level = max(1, indent_level - 1)
                prefix = "  " * indent_level
                lines.append(f"{prefix}end")
                continue
            elif block_type == "else":
                else_prefix = "  " * max(1, indent_level - 1)
                msg = f" {sanitized_block_label}" if sanitized_block_label else ""
                lines.append(f"{else_prefix}else{msg}")
                continue
            elif block_type in block_keywords:
                msg = f" {sanitized_block_label}" if sanitized_block_label else ""
                lines.append(f"{prefix}{block_type}{msg}")
                indent_level += 1
                continue

        # Handle notes
        note = step.get("note")
        if note:
            pos = step.get("position", "over")
            target = step.get("target", step.get("source", ""))
            safe_target = sanitize_node_id(target) if isinstance(target, str) else ", ".join(sanitize_node_id(t) for t in target)
            sanitized_note = sanitize_sequence_message(note)
            lines.append(f"{prefix}Note {pos} {safe_target}: {sanitized_note}")
            continue

        # Handle message interactions
        raw_source = step.get("source")
        raw_target = step.get("target")
        if not raw_source or not raw_target:
            continue

        source = sanitize_node_id(raw_source)
        target = sanitize_node_id(raw_target)
        message = sanitize_sequence_message(step.get("message", ""))

        arrow = step.get("arrow")
        if not arrow:
            if step.get("return", False) or step.get("dashed", False):
                arrow = "-->>"
            else:
                arrow = "->>"

        lines.append(f"{prefix}{source}{arrow}{target}: {message}")

        if step.get("activate", False):
            lines.append(f"{prefix}activate {target}")
        if step.get("deactivate", False):
            lines.append(f"{prefix}deactivate {source}")

    body = "\n".join(lines)
    if fenced:
        return f"```mermaid\n{body}\n```"
    return body
