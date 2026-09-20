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
Data schemas and manifest models for What-If Architectural Trade-Off Simulator.
Adheres to DESIGN.md § 2.1 and § 4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional


@dataclass
class TradeOffDimension:
    """
    Definition of an architectural trade-off dimension axis.
    """
    id: str
    name: str
    description: str = ""
    min: float = 0.0
    max: float = 100.0
    step: float = 1.0
    defaultValue: float = 50.0
    unit: str = ""
    higherIsBetter: bool = True
    weight: float = 1.0

    @property
    def default_value(self) -> float:
        return self.defaultValue

    @property
    def higher_is_better(self) -> bool:
        return self.higherIsBetter

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "min": self.min,
            "max": self.max,
            "step": self.step,
            "defaultValue": self.defaultValue,
            "unit": self.unit,
            "higherIsBetter": self.higherIsBetter,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TradeOffDimension:
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            min=float(data.get("min", 0.0)),
            max=float(data.get("max", 100.0)),
            step=float(data.get("step", 1.0)),
            defaultValue=float(data.get("defaultValue", data.get("default_value", 50.0))),
            unit=str(data.get("unit", "")),
            higherIsBetter=bool(data.get("higherIsBetter", data.get("higher_is_better", True))),
            weight=float(data.get("weight", 1.0)),
        )


@dataclass
class ArchitectureProfile:
    """
    Pre-configured architecture profile evaluated during tournament.
    """
    id: str
    name: str
    architect: str = ""
    summary: str = ""
    isRecommended: bool = False
    dimensionValues: Dict[str, float] = field(default_factory=dict)
    projectedMetrics: Optional[Dict[str, Any]] = None

    @property
    def is_recommended(self) -> bool:
        return self.isRecommended

    @property
    def dimension_values(self) -> Dict[str, float]:
        return self.dimensionValues

    @property
    def projected_metrics(self) -> Optional[Dict[str, Any]]:
        return self.projectedMetrics

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "architect": self.architect,
            "summary": self.summary,
            "isRecommended": self.isRecommended,
            "dimensionValues": dict(self.dimensionValues),
        }
        if self.projectedMetrics is not None:
            res["projectedMetrics"] = dict(self.projectedMetrics)
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArchitectureProfile:
        dim_vals = data.get("dimensionValues", data.get("dimension_values", {}))
        converted_dims = {str(k): float(v) for k, v in dim_vals.items()}
        proj_metrics = data.get("projectedMetrics", data.get("projected_metrics"))
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            architect=str(data.get("architect", "")),
            summary=str(data.get("summary", "")),
            isRecommended=bool(data.get("isRecommended", data.get("is_recommended", False))),
            dimensionValues=converted_dims,
            projectedMetrics=proj_metrics if proj_metrics is not None else None,
        )


@dataclass
class WhatIfSimulatorManifest:
    """
    Complete manifest for compiling dynamic Generative UI trade-off simulators.
    """
    projectName: str
    decisionTitle: str = "Architectural Trade-Off Analysis"
    description: str = ""
    dimensions: List[TradeOffDimension] = field(default_factory=list)
    profiles: Dict[str, ArchitectureProfile] = field(default_factory=dict)
    generatedAt: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def project_name(self) -> str:
        return self.projectName

    @property
    def decision_title(self) -> str:
        return self.decisionTitle

    @property
    def generated_at(self) -> str:
        return self.generatedAt

    def get_recommended_profile(self) -> Optional[ArchitectureProfile]:
        for prof in self.profiles.values():
            if prof.isRecommended:
                return prof
        if self.profiles:
            return next(iter(self.profiles.values()))
        return None

    def validate(self) -> List[str]:
        """
        Validates manifest structural integrity.
        Returns a list of error strings, or empty list if valid.
        """
        errors = []
        if not self.projectName.strip():
            errors.append("projectName must not be empty")
        if not self.dimensions:
            errors.append("dimensions list must contain at least 1 dimension")
        if not self.profiles:
            errors.append("profiles map must contain at least 1 profile")

        dim_ids = set()
        for dim in self.dimensions:
            if not dim.id.strip():
                errors.append("Dimension id must not be empty")
            if dim.id in dim_ids:
                errors.append(f"Duplicate dimension id: '{dim.id}'")
            dim_ids.add(dim.id)
            if dim.min >= dim.max:
                errors.append(f"Dimension '{dim.id}' min ({dim.min}) must be less than max ({dim.max})")
            if dim.step <= 0:
                errors.append(f"Dimension '{dim.id}' step must be positive, got {dim.step}")

        for prof_id, prof in self.profiles.items():
            if not prof.name.strip():
                errors.append(f"Profile '{prof_id}' name must not be empty")
            for dim_id in dim_ids:
                if dim_id not in prof.dimensionValues:
                    errors.append(f"Profile '{prof_id}' missing value for dimension '{dim_id}'")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "projectName": self.projectName,
            "decisionTitle": self.decisionTitle,
            "description": self.description,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "profiles": {k: p.to_dict() for k, p in self.profiles.items()},
            "generatedAt": self.generatedAt,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WhatIfSimulatorManifest:
        p_name = str(data.get("projectName", data.get("project_name", "")))
        d_title = str(data.get("decisionTitle", data.get("decision_title", "Architectural Trade-Off Analysis")))
        desc = str(data.get("description", ""))
        gen_at = str(data.get("generatedAt", data.get("generated_at", datetime.now(timezone.utc).isoformat())))

        raw_dims = data.get("dimensions", [])
        dims = [TradeOffDimension.from_dict(d) if isinstance(d, dict) else d for d in raw_dims]

        raw_profiles = data.get("profiles", {})
        profiles = {}
        if isinstance(raw_profiles, dict):
            for k, v in raw_profiles.items():
                profiles[str(k)] = ArchitectureProfile.from_dict(v) if isinstance(v, dict) else v

        return cls(
            projectName=p_name,
            decisionTitle=d_title,
            description=desc,
            dimensions=dims,
            profiles=profiles,
            generatedAt=gen_at,
        )

    @classmethod
    def from_json(cls, json_str: str) -> WhatIfSimulatorManifest:
        data = json.loads(json_str)
        return cls.from_dict(data)


def get_baseline_manifest(project_name: str = "WorkVisuals") -> WhatIfSimulatorManifest:
    """
    Returns the baseline 5-axis trade-off manifest as defined in DESIGN.md § 4.
    """
    dimensions = [
        TradeOffDimension(
            id="latency",
            name="P95 Latency",
            description="Tail execution latency for diagram rendering and compilation (lower is better)",
            min=5.0,
            max=50.0,
            step=1.0,
            defaultValue=14.0,
            unit="ms",
            higherIsBetter=False,
            weight=0.25,
        ),
        TradeOffDimension(
            id="memory",
            name="Memory Footprint",
            description="Peak process memory footprint during swarm execution (lower is better)",
            min=20.0,
            max=150.0,
            step=2.0,
            defaultValue=52.0,
            unit="MB",
            higherIsBetter=False,
            weight=0.20,
        ),
        TradeOffDimension(
            id="coldStart",
            name="Cold Start Time",
            description="Initialization overhead for sub-agent environment and visual modules (lower is better)",
            min=50.0,
            max=500.0,
            step=10.0,
            defaultValue=195.0,
            unit="ms",
            higherIsBetter=False,
            weight=0.15,
        ),
        TradeOffDimension(
            id="durability",
            name="Durability & Persistence",
            description="Resilience to crashes, state loss, and artifact corruption (higher is better)",
            min=50.0,
            max=100.0,
            step=1.0,
            defaultValue=94.0,
            unit="/100",
            higherIsBetter=True,
            weight=0.25,
        ),
        TradeOffDimension(
            id="complexity",
            name="Implementation Complexity",
            description="Architectural surface area, dependency count, and cognitive load (lower is better)",
            min=10.0,
            max=100.0,
            step=5.0,
            defaultValue=40.0,
            unit="/100",
            higherIsBetter=False,
            weight=0.15,
        ),
    ]

    profiles = {
        "alpha": ArchitectureProfile(
            id="alpha",
            name="Proposal Alpha (In-Memory / Canvas First)",
            architect="Design Architect Alpha",
            summary="Monolithic templates, lightweight inline Canvas radar engine, minimal disk writes.",
            isRecommended=False,
            dimensionValues={
                "latency": 12.0,
                "memory": 45.0,
                "coldStart": 180.0,
                "durability": 82.0,
                "complexity": 25.0,
            },
            projectedMetrics={
                "p95LatencyMs": 12,
                "memoryMb": 45,
                "coldStartMs": 180,
                "durabilityScore": 82,
                "implementationComplexity": 25,
            },
        ),
        "beta": ArchitectureProfile(
            id="beta",
            name="Proposal Beta (Modular / Manifest First)",
            architect="Design Architect Beta",
            summary="Decoupled visual_engine subpackage, manifest-driven generators, automated Mermaid linting.",
            isRecommended=False,
            dimensionValues={
                "latency": 18.0,
                "memory": 68.0,
                "coldStart": 220.0,
                "durability": 95.0,
                "complexity": 55.0,
            },
            projectedMetrics={
                "p95LatencyMs": 18,
                "memoryMb": 68,
                "coldStartMs": 220,
                "durabilityScore": 95,
                "implementationComplexity": 55,
            },
        ),
        "hybrid": ArchitectureProfile(
            id="hybrid",
            name="Synthesized Hybrid (Arbiter Approved)",
            architect="Architectural Arbiter",
            summary="Decoupled visual_engine package with high-DPI Canvas 2D radar visualizer and manifest compilation.",
            isRecommended=True,
            dimensionValues={
                "latency": 14.0,
                "memory": 52.0,
                "coldStart": 195.0,
                "durability": 94.0,
                "complexity": 40.0,
            },
            projectedMetrics={
                "p95LatencyMs": 14,
                "memoryMb": 52,
                "coldStartMs": 195,
                "durabilityScore": 94,
                "implementationComplexity": 40,
            },
        ),
    }

    return WhatIfSimulatorManifest(
        projectName=project_name,
        decisionTitle="Architecture Selection: Visual Production Swarm Engine",
        description="Evaluate latency, memory footprint, cold start, durability, and complexity trade-offs between Proposal Alpha, Proposal Beta, and the Synthesized Hybrid Architecture.",
        dimensions=dimensions,
        profiles=profiles,
    )


def get_baseline_simulator_manifest(project_name: str = "WorkVisuals") -> Dict[str, Any]:
    """
    Returns the baseline 5-axis manifest as a dictionary for initial scaffolding.
    """
    return get_baseline_manifest(project_name).to_dict()
