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
Comprehensive unit tests for Visual Engine Subsystem & Generators.
Tests:
1. Manifest schemas, serialization, validation, and baseline generators.
2. C4 component diagram generator with strict adversarial label sanitization.
3. Sequence and dataflow diagram generator with autonumber and control blocks.
4. What-If simulator compiler (Canvas 2D radar, zero unauthorized CDNs, headless fallback).
"""

from pathlib import Path
import re
import sys
import unittest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from visual_engine.manifest import (
    ArchitectureProfile,
    TradeOffDimension,
    WhatIfSimulatorManifest,
    get_baseline_manifest,
    get_baseline_simulator_manifest,
)
from visual_engine.c4_generator import (
    render_c4_component_diagram,
    sanitize_c4_label,
    sanitize_node_id,
)
from visual_engine.sequence_generator import (
    render_sequence_diagram,
    sanitize_sequence_message,
)
from visual_engine.what_if_compiler import (
    compile_what_if_simulator,
    generate_headless_fallback_table,
)


class TestManifest(unittest.TestCase):
    """Tests for TradeOffDimension, ArchitectureProfile, and WhatIfSimulatorManifest."""

    def test_trade_off_dimension_serialization(self):
        dim = TradeOffDimension(
            id="throughput",
            name="Throughput",
            description="Operations per second",
            min=100.0,
            max=10000.0,
            step=50.0,
            defaultValue=500.0,
            unit="ops/sec",
            higherIsBetter=True,
            weight=0.3,
        )
        d = dim.to_dict()
        self.assertEqual(d["id"], "throughput")
        self.assertEqual(d["defaultValue"], 500.0)
        self.assertTrue(d["higherIsBetter"])

        # Test aliases
        self.assertEqual(dim.default_value, 500.0)
        self.assertTrue(dim.higher_is_better)

        # Reconstruct from dict
        reconstructed = TradeOffDimension.from_dict(d)
        self.assertEqual(reconstructed.id, dim.id)
        self.assertEqual(reconstructed.min, dim.min)
        self.assertEqual(reconstructed.max, dim.max)
        self.assertEqual(reconstructed.weight, dim.weight)

    def test_architecture_profile_serialization(self):
        prof = ArchitectureProfile(
            id="alpha",
            name="Proposal Alpha",
            architect="Architect Alpha",
            summary="In-memory design",
            isRecommended=False,
            dimensionValues={"latency": 10.0, "memory": 30.0},
            projectedMetrics={"p95LatencyMs": 10},
        )
        d = prof.to_dict()
        self.assertEqual(d["id"], "alpha")
        self.assertFalse(d["isRecommended"])
        self.assertEqual(d["dimensionValues"]["latency"], 10.0)

        # Test aliases
        self.assertFalse(prof.is_recommended)
        self.assertEqual(prof.dimension_values["latency"], 10.0)
        self.assertEqual(prof.projected_metrics["p95LatencyMs"], 10)

        # Reconstruct from dict
        reconstructed = ArchitectureProfile.from_dict(d)
        self.assertEqual(reconstructed.id, prof.id)
        self.assertEqual(reconstructed.name, prof.name)
        self.assertEqual(reconstructed.dimensionValues, prof.dimensionValues)

    def test_baseline_manifest(self):
        manifest = get_baseline_manifest("TestProject")
        self.assertEqual(manifest.projectName, "TestProject")
        self.assertEqual(len(manifest.dimensions), 5)
        self.assertIn("alpha", manifest.profiles)
        self.assertIn("beta", manifest.profiles)
        self.assertIn("hybrid", manifest.profiles)

        rec = manifest.get_recommended_profile()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.id, "hybrid")
        self.assertTrue(rec.isRecommended)

        # Validate no errors
        errors = manifest.validate()
        self.assertEqual(errors, [])

        # JSON roundtrip
        json_str = manifest.to_json()
        restored = WhatIfSimulatorManifest.from_json(json_str)
        self.assertEqual(restored.projectName, "TestProject")
        self.assertEqual(len(restored.dimensions), 5)

        # Test dictionary helper
        dict_manifest = get_baseline_simulator_manifest("TestProject")
        self.assertIsInstance(dict_manifest, dict)
        self.assertEqual(dict_manifest["projectName"], "TestProject")

    def test_manifest_validation_failures(self):
        # Empty project name
        m1 = WhatIfSimulatorManifest(projectName="", dimensions=[], profiles={})
        errors = m1.validate()
        self.assertIn("projectName must not be empty", errors)
        self.assertIn("dimensions list must contain at least 1 dimension", errors)
        self.assertIn("profiles map must contain at least 1 profile", errors)

        # Invalid dimension min/max
        bad_dim = TradeOffDimension(id="d1", name="D1", min=100.0, max=50.0)
        prof = ArchitectureProfile(id="p1", name="P1", dimensionValues={"d1": 60.0})
        m2 = WhatIfSimulatorManifest(projectName="P", dimensions=[bad_dim], profiles={"p1": prof})
        errs2 = m2.validate()
        self.assertTrue(any("min (100.0) must be less than max (50.0)" in e for e in errs2))

        # Missing dimension value in profile
        good_dim = TradeOffDimension(id="d2", name="D2", min=0.0, max=100.0)
        prof_missing = ArchitectureProfile(id="p2", name="P2", dimensionValues={})
        m3 = WhatIfSimulatorManifest(projectName="P", dimensions=[good_dim], profiles={"p2": prof_missing})
        errs3 = m3.validate()
        self.assertTrue(any("missing value for dimension 'd2'" in e for e in errs3))


class TestC4Generator(unittest.TestCase):
    """Tests for C4 component diagram generator and label sanitization."""

    def test_adversarial_label_sanitization(self):
        # 1. Standard Component
        self.assertEqual(sanitize_c4_label("Standard Component"), "Standard Component")
        # 2. Engine [v2.1.0]
        self.assertEqual(sanitize_c4_label("Engine [v2.1.0]"), "Engine [v2.1.0]")
        # 3. Database (SQLite / Async)
        self.assertEqual(sanitize_c4_label("Database (SQLite / Async)"), "Database (SQLite / Async)")
        # 4. Service "Auth" Gateway -> internal quotes escaped as #quot;
        self.assertEqual(sanitize_c4_label('Service "Auth" Gateway'), "Service #quot;Auth#quot; Gateway")
        # 5. Risk: A --> B injection -> arrows escaped
        self.assertEqual(sanitize_c4_label("Risk: A --> B injection"), "Risk: A --&gt; B injection")
        self.assertEqual(sanitize_c4_label("Risk: A ==> B injection"), "Risk: A ==&gt; B injection")
        # 6. Unsafe <script>alert(1)</script> clean -> stripped
        self.assertEqual(sanitize_c4_label("Unsafe <script>alert(1)</script> clean"), "Unsafe  clean")
        # 7. Multiline\nLine2\r\nLine3 -> <br/>
        self.assertEqual(sanitize_c4_label("Multiline\nLine2\r\nLine3"), "Multiline<br/>Line2<br/>Line3")
        # 8. Pipe | character -> &#124;
        self.assertEqual(sanitize_c4_label("Pipe | character"), "Pipe &#124; character")

    def test_node_id_sanitization(self):
        self.assertEqual(sanitize_node_id("scaffold_work.py"), "scaffold_work_py")
        self.assertEqual(sanitize_node_id("my-service@v1"), "my_service_v1")
        self.assertEqual(sanitize_node_id("123node"), "n_123node")
        self.assertEqual(sanitize_node_id(""), "node")

    def test_render_c4_component_diagram(self):
        spec = {
            "title": "Work Swarm Subsystem",
            "direction": "TD",
            "boundaries": [
                {"id": "CLI", "label": "Swarm Core CLI & Entrypoints"},
                {"id": "VEngine", "label": 'Visual Engine "Core" [v1.0]'},
            ],
            "components": [
                {
                    "id": "SW",
                    "name": 'scaffold_work "CLI"',
                    "technology": "Python Script",
                    "description": "Scaffolds <script>bad()</script> workspace & templates",
                    "boundary": "CLI",
                    "dependencies": ["C4Gen"],
                },
                {
                    "id": "C4Gen",
                    "name": "c4_generator.py",
                    "technology": "Python Module",
                    "description": "Renders C4 | diagrams cleanly\nNext line",
                    "boundary": "VEngine",
                    "dependencies": [],
                },
                {
                    "id": "UnboundedComp",
                    "name": "External Store",
                    "technology": "Disk",
                    "description": "Artifact storage",
                    "dependencies": [],
                },
            ],
        }

        rendered = render_c4_component_diagram(spec, fenced=True)
        # Check code fence
        self.assertTrue(rendered.startswith("```mermaid\n"))
        self.assertTrue(rendered.endswith("\n```"))
        self.assertIn("graph TD", rendered)

        # Check subgraphs
        self.assertIn('subgraph CLI ["Swarm Core CLI & Entrypoints"]', rendered)
        self.assertIn('subgraph VEngine ["Visual Engine #quot;Core#quot; [v1.0]"]', rendered)

        # Check node definitions are quoted
        self.assertIn('SW["<b>scaffold_work #quot;CLI#quot;</b><br/>[Python Script]<br/>Scaffolds  workspace & templates"]', rendered)
        # Check script tags stripped
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("bad()", rendered)

        # Check multiline and pipe escaping in C4Gen
        self.assertIn("&#124;", rendered)
        self.assertIn("<br/>Next line", rendered)

        # Check edge
        self.assertIn("SW --> C4Gen", rendered)

        # Test unfenced output
        unfenced = render_c4_component_diagram(spec, fenced=False)
        self.assertFalse(unfenced.startswith("```mermaid"))
        self.assertTrue(unfenced.startswith("graph TD"))

    def test_nested_boundaries_and_auto_registration(self):
        spec = {
            "direction": "LR",
            "diagram_type": "flowchart",
            "boundaries": [
                {"id": "RootBoundary", "label": "Root System"},
                {"id": "ChildBoundary", "label": "Child Subsystem", "parent": "RootBoundary"},
            ],
            "components": [
                {
                    "id": "NestedComp",
                    "name": "Nested Worker",
                    "boundary": "ChildBoundary",
                },
                {
                    "id": "AutoBoundComp",
                    "name": "Auto Bound Worker",
                    "boundary": "AutoCreatedBoundary",
                },
            ],
            "relationships": [
                {"source": "NestedComp", "target": "AutoBoundComp", "label": "Delegates task", "arrow": "-->"},
            ],
        }
        rendered = render_c4_component_diagram(spec)
        self.assertIn("flowchart LR", rendered)
        self.assertIn('subgraph RootBoundary ["Root System"]', rendered)
        self.assertIn('subgraph ChildBoundary ["Child Subsystem"]', rendered)
        self.assertIn('subgraph AutoCreatedBoundary ["AutoCreatedBoundary"]', rendered)
        self.assertIn('NestedComp["<b>Nested Worker</b>"]', rendered)
        self.assertIn('NestedComp -->|Delegates task| AutoBoundComp', rendered)


class TestSequenceGenerator(unittest.TestCase):
    """Tests for sequence and dataflow diagram generator."""

    def test_sanitize_sequence_message(self):
        self.assertEqual(sanitize_sequence_message("Simple message"), "Simple message")
        self.assertEqual(sanitize_sequence_message('Call "process"()'), "Call #quot;process#quot;()")
        self.assertEqual(sanitize_sequence_message("Multi\nLine"), "Multi<br/>Line")
        self.assertEqual(sanitize_sequence_message("Inject <script>alert(1)</script>"), "Inject")

    def test_render_sequence_diagram(self):
        participants = [
            {"id": "Sentinel", "label": "Work Sentinel (Primary Thread)"},
            {"id": "Scaffolder", "label": "scaffold_work.py"},
            {"id": "VEngine", "label": "visual_engine"},
        ]
        steps = [
            {"source": "Sentinel", "target": "Scaffolder", "message": "Run scaffold_work.py --topology lifecycle"},
            {"source": "Scaffolder", "target": "VEngine", "message": "Request baseline C4 diagrams"},
            {"source": "VEngine", "target": "Scaffolder", "message": "Formatted Mermaid blocks", "return": True},
            {"block": "par Parallel Design Authoring"},
            {"source": "Sentinel", "target": "VEngine", "message": "Render sequence diagram"},
            {"block": "end"},
            {"block": "alt Fundamental Trade-Off Detected"},
            {"source": "VEngine", "target": "Sentinel", "message": "Emit what_if_simulator.html"},
            {"block": "else No Trade-Off"},
            {"source": "Sentinel", "target": "Sentinel", "message": "Proceed directly"},
            {"block": "end"},
            {"note": "Lifecycle verified", "position": "over", "target": "Sentinel"},
        ]

        rendered = render_sequence_diagram(participants, steps, autonumber=True, fenced=True)

        self.assertTrue(rendered.startswith("```mermaid\n"))
        self.assertTrue(rendered.endswith("\n```"))
        self.assertIn("sequenceDiagram", rendered)
        self.assertIn("autonumber", rendered)

        # Participants
        self.assertIn("participant Sentinel as Work Sentinel (Primary Thread)", rendered)
        self.assertIn("participant Scaffolder as scaffold_work.py", rendered)

        # Interactions
        self.assertIn("Sentinel->>Scaffolder: Run scaffold_work.py --topology lifecycle", rendered)
        self.assertIn("VEngine-->>Scaffolder: Formatted Mermaid blocks", rendered)

        # Blocks
        self.assertIn("par Parallel Design Authoring", rendered)
        self.assertIn("alt Fundamental Trade-Off Detected", rendered)
        self.assertIn("else No Trade-Off", rendered)
        self.assertIn("Note over Sentinel: Lifecycle verified", rendered)

    def test_sequence_with_actors_and_loops(self):
        participants = ["User", {"id": "CLI", "label": "Swarm CLI", "actor": True}]
        steps = [
            {"block": "loop Health Check Interval"},
            {"source": "User", "target": "CLI", "message": "ping()", "activate": True},
            {"source": "CLI", "target": "User", "message": "pong()", "return": True, "deactivate": True},
            {"block": "end"},
        ]
        rendered = render_sequence_diagram(participants, steps, autonumber=False, fenced=False)
        self.assertNotIn("autonumber", rendered)
        self.assertIn("participant User", rendered)
        self.assertIn("actor CLI as Swarm CLI", rendered)
        self.assertIn("loop Health Check Interval", rendered)
        self.assertIn("activate CLI", rendered)
        self.assertIn("deactivate CLI", rendered)
        self.assertFalse(rendered.startswith("```mermaid"))


class TestWhatIfCompiler(unittest.TestCase):
    """Tests for What-If simulator compiler."""

    def test_compile_baseline_simulator(self):
        manifest = get_baseline_manifest("TestSwarm")
        html_content = compile_what_if_simulator(manifest)

        # 1. Self-contained HTML5 document
        self.assertTrue(html_content.startswith("<!DOCTYPE html>"))
        self.assertIn("<html lang=\"en\">", html_content)
        self.assertIn("</html>", html_content)

        # 2. Approved Antigravity Tailwind CDN dependency ONLY
        self.assertIn("https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js", html_content)

        # Audit for unauthorized script tags
        script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html_content, flags=re.IGNORECASE)
        self.assertEqual(len(script_srcs), 1, f"Found unexpected external scripts: {script_srcs}")
        self.assertEqual(script_srcs[0], "https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js")

        # Explicit forbidden CDN check
        forbidden_patterns = ["cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com", "chart.js", "d3", "googleapis.com"]
        for forbidden in forbidden_patterns:
            self.assertNotIn(forbidden, html_content)

        # 3. Canvas 2D Retina Engine presence
        self.assertIn('id="radar-canvas"', html_content)
        self.assertIn('getContext("2d")', html_content)
        self.assertIn("devicePixelRatio", html_content)
        self.assertIn("ctx.scale(dpr, dpr)", html_content)
        self.assertIn("drawRadarChart", html_content)

        # 4. Interactive controls & Export
        self.assertIn('id="preset-buttons"', html_content)
        self.assertIn('id="sliders-container"', html_content)
        self.assertIn("exportDecisionMarkdown", html_content)
        self.assertIn('id="composite-score"', html_content)
        self.assertIn('id="composite-bar"', html_content)

        # 5. Headless & Non-JS Fallback
        self.assertIn("<noscript>", html_content)
        self.assertIn("Static Comparison Matrix (JavaScript Disabled)", html_content)
        self.assertIn("P95 Latency", html_content)
        self.assertIn("Memory Footprint", html_content)
        self.assertIn("Durability & Persistence", html_content)

    def test_headless_fallback_table_direct(self):
        manifest_dict = get_baseline_simulator_manifest("FallbackTest")
        table_html = generate_headless_fallback_table(manifest_dict)
        self.assertIn("<table", table_html)
        self.assertIn("Metric Dimension", table_html)
        self.assertIn("Proposal Alpha", table_html)
        self.assertIn("Proposal Beta", table_html)
        self.assertIn("Synthesized Hybrid", table_html)
        self.assertIn("P95 Latency", table_html)

    def test_compile_custom_manifest(self):
        custom_manifest = WhatIfSimulatorManifest(
            projectName="CustomEngine",
            decisionTitle="Storage Engine Selection",
            description="Choose between SQLite and In-Memory KV",
            dimensions=[
                TradeOffDimension(
                    id="cost",
                    name="Monthly Cost",
                    min=10.0,
                    max=100.0,
                    defaultValue=25.0,
                    unit="$",
                    higherIsBetter=False,
                ),
                TradeOffDimension(
                    id="durability",
                    name="Durability",
                    min=0.0,
                    max=100.0,
                    defaultValue=90.0,
                    unit="%",
                    higherIsBetter=True,
                ),
                TradeOffDimension(
                    id="simplicity",
                    name="Simplicity",
                    min=1.0,
                    max=10.0,
                    defaultValue=8.0,
                    unit="/10",
                    higherIsBetter=True,
                ),
            ],
            profiles={
                "sqlite": ArchitectureProfile(
                    id="sqlite",
                    name="SQLite Engine",
                    summary="Persistent file storage",
                    isRecommended=True,
                    dimensionValues={"cost": 15.0, "durability": 98.0, "simplicity": 7.0},
                ),
                "memory": ArchitectureProfile(
                    id="memory",
                    name="In-Memory KV",
                    summary="Ultra fast transient storage",
                    isRecommended=False,
                    dimensionValues={"cost": 30.0, "durability": 50.0, "simplicity": 9.0},
                ),
            },
        )

        compiled = compile_what_if_simulator(custom_manifest)
        self.assertIn("Storage Engine Selection — CustomEngine", compiled)
        self.assertIn("Monthly Cost", compiled)
        self.assertIn("SQLite Engine", compiled)
        self.assertIn("In-Memory KV", compiled)

    def test_compile_from_dict_and_invalid_type(self):
        # From dict
        manifest_dict = get_baseline_simulator_manifest("DictSwarm")
        compiled = compile_what_if_simulator(manifest_dict)
        self.assertTrue(compiled.startswith("<!DOCTYPE html>"))
        self.assertIn("DictSwarm", compiled)

        # Invalid type raises TypeError
        with self.assertRaises(TypeError):
            compile_what_if_simulator("invalid_string_manifest")  # type: ignore

    def test_html_escaping_in_headers(self):
        malicious_manifest = WhatIfSimulatorManifest(
            projectName="<script>evil()</script>Project",
            decisionTitle="Choice <title>Attack</title> & Trade-offs",
            description="Testing <img src=x onerror=alert(1)> description",
            dimensions=[
                TradeOffDimension(id="d", name="Dim <bad>", min=0, max=10),
            ],
            profiles={
                "p": ArchitectureProfile(id="p", name="Profile <evil>", dimensionValues={"d": 5}),
            },
        )
        compiled = compile_what_if_simulator(malicious_manifest)
        # Ensure raw unescaped script / tags not in HTML title / header outside embedded JSON
        body_section = compiled.split("<script>")[1]  # after tailwind script tag, before embedded JSON script
        html_markup = compiled.split("<script>\n    const MANIFEST")[0]
        self.assertNotIn("<script>evil()</script>", html_markup)
        self.assertIn("&lt;script&gt;evil()&lt;/script&gt;Project", html_markup)
        self.assertIn("&lt;title&gt;Attack&lt;/title&gt;", html_markup)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html_markup)


class TestAdversarialVisualStress(unittest.TestCase):
    """Adversarial stress tests for hostile payloads, boundary edge cases, and extreme inputs."""

    def test_c4_hostile_payloads_and_empty_inputs(self):
        # Empty spec
        empty_c4 = render_c4_component_diagram({}, fenced=True)
        self.assertIn("graph TD", empty_c4)
        self.assertIn("```mermaid", empty_c4)

        # Hostile script, quotes, pipes, arrows
        hostile_spec = {
            "title": 'Hostile <script>alert(1)</script> "System"',
            "boundaries": [
                {"id": "<script>b1</script>", "label": 'Boundary <style>body{color:red}</style> "One"'}
            ],
            "components": [
                {
                    "id": "123hostile-id",
                    "name": 'Component "Alpha" <script>bad()</script>',
                    "technology": "Python --> Pipeline ==> BigQuery | Worker",
                    "description": "Risk of [injection] & (corruption) with 'single' and \"double\" quotes",
                    "boundary": "<script>b1</script>",
                    "dependencies": [{"target": "123hostile-id", "label": "Self | loop --> test"}],
                }
            ],
        }
        rendered = render_c4_component_diagram(hostile_spec)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<style>", rendered)
        self.assertIn("#quot;Alpha#quot;", rendered)
        self.assertIn("&#124;", rendered)
        self.assertIn("--&gt;", rendered)
        self.assertIn("==&gt;", rendered)

    def test_c4_deeply_nested_and_cyclic_boundaries(self):
        # 5-level nested boundaries
        nested_spec = {
            "boundaries": [
                {"id": "L1", "label": "Level 1"},
                {"id": "L2", "label": "Level 2", "parent": "L1"},
                {"id": "L3", "label": "Level 3", "parent": "L2"},
                {"id": "L4", "label": "Level 4", "parent": "L3"},
                {"id": "L5", "label": "Level 5", "parent": "L4"},
            ],
            "components": [
                {"id": "DeepWorker", "name": "Deep Worker", "boundary": "L5"}
            ]
        }
        rendered = render_c4_component_diagram(nested_spec)
        for i in range(1, 6):
            self.assertIn(f"subgraph L{i}", rendered)

        # Cyclic boundaries should not cause RecursionError
        cyclic_spec = {
            "boundaries": [
                {"id": "B1", "label": "B1", "parent": "B2"},
                {"id": "B2", "label": "B2", "parent": "B1"},
            ],
            "components": [
                {"id": "C1", "name": "C1", "boundary": "B1"}
            ]
        }
        rendered_cyclic = render_c4_component_diagram(cyclic_spec)
        self.assertIn("subgraph B1", rendered_cyclic)

    def test_c4_extreme_multiline_component(self):
        # 50 lines description
        multiline_desc = "\n".join([f"Line {i}: Processing payload with | and \"quotes\"" for i in range(50)])
        spec = {
            "components": [
                {"id": "ExtremeComp", "name": "Extreme Component", "description": multiline_desc}
            ]
        }
        rendered = render_c4_component_diagram(spec)
        # Verify node declaration stays on single logical line using <br/>
        node_lines = [l for l in rendered.splitlines() if "ExtremeComp[" in l]
        self.assertEqual(len(node_lines), 1)
        self.assertIn("<br/>", node_lines[0])

    def test_sequence_generator_hostile_and_empty_inputs(self):
        # Empty participants and steps
        empty_seq = render_sequence_diagram([], [])
        self.assertIn("sequenceDiagram", empty_seq)

        # Hostile script tags in block_text and messages
        participants = [
            {"id": "<script>p1</script>", "label": 'Participant <script>alert("xss")</script> "One"'}
        ]
        steps = [
            {"block": "par Parallel <script>alert(1)</script>"},
            {"source": "<script>p1</script>", "target": "<script>p1</script>", "message": 'Message with "quotes" & <style>bad</style>'},
            {"block": "end"},
            {"note": "Note with <script>evil()</script>", "target": "<script>p1</script>"}
        ]
        rendered = render_sequence_diagram(participants, steps)
        self.assertNotIn("<script", rendered)
        self.assertNotIn("<style", rendered)
        self.assertIn("#quot;", rendered)
        self.assertIn("sequenceDiagram", rendered)

        # Empty step should be skipped cleanly without emitting node->>node
        empty_step_seq = render_sequence_diagram(["A"], [{}])
        self.assertNotIn("->>", empty_step_seq)

    def test_what_if_compiler_edge_case_1_dimension(self):
        manifest_1dim = WhatIfSimulatorManifest(
            projectName="OneDimProject",
            decisionTitle="1-Axis Decision",
            dimensions=[
                TradeOffDimension(id="simplicity", name="Simplicity", min=0.0, max=10.0, defaultValue=8.0, unit="/10")
            ],
            profiles={
                "base": ArchitectureProfile(id="base", name="Base Profile", dimensionValues={"simplicity": 8.0})
            }
        )
        html_out = compile_what_if_simulator(manifest_1dim)
        self.assertTrue(html_out.startswith("<!DOCTYPE html>"))
        self.assertIn("Simplicity", html_out)
        self.assertIn("totalAxes < 3", html_out)
        # Headless table fallback
        table = generate_headless_fallback_table(manifest_1dim.to_dict())
        self.assertIn("Simplicity", table)

    def test_what_if_compiler_edge_case_10_dimensions(self):
        dims = [
            TradeOffDimension(
                id=f"dim_{i}",
                name=f"Axis {i}",
                min=0.0,
                max=100.0,
                defaultValue=float(i * 10),
                higherIsBetter=(i % 2 == 0)
            )
            for i in range(1, 11)
        ]
        prof_vals = {f"dim_{i}": float(i * 10) for i in range(1, 11)}
        manifest_10dim = WhatIfSimulatorManifest(
            projectName="TenDimProject",
            decisionTitle="10-Axis Decathlon",
            dimensions=dims,
            profiles={
                "decathlon": ArchitectureProfile(id="decathlon", name="Decathlon Profile", dimensionValues=prof_vals)
            }
        )
        html_out = compile_what_if_simulator(manifest_10dim)
        for i in range(1, 11):
            self.assertIn(f"Axis {i}", html_out)
        table = generate_headless_fallback_table(manifest_10dim.to_dict())
        for i in range(1, 11):
            self.assertIn(f"Axis {i}", table)

    def test_what_if_compiler_edge_case_inverted_polarity(self):
        dims = [
            TradeOffDimension(id="latency", name="Latency", min=10.0, max=1000.0, defaultValue=20.0, unit="ms", higherIsBetter=False),
            TradeOffDimension(id="cost", name="Cost", min=50.0, max=5000.0, defaultValue=200.0, unit="$", higherIsBetter=False),
        ]
        manifest = WhatIfSimulatorManifest(
            projectName="InvertedProject",
            decisionTitle="Inverted Polarity",
            dimensions=dims,
            profiles={
                "efficient": ArchitectureProfile(id="efficient", name="Efficient", dimensionValues={"latency": 25.0, "cost": 150.0})
            }
        )
        html_out = compile_what_if_simulator(manifest)
        self.assertIn("Lower is better", html_out)
        self.assertIn("higherBetter ? (val - dim.min) / range : (dim.max - val) / range", html_out)

    def test_what_if_compiler_edge_case_missing_profiles(self):
        # Empty profiles dictionary manifest
        manifest_dict = {
            "projectName": "EmptyProfiles",
            "decisionTitle": "Zero Profiles",
            "dimensions": [
                {"id": "speed", "name": "Speed", "min": 0, "max": 100, "defaultValue": 50, "unit": "mph", "higherIsBetter": True}
            ],
            "profiles": {}
        }
        html_out = compile_what_if_simulator(manifest_dict)
        self.assertTrue(html_out.startswith("<!DOCTYPE html>"))
        self.assertIn('state.activeProfileId = "custom"', html_out)
        table = generate_headless_fallback_table(manifest_dict)
        self.assertIn("<table", table)
        self.assertIn("Speed", table)


if __name__ == "__main__":
    unittest.main()
