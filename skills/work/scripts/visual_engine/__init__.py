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
Visual Engine Subsystem for Work Swarms.
Provides decoupled diagram generators (C4 component block, sequence/dataflow)
and What-If architectural trade-off simulator compilation.
"""

from .c4_generator import (
    render_c4_component_diagram,
    sanitize_c4_label,
    sanitize_node_id,
)
from .manifest import (
    ArchitectureProfile,
    TradeOffDimension,
    WhatIfSimulatorManifest,
    get_baseline_manifest,
    get_baseline_simulator_manifest,
)
from .sequence_generator import (
    render_sequence_diagram,
    sanitize_sequence_message,
)
from .what_if_compiler import (
    compile_what_if_simulator,
    generate_headless_fallback_table,
)

__all__ = [
    "ArchitectureProfile",
    "TradeOffDimension",
    "WhatIfSimulatorManifest",
    "compile_what_if_simulator",
    "generate_headless_fallback_table",
    "get_baseline_manifest",
    "get_baseline_simulator_manifest",
    "render_c4_component_diagram",
    "render_sequence_diagram",
    "sanitize_c4_label",
    "sanitize_node_id",
    "sanitize_sequence_message",
]
