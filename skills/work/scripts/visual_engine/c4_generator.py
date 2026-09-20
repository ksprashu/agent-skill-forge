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
C4 Level 2/3 Component Diagram Generator with Strict Label Sanitization.
Adheres to DESIGN.md § 2.2, § 3, and spike_results.md § 3.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Union


def sanitize_c4_label(text: str) -> str:
    """
    Sanitizes arbitrary text for safe inclusion within Mermaid quoted node labels.

    Rules applied (spike_results.md § 3.2):
    1. Strip <script> and <style> tags and their contents.
    2. Escape arrow tokens (--> to --&gt;, ==> to ==&gt;).
    3. Escape pipe character (| to &#124;).
    4. Escape internal double quotes (" to #quot;).
    5. Normalize newlines (\\r\\n, \\r, \\n to <br/>).
    """
    if not text:
        return ""

    # 1. Strip script and style tags
    sanitized = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
    sanitized = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', sanitized, flags=re.IGNORECASE)

    # 2. Escape arrow tokens to prevent confusing Mermaid edge parser
    sanitized = sanitized.replace("-->", "--&gt;").replace("==>", "==&gt;")

    # 3. Escape pipe character
    sanitized = sanitized.replace("|", "&#124;")

    # 4. Escape internal double quotes using official Mermaid HTML entity
    sanitized = sanitized.replace('"', "#quot;")

    # 5. Normalize newlines to <br/>
    sanitized = re.sub(r'\r\n|\r|\n', '<br/>', sanitized)

    return sanitized.strip()


def sanitize_node_id(node_id: str) -> str:
    """
    Sanitizes a node ID to ensure valid Mermaid identifier syntax.
    """
    if not node_id:
        return "node"
    clean = re.sub(r'[^a-zA-Z0-9_]', '_', str(node_id))
    if clean and clean[0].isdigit():
        clean = f"n_{clean}"
    return clean or "node"


def render_c4_component_diagram(
    spec: Dict[str, Any],
    fenced: bool = True,
) -> str:
    """
    Renders a standard-compliant Mermaid C4 Level 2/3 component diagram.
    Ensures all node labels are properly quoted and sanitized.

    Args:
        spec: Dictionary conforming to C4DiagramSpec schema.
            - title: Optional title string.
            - direction: "TD" | "LR" (default "TD").
            - diagram_type: "graph" | "flowchart" (default "graph").
            - boundaries: List of boundaries with 'id' and 'label', optional 'parent'.
            - components: List of components with 'id', 'name', 'technology',
                          'description', optional 'boundary', 'dependencies'.
            - edges / relationships: Optional list of explicit edge definitions.
        fenced: Whether to wrap output in ```mermaid ... ``` code fences.

    Returns:
        Formatted Mermaid diagram string ready for embedding in markdown.
    """
    direction = spec.get("direction", "TD")
    diagram_type = spec.get("diagram_type", "graph")
    lines: List[str] = [f"{diagram_type} {direction}"]

    raw_boundaries = spec.get("boundaries", [])
    raw_components = spec.get("components", [])
    raw_edges = spec.get("edges", spec.get("relationships", []))

    # Index boundaries
    boundaries_map: Dict[str, Dict[str, Any]] = {}
    boundary_children: Dict[str, List[str]] = {}  # boundary_id -> list of child boundary_ids
    top_level_boundaries: List[str] = []

    for b in raw_boundaries:
        b_id = str(b.get("id", ""))
        if not b_id:
            continue
        parent_id = b.get("parent")
        boundaries_map[b_id] = b
        if parent_id:
            boundary_children.setdefault(parent_id, []).append(b_id)
        else:
            top_level_boundaries.append(b_id)

    # Ensure any boundary whose parent does not exist is rendered as top-level
    for parent_id, children in list(boundary_children.items()):
        if parent_id not in boundaries_map:
            for child_id in children:
                if child_id not in top_level_boundaries:
                    top_level_boundaries.append(child_id)

    # Group components by boundary
    components_by_boundary: Dict[str, List[Dict[str, Any]]] = {}
    unbounded_components: List[Dict[str, Any]] = []

    for comp in raw_components:
        b_id = comp.get("boundary")
        if b_id:
            components_by_boundary.setdefault(str(b_id), []).append(comp)
            # Auto-register boundary if missing from boundaries list
            if str(b_id) not in boundaries_map:
                boundaries_map[str(b_id)] = {"id": str(b_id), "label": str(b_id)}
                top_level_boundaries.append(str(b_id))
        else:
            unbounded_components.append(comp)

    # Ensure any boundary in boundaries_map that is not reachable from top_level_boundaries
    # (e.g. due to circular parent references) is promoted to top_level_boundaries so it and its
    # components are guaranteed to be rendered.
    reachable_boundaries: Set[str] = set()
    def _mark_reachable(bid: str) -> None:
        if bid in reachable_boundaries:
            return
        reachable_boundaries.add(bid)
        for child in boundary_children.get(bid, []):
            _mark_reachable(child)

    for bid in list(top_level_boundaries):
        _mark_reachable(bid)

    for bid in list(boundaries_map.keys()):
        if bid not in reachable_boundaries:
            top_level_boundaries.append(bid)
            _mark_reachable(bid)

    def render_component_node(comp: Dict[str, Any], indent_level: int = 2) -> str:
        safe_id = sanitize_node_id(comp.get("id", ""))
        name = sanitize_c4_label(comp.get("name", safe_id))
        tech = sanitize_c4_label(comp.get("technology", ""))
        desc = sanitize_c4_label(comp.get("description", ""))

        parts = [f"<b>{name}</b>" if name else ""]
        if tech:
            parts.append(f"[{tech}]")
        if desc:
            parts.append(desc)

        inner_label = "<br/>".join([p for p in parts if p])
        prefix = "  " * indent_level
        return f'{prefix}{safe_id}["{inner_label}"]'

    def render_boundary(b_id: str, indent_level: int = 1, visited: Optional[Set[str]] = None) -> List[str]:
        if visited is None:
            visited = set()
        if b_id in visited:
            return []
        visited.add(b_id)

        b = boundaries_map.get(b_id, {"id": b_id, "label": b_id})
        safe_b_id = sanitize_node_id(b_id)
        label = sanitize_c4_label(b.get("label", b_id))
        prefix = "  " * indent_level

        out: List[str] = [f'{prefix}subgraph {safe_b_id} ["{label}"]']

        # Render nested boundaries
        for child_b_id in boundary_children.get(b_id, []):
            out.extend(render_boundary(child_b_id, indent_level + 1, visited))

        # Render components in this boundary
        for comp in components_by_boundary.get(b_id, []):
            out.append(render_component_node(comp, indent_level + 1))

        out.append(f"{prefix}end")
        return out

    # 1. Render all top-level boundaries
    for b_id in top_level_boundaries:
        lines.extend(render_boundary(b_id, 1))

    # 2. Render unbounded components
    for comp in unbounded_components:
        lines.append(render_component_node(comp, 1))

    # 3. Collect and render edges
    rendered_edges: Set[str] = set()

    # From components dependencies
    for comp in raw_components:
        source_id = sanitize_node_id(comp.get("id", ""))
        deps = comp.get("dependencies", [])
        for dep in deps:
            if isinstance(dep, dict):
                target_id = sanitize_node_id(dep.get("target", ""))
                label = sanitize_c4_label(dep.get("label", ""))
                arrow = dep.get("arrow", "-->")
                edge_str = f"  {source_id} {arrow}|{label}| {target_id}" if label else f"  {source_id} {arrow} {target_id}"
            else:
                target_id = sanitize_node_id(str(dep))
                edge_str = f"  {source_id} --> {target_id}"
            
            if target_id and edge_str not in rendered_edges:
                rendered_edges.add(edge_str)
                lines.append(edge_str)

    # From explicit edges
    for edge in raw_edges:
        src = sanitize_node_id(edge.get("source", ""))
        tgt = sanitize_node_id(edge.get("target", ""))
        label = sanitize_c4_label(edge.get("label", ""))
        arrow = edge.get("arrow", "-->")
        if src and tgt:
            edge_str = f"  {src} {arrow}|{label}| {tgt}" if label else f"  {src} {arrow} {tgt}"
            if edge_str not in rendered_edges:
                rendered_edges.add(edge_str)
                lines.append(edge_str)

    # 4. Standard styling classes
    lines.append("")
    lines.append("  classDef default fill:#1e293b,stroke:#475569,stroke-width:2px,color:#f8fafc;")

    body = "\n".join(lines)
    if fenced:
        return f"```mermaid\n{body}\n```"
    return body
