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
Compiler for What-If Architectural Trade-Off Simulator (Generative UI).
Generates a self-contained, single-file HTML5 artifact with native Canvas 2D radar visualizer,
interactive range sliders, high-DPI scaling, and Markdown decision card export.
Adheres to DESIGN.md § 2.2, § 2.3, § 3, and spike_results.md § 4.
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict, Union

from .manifest import WhatIfSimulatorManifest, get_baseline_manifest


def generate_headless_fallback_table(manifest_dict: Dict[str, Any]) -> str:
    """
    Generates a static HTML comparison matrix for the <noscript> section,
    allowing headless environments, CI runners, and terminal agents to inspect
    architectural trade-offs without executing JavaScript.
    """
    dimensions = manifest_dict.get("dimensions", [])
    profiles = manifest_dict.get("profiles", {})

    profile_list = list(profiles.values())
    headers = ["Metric Dimension"] + [p.get("name", p.get("id", "")) for p in profile_list] + ["Unit"]

    header_cells = "".join(f"<th class='p-2 font-medium text-[var(--muted-foreground)]'>{html.escape(h)}</th>" for h in headers)
    thead = f"<thead>\n<tr class='bg-[var(--background)] border-b border-[var(--border)]'>{header_cells}</tr>\n</thead>"

    rows = []
    for dim in dimensions:
        dim_id = dim.get("id", "")
        dim_name = dim.get("name", dim_id)
        unit = dim.get("unit", "")
        cells = [f"<td class='p-2 text-[var(--foreground)]'>{html.escape(dim_name)}</td>"]
        for prof in profile_list:
            vals = prof.get("dimensionValues", prof.get("dimension_values", {}))
            val = vals.get(dim_id, "N/A")
            val_str = f"{val} {unit}".strip() if val != "N/A" else "N/A"
            cells.append(f"<td class='p-2 text-[var(--foreground)]'>{html.escape(val_str)}</td>")
        cells.append(f"<td class='p-2 text-[var(--foreground)]'>{html.escape(unit)}</td>")
        row_content = "".join(cells)
        rows.append(f"<tr class='border-b border-[var(--border)] hover:bg-[var(--background)]/50'>{row_content}</tr>")

    tbody = f"<tbody>{''.join(rows)}</tbody>"
    return f"<table class='w-full text-left text-xs border border-[var(--border)] border-collapse my-3'>\n{thead}\n{tbody}\n</table>"


def compile_what_if_simulator(manifest: Union[Dict[str, Any], WhatIfSimulatorManifest]) -> str:
    """
    Compiles a self-contained, single-file HTML5 Generative UI artifact.
    Embeds native Canvas 2D radar rendering, responsive CSS, interactive sliders,
    and Markdown export logic with zero unauthorized external CDN dependencies.

    Args:
        manifest: Dictionary or WhatIfSimulatorManifest instance.

    Returns:
        Complete HTML string to write to .agents/design/what_if_simulator.html.
    """
    if isinstance(manifest, WhatIfSimulatorManifest):
        manifest_dict = manifest.to_dict()
    elif isinstance(manifest, dict):
        manifest_dict = manifest
    else:
        raise TypeError(f"Expected WhatIfSimulatorManifest or dict, got {type(manifest).__name__}")

    project_name = html.escape(str(manifest_dict.get("projectName", "WorkVisuals")))
    decision_title = html.escape(str(manifest_dict.get("decisionTitle", "Architectural Trade-Off Analysis")))
    description = html.escape(str(manifest_dict.get("description", "")))
    manifest_json = json.dumps(manifest_dict, indent=2)
    fallback_table = generate_headless_fallback_table(manifest_dict)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{decision_title} — {project_name}</title>
  <!-- Approved Antigravity Tailwind CDN dependency -->
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    /* Generative UI Theme Fallbacks & Smooth Transitions */
    :root {{
      --background: #0f172a;
      --card: #1e293b;
      --foreground: #f8fafc;
      --muted-foreground: #94a3b8;
      --border: #334155;
      --primary: #3b82f6;
      --primary-foreground: #ffffff;
      --accent: #10b981;
    }}
    .light {{
      --background: #f8fafc;
      --card: #ffffff;
      --foreground: #0f172a;
      --muted-foreground: #64748b;
      --border: #e2e8f0;
      --primary: #2563eb;
      --primary-foreground: #ffffff;
      --accent: #059669;
    }}
    input[type=range] {{
      accent-color: var(--primary);
    }}
  </style>
</head>
<body class="bg-transparent text-[var(--foreground)] antialiased p-3 sm:p-5 font-sans">
  <div class="max-w-5xl mx-auto bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] rounded-xl shadow-lg p-4 sm:p-6">
    <!-- Header Section -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-[var(--border)] pb-4 mb-5 gap-3">
      <div>
        <div class="flex items-center gap-2">
          <span class="px-2 py-0.5 text-xs font-semibold rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">Phase 3 Decision Gate</span>
          <h1 class="text-lg sm:text-xl font-bold tracking-tight text-[var(--foreground)]">{decision_title}</h1>
        </div>
        <p class="text-xs sm:text-sm text-[var(--muted-foreground)] mt-1">{description}</p>
      </div>
      <div class="flex items-center gap-2">
        <button id="btn-export" onclick="exportDecisionMarkdown()" class="px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-1 shadow-sm">
          <span>📋</span> Copy Decision Card
        </button>
      </div>
    </div>

    <!-- Profile Preset Selector -->
    <div class="mb-5">
      <label class="block text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mb-2">Architectural Configurations</label>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-2" id="preset-buttons">
        <!-- Dynamically injected preset buttons -->
      </div>
    </div>

    <!-- Main Interactive Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <!-- Left Column: Controls & Sensitivity Sliders (6 cols) -->
      <div class="lg:col-span-6 space-y-4">
        <div class="bg-[var(--background)]/60 border border-[var(--border)] rounded-lg p-4">
          <h2 class="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mb-3">Interactive Trade-off Controls</h2>
          <div class="space-y-4" id="sliders-container">
            <!-- Dynamically injected range sliders -->
          </div>
        </div>

        <!-- Metric Scorecard & Composite Efficiency -->
        <div class="bg-[var(--background)]/60 border border-[var(--border)] rounded-lg p-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">Synthesized Composite Score</span>
            <span id="composite-score" class="text-lg font-bold text-blue-400">0.0 / 100</span>
          </div>
          <div class="w-full bg-slate-700/50 rounded-full h-2.5 overflow-hidden">
            <div id="composite-bar" class="bg-blue-500 h-2.5 rounded-full transition-all duration-300" style="width: 0%"></div>
          </div>
          <p id="score-summary" class="text-xs text-[var(--muted-foreground)] mt-2 italic">Adjust sliders or choose a preset profile above to simulate architectural trade-offs.</p>
        </div>
      </div>

      <!-- Right Column: Canvas 2D Retina Radar Engine (6 cols) -->
      <div class="lg:col-span-6 flex flex-col items-center">
        <div class="w-full bg-[var(--background)]/60 border border-[var(--border)] rounded-lg p-4 flex flex-col items-center">
          <div class="w-full flex items-center justify-between mb-2">
            <h2 class="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">High-DPI Radar Polygon Visualization</h2>
            <div class="flex items-center gap-3 text-[10px] text-[var(--muted-foreground)]">
              <span class="flex items-center gap-1"><span class="inline-block w-2.5 h-2.5 rounded-full bg-blue-500"></span> Active Target</span>
              <span class="flex items-center gap-1"><span class="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 border border-emerald-400"></span> Recommended</span>
            </div>
          </div>
          
          <div class="relative w-full max-w-[420px] aspect-square flex items-center justify-center">
            <canvas id="radar-canvas" class="w-full h-full block" width="400" height="400"></canvas>
          </div>
          
          <div id="export-status" class="w-full text-center text-xs text-emerald-400 mt-2 font-medium hidden">
            ✓ Markdown Decision Card copied to clipboard!
          </div>
        </div>
      </div>
    </div>

    <!-- Non-JS / Headless Fallback Comparison Table -->
    <noscript>
      <div class="mt-6 border-t border-[var(--border)] pt-4">
        <h3 class="text-sm font-semibold text-[var(--foreground)] mb-2">Static Comparison Matrix (JavaScript Disabled)</h3>
        {fallback_table}
      </div>
    </noscript>
  </div>

  <script>
    const MANIFEST = {manifest_json};

    let state = {{
      activeProfileId: "hybrid",
      values: {{}},
      dimensions: MANIFEST.dimensions || [],
      profiles: MANIFEST.profiles || {{}}
    }};

    // Initialize values from recommended profile or first available
    function initState() {{
      const profileList = Object.values(state.profiles);
      const rec = profileList.find(p => p.isRecommended) || profileList[0];
      if (rec) {{
        state.activeProfileId = rec.id;
        state.values = Object.assign({{}}, rec.dimensionValues || rec.dimension_values);
      }} else {{
        state.activeProfileId = "custom";
        state.values = {{}};
        state.dimensions.forEach(dim => {{
          state.values[dim.id] = dim.defaultValue !== undefined ? dim.defaultValue : dim.default_value;
        }});
      }}
    }}

    // Render Preset Selection Buttons
    function renderPresets() {{
      const container = document.getElementById("preset-buttons");
      if (!container) return;
      container.innerHTML = "";
      for (const [key, prof] of Object.entries(state.profiles)) {{
        const isActive = state.activeProfileId === key;
        const btn = document.createElement("button");
        btn.className = `p-2.5 text-left rounded-lg border transition-all ${{
          isActive 
            ? "border-blue-500 bg-blue-500/10 text-white shadow-sm" 
            : "border-[var(--border)] bg-[var(--background)]/40 hover:bg-[var(--background)] text-[var(--muted-foreground)]"
        }}`;
        btn.onclick = () => selectProfile(key);
        
        let badge = "";
        if (prof.isRecommended || prof.is_recommended) {{
          badge = `<span class="ml-1.5 px-1.5 py-0.2 text-[9px] bg-emerald-500/20 text-emerald-300 rounded border border-emerald-500/30">RECOMMENDED</span>`;
        }}
        
        const displayName = prof.name ? prof.name.split(' (')[0] : key;
        btn.innerHTML = `
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold text-[var(--foreground)]">${{displayName}}${{badge}}</span>
          </div>
          <p class="text-[11px] line-clamp-1 mt-0.5 text-[var(--muted-foreground)]">${{prof.summary || ""}}</p>
        `;
        container.appendChild(btn);
      }}
    }}

    // Render Sensitivity Sliders
    function renderSliders() {{
      const container = document.getElementById("sliders-container");
      if (!container) return;
      container.innerHTML = "";
      state.dimensions.forEach(dim => {{
        const defaultVal = dim.defaultValue !== undefined ? dim.defaultValue : dim.default_value;
        const val = state.values[dim.id] !== undefined ? state.values[dim.id] : defaultVal;
        const wrapper = document.createElement("div");
        wrapper.className = "flex flex-col gap-1";
        const higherBetter = dim.higherIsBetter !== undefined ? dim.higherIsBetter : dim.higher_is_better;
        wrapper.innerHTML = `
          <div class="flex items-center justify-between text-xs">
            <span class="font-medium text-[var(--foreground)]">${{dim.name}}</span>
            <span class="font-mono text-blue-400 font-semibold" id="val-${{dim.id}}">${{val}} ${{dim.unit}}</span>
          </div>
          <input type="range" 
                 id="slider-${{dim.id}}" 
                 min="${{dim.min}}" 
                 max="${{dim.max}}" 
                 step="${{dim.step}}" 
                 value="${{val}}"
                 class="w-full cursor-pointer h-1.5 bg-slate-700 rounded-lg appearance-none"
                 oninput="onSliderChange('${{dim.id}}', this.value)" />
          <div class="flex justify-between text-[10px] text-[var(--muted-foreground)]">
            <span>${{dim.min}} ${{dim.unit}}</span>
            <span>${{higherBetter ? 'Higher is better' : 'Lower is better'}}</span>
            <span>${{dim.max}} ${{dim.unit}}</span>
          </div>
        `;
        container.appendChild(wrapper);
      }});
    }}

    function onSliderChange(dimId, newVal) {{
      state.values[dimId] = parseFloat(newVal);
      const valDisplay = document.getElementById(`val-${{dimId}}`);
      const dim = state.dimensions.find(d => d.id === dimId);
      if (valDisplay && dim) {{
        valDisplay.innerText = `${{newVal}} ${{dim.unit}}`;
      }}
      state.activeProfileId = "custom";
      renderPresets();
      updateCalculations();
      drawRadarChart();
    }}

    function selectProfile(profileId) {{
      state.activeProfileId = profileId;
      const prof = state.profiles[profileId];
      if (prof) {{
        const dimVals = prof.dimensionValues || prof.dimension_values || {{}};
        state.values = Object.assign({{}}, dimVals);
      }}
      renderPresets();
      renderSliders();
      updateCalculations();
      drawRadarChart();
    }}

    // Calculate Composite Score (0 - 100)
    function calculateCompositeScore() {{
      let totalWeight = 0;
      let weightedSum = 0;
      state.dimensions.forEach(dim => {{
        const defaultVal = dim.defaultValue !== undefined ? dim.defaultValue : dim.default_value;
        const val = state.values[dim.id] !== undefined ? state.values[dim.id] : defaultVal;
        const range = dim.max - dim.min;
        let norm = 0;
        const higherBetter = dim.higherIsBetter !== undefined ? dim.higherIsBetter : dim.higher_is_better;
        if (range > 0) {{
          norm = higherBetter 
            ? (val - dim.min) / range 
            : (dim.max - val) / range;
        }}
        norm = Math.max(0, Math.min(1, norm));
        const w = dim.weight !== undefined ? dim.weight : 1;
        weightedSum += norm * 100 * w;
        totalWeight += w;
      }});
      return totalWeight > 0 ? Math.round(weightedSum / totalWeight) : 0;
    }}

    function updateCalculations() {{
      const score = calculateCompositeScore();
      const scoreEl = document.getElementById("composite-score");
      const barEl = document.getElementById("composite-bar");
      const summaryEl = document.getElementById("score-summary");
      if (scoreEl) scoreEl.innerText = `${{score}} / 100`;
      if (barEl) {{
        barEl.style.width = `${{score}}%`;
        if (score >= 80) {{
          barEl.className = "bg-emerald-500 h-2.5 rounded-full transition-all duration-300";
        }} else if (score >= 60) {{
          barEl.className = "bg-blue-500 h-2.5 rounded-full transition-all duration-300";
        }} else {{
          barEl.className = "bg-amber-500 h-2.5 rounded-full transition-all duration-300";
        }}
      }}
      if (summaryEl) {{
        if (state.activeProfileId !== "custom" && state.profiles[state.activeProfileId]) {{
          const p = state.profiles[state.activeProfileId];
          summaryEl.innerText = `Active Profile: ${{p.name}} — ${{p.summary || ""}}`;
        }} else {{
          summaryEl.innerText = "Custom configuration: Real-time sensitivity simulation.";
        }}
      }}
    }}

    // Canvas 2D Retina Radar Engine with High-DPI Scaling
    function drawRadarChart() {{
      const canvas = document.getElementById("radar-canvas");
      if (!canvas) return;
      
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      const displaySize = Math.min(rect.width || 380, rect.height || 380);
      
      // High-DPI buffer scaling
      canvas.width = Math.round(displaySize * dpr);
      canvas.height = Math.round(displaySize * dpr);
      
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      if (ctx.resetTransform) {{
        ctx.resetTransform();
      }} else {{
        ctx.setTransform(1, 0, 0, 1, 0, 0);
      }}
      ctx.scale(dpr, dpr);
      
      const size = displaySize;
      const center = size / 2;
      const radius = center - 45;
      const dims = state.dimensions;
      const totalAxes = dims.length;
      if (totalAxes < 3) return;
      
      ctx.clearRect(0, 0, size, size);
      
      // Draw Concentric Polygonal Grid Lines
      const gridLevels = [0.2, 0.4, 0.6, 0.8, 1.0];
      gridLevels.forEach((lvl, idx) => {{
        ctx.beginPath();
        for (let i = 0; i < totalAxes; i++) {{
          const angle = -Math.PI / 2 + (i * 2 * Math.PI / totalAxes);
          const r = radius * lvl;
          const x = center + r * Math.cos(angle);
          const y = center + r * Math.sin(angle);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }}
        ctx.closePath();
        ctx.strokeStyle = idx === gridLevels.length - 1 ? "rgba(148, 163, 184, 0.4)" : "rgba(148, 163, 184, 0.15)";
        ctx.lineWidth = idx === gridLevels.length - 1 ? 1.5 : 1;
        ctx.stroke();
      }});

      // Draw Axis Spokes & Labels
      ctx.font = "10px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
      dims.forEach((dim, i) => {{
        const angle = -Math.PI / 2 + (i * 2 * Math.PI / totalAxes);
        const xSpoke = center + radius * Math.cos(angle);
        const ySpoke = center + radius * Math.sin(angle);
        
        // Spoke line
        ctx.beginPath();
        ctx.moveTo(center, center);
        ctx.lineTo(xSpoke, ySpoke);
        ctx.strokeStyle = "rgba(148, 163, 184, 0.25)";
        ctx.lineWidth = 1;
        ctx.stroke();
        
        // Label position with offset
        const labelR = radius + 22;
        const xLabel = center + labelR * Math.cos(angle);
        const yLabel = center + labelR * Math.sin(angle);
        
        ctx.fillStyle = "rgba(226, 232, 240, 0.9)";
        ctx.textAlign = Math.abs(Math.cos(angle)) < 0.2 ? "center" : (Math.cos(angle) > 0 ? "left" : "right");
        ctx.textBaseline = Math.abs(Math.sin(angle)) < 0.2 ? "middle" : (Math.sin(angle) > 0 ? "top" : "bottom");
        ctx.fillText(dim.name, xLabel, yLabel);
      }});

      // Draw Benchmark Recommended Profile Polygon (Emerald dashed)
      const recProfile = Object.values(state.profiles).find(p => p.isRecommended || p.is_recommended);
      if (recProfile) {{
        ctx.beginPath();
        const recVals = recProfile.dimensionValues || recProfile.dimension_values || {{}};
        dims.forEach((dim, i) => {{
          const angle = -Math.PI / 2 + (i * 2 * Math.PI / totalAxes);
          const val = recVals[dim.id] !== undefined ? recVals[dim.id] : dim.defaultValue;
          const range = dim.max - dim.min;
          const higherBetter = dim.higherIsBetter !== undefined ? dim.higherIsBetter : dim.higher_is_better;
          let norm = range > 0 ? (higherBetter ? (val - dim.min) / range : (dim.max - val) / range) : 0.5;
          norm = Math.max(0.05, Math.min(1.0, norm));
          const r = radius * norm;
          const x = center + r * Math.cos(angle);
          const y = center + r * Math.sin(angle);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }});
        ctx.closePath();
        ctx.strokeStyle = "rgba(16, 185, 129, 0.85)";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);
        ctx.fillStyle = "rgba(16, 185, 129, 0.08)";
        ctx.fill();
        ctx.stroke();
        ctx.setLineDash([]);
      }}

      // Draw Active Target Profile Polygon (Blue solid)
      ctx.beginPath();
      const activeCoords = [];
      dims.forEach((dim, i) => {{
        const angle = -Math.PI / 2 + (i * 2 * Math.PI / totalAxes);
        const defaultVal = dim.defaultValue !== undefined ? dim.defaultValue : dim.default_value;
        const val = state.values[dim.id] !== undefined ? state.values[dim.id] : defaultVal;
        const range = dim.max - dim.min;
        const higherBetter = dim.higherIsBetter !== undefined ? dim.higherIsBetter : dim.higher_is_better;
        let norm = range > 0 ? (higherBetter ? (val - dim.min) / range : (dim.max - val) / range) : 0.5;
        norm = Math.max(0.05, Math.min(1.0, norm));
        const r = radius * norm;
        const x = center + r * Math.cos(angle);
        const y = center + r * Math.sin(angle);
        activeCoords.push({{x, y}});
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }});
      ctx.closePath();
      ctx.strokeStyle = "rgba(59, 130, 246, 0.95)";
      ctx.lineWidth = 2.5;
      ctx.fillStyle = "rgba(59, 130, 246, 0.28)";
      ctx.fill();
      ctx.stroke();

      // Vertex Dots
      activeCoords.forEach(pt => {{
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 3.5, 0, 2 * Math.PI);
        ctx.fillStyle = "#60a5fa";
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1;
        ctx.stroke();
      }});
    }}

    // Export Formatted Markdown Decision Snippet for Sentinel ask_question
    function exportDecisionMarkdown() {{
      const score = calculateCompositeScore();
      const profName = (state.activeProfileId !== "custom" && state.profiles[state.activeProfileId])
        ? state.profiles[state.activeProfileId].name 
        : "Custom Architectural Configuration";
        
      let md = `### Architectural Decision Selection: ${{profName}}\\n\\n`;
      md += `**Composite Efficiency Score**: ${{score}} / 100\\n\\n`;
      md += `| Trade-Off Dimension | Simulated Value | Unit | Direction |\\n`;
      md += `|---|---|---|---|\\n`;
      state.dimensions.forEach(dim => {{
        const val = state.values[dim.id];
        const higherBetter = dim.higherIsBetter !== undefined ? dim.higherIsBetter : dim.higher_is_better;
        md += `| ${{dim.name}} | ${{val}} | ${{dim.unit}} | ${{higherBetter ? 'Higher is better' : 'Lower is better'}} |\\n`;
      }});
      md += `\\n*Generated by What-If Simulator at ${{new Date().toISOString()}}*\\n`;

      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(md).then(() => {{
          showExportStatus();
        }}).catch(() => {{
          fallbackCopy(md);
        }});
      }} else {{
        fallbackCopy(md);
      }}
      return md;
    }}

    function fallbackCopy(text) {{
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try {{
        document.execCommand("copy");
        showExportStatus();
      }} catch (e) {{
        console.log(text);
      }}
      document.body.removeChild(ta);
    }}

    function showExportStatus() {{
      const el = document.getElementById("export-status");
      if (el) {{
        el.classList.remove("hidden");
        setTimeout(() => el.classList.add("hidden"), 3000);
      }}
    }}

    // Initialization on DOM Load
    window.addEventListener("DOMContentLoaded", () => {{
      initState();
      renderPresets();
      renderSliders();
      updateCalculations();
      drawRadarChart();
      window.addEventListener("resize", drawRadarChart);
    }});
  </script>
</body>
</html>
"""
    return html_template
