# Copyright 2026 Google LLC
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

import os
import re
import sys
import json
import argparse
import html
import shutil

# ==============================================================================
# 4 Clean, High-Contrast, Proportional CSS Configurations
# ==============================================================================

THEME_CSS = {
    "technical": """
        /* TECHNICAL DOCUMENTATION THEME (Clean Light) */
        :root {
            --bg-canvas: #f8fafc;
            --bg-surface: #ffffff;
            --bg-surface-alt: #f1f5f9;
            --text-primary: #0f172a;
            --text-secondary: #334155;
            --text-muted: #64748b;
            --color-primary: #1e40af;
            --color-accent: #2563eb;
            --color-accent-glow: rgba(37, 99, 235, 0.08);
            --border-color: #e2e8f0;
            --font-heading: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
            --rounding: 8px;
            --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            --header-bg: #ffffff;
        }
        body {
            background-color: var(--bg-canvas);
            color: var(--text-primary);
            font-family: var(--font-body);
        }
        .main-container {
            display: grid;
            grid-template-columns: 240px minmax(0, 1fr) 200px;
            gap: 28px;
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px 24px;
        }
        @media(max-width: 1100px) {
            .main-container { grid-template-columns: 220px minmax(0, 1fr); }
            .toc-bar { display: none; }
        }
        @media(max-width: 768px) {
            .main-container { grid-template-columns: 1fr; padding: 16px; }
            .sidebar { position: relative; top: 0; height: auto; border-right: none; padding-right: 0; margin-bottom: 20px; }
        }
        .sidebar {
            position: sticky;
            top: 76px;
            height: calc(100vh - 100px);
            overflow-y: auto;
            border-right: 1px solid var(--border-color);
            padding-right: 20px;
        }
        .toc-bar {
            position: sticky;
            top: 76px;
            height: calc(100vh - 100px);
            overflow-y: auto;
            border-left: 1px solid var(--border-color);
            padding-left: 20px;
        }
        .prose-content {
            min-width: 0;
            line-height: 1.7;
            font-size: 15px;
        }
        .glass-panel {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: var(--rounding);
            box-shadow: var(--shadow-sm);
            padding: 32px;
            margin-bottom: 24px;
        }
    """,
    "obsidian": """
        /* LUMINOUS OBSIDIAN THEME (Sleek Dark) */
        :root {
            --bg-canvas: #0f172a;
            --bg-surface: #1e293b;
            --bg-surface-alt: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #cbd5e1;
            --text-muted: #94a3b8;
            --color-primary: #38bdf8;
            --color-accent: #0ea5e9;
            --color-accent-glow: rgba(56, 189, 248, 0.12);
            --border-color: #334155;
            --font-heading: 'Outfit', sans-serif;
            --font-body: 'Inter', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
            --rounding: 8px;
            --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
            --header-bg: #1e293b;
        }
        body {
            background-color: var(--bg-canvas);
            color: var(--text-primary);
            font-family: var(--font-body);
        }
        .main-container {
            display: grid;
            grid-template-columns: 240px minmax(0, 1fr) 200px;
            gap: 28px;
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px 24px;
        }
        @media(max-width: 1100px) {
            .main-container { grid-template-columns: 220px minmax(0, 1fr); }
            .toc-bar { display: none; }
        }
        @media(max-width: 768px) {
            .main-container { grid-template-columns: 1fr; padding: 16px; }
            .sidebar { position: relative; top: 0; height: auto; border-right: none; padding-right: 0; margin-bottom: 20px; }
        }
        .sidebar {
            position: sticky;
            top: 76px;
            height: calc(100vh - 100px);
            overflow-y: auto;
            border-right: 1px solid var(--border-color);
            padding-right: 20px;
        }
        .toc-bar {
            position: sticky;
            top: 76px;
            height: calc(100vh - 100px);
            overflow-y: auto;
            border-left: 1px solid var(--border-color);
            padding-left: 20px;
        }
        .prose-content {
            min-width: 0;
            line-height: 1.7;
            font-size: 15px;
        }
        .glass-panel {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: var(--rounding);
            box-shadow: var(--shadow-sm);
            padding: 32px;
            margin-bottom: 24px;
        }
    """,
    "proscript": """
        /* PROSCRIPT SYSTEM THEME (Enterprise Light) */
        :root {
            --bg-canvas: #fafafa;
            --bg-surface: #ffffff;
            --bg-surface-alt: #f4f4f5;
            --text-primary: #18181b;
            --text-secondary: #3f3f46;
            --text-muted: #71717a;
            --color-primary: #1e3a8a;
            --color-accent: #2563eb;
            --color-accent-glow: rgba(37, 99, 235, 0.08);
            --border-color: #e4e4e7;
            --font-heading: 'Outfit', sans-serif;
            --font-body: 'Inter', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
            --rounding: 6px;
            --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            --header-bg: #ffffff;
        }
        body {
            background-color: var(--bg-canvas);
            color: var(--text-primary);
            font-family: var(--font-body);
        }
        .main-container {
            display: grid;
            grid-template-columns: 240px minmax(0, 1fr) 200px;
            gap: 28px;
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px 24px;
        }
        @media(max-width: 1100px) {
            .main-container { grid-template-columns: 220px minmax(0, 1fr); }
            .toc-bar { display: none; }
        }
        @media(max-width: 768px) {
            .main-container { grid-template-columns: 1fr; padding: 16px; }
            .sidebar { position: relative; top: 0; height: auto; border-right: none; padding-right: 0; margin-bottom: 20px; }
        }
        .sidebar {
            position: sticky;
            top: 76px;
            height: calc(100vh - 100px);
            overflow-y: auto;
            border-right: 1px solid var(--border-color);
            padding-right: 20px;
        }
        .toc-bar {
            position: sticky;
            top: 76px;
            height: calc(100vh - 100px);
            overflow-y: auto;
            border-left: 1px solid var(--border-color);
            padding-left: 20px;
        }
        .prose-content {
            min-width: 0;
            line-height: 1.7;
            font-size: 15px;
        }
        .glass-panel {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: var(--rounding);
            box-shadow: var(--shadow-sm);
            padding: 32px;
            margin-bottom: 24px;
        }
    """,
    "dynamics": """
        /* TELEMETRY DYNAMICS THEME (High-Density Dark) */
        :root {
            --bg-canvas: #0c0a09;
            --bg-surface: #1c1917;
            --bg-surface-alt: #292524;
            --text-primary: #f7fee7;
            --text-secondary: #d6d3d1;
            --text-muted: #a8a29e;
            --color-primary: #22c55e;
            --color-accent: #16a34a;
            --color-accent-glow: rgba(34, 197, 94, 0.12);
            --border-color: #44403c;
            --font-heading: 'Outfit', sans-serif;
            --font-body: 'Inter', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
            --rounding: 6px;
            --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.4);
            --shadow-md: 0 4px 10px rgba(0, 0, 0, 0.5);
            --header-bg: #1c1917;
        }
        body {
            background-color: var(--bg-canvas);
            color: var(--text-primary);
            font-family: var(--font-body);
        }
        .main-container {
            display: grid;
            grid-template-columns: 240px minmax(0, 1fr) 200px;
            gap: 28px;
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px 24px;
        }
        @media(max-width: 1100px) {
            .main-container { grid-template-columns: 220px minmax(0, 1fr); }
            .toc-bar { display: none; }
        }
        @media(max-width: 768px) {
            .main-container { grid-template-columns: 1fr; padding: 16px; }
            .sidebar { position: relative; top: 0; height: auto; border-right: none; padding-right: 0; margin-bottom: 20px; }
        }
        .sidebar {
            position: sticky;
            top: 76px;
            height: calc(100vh - 100px);
            overflow-y: auto;
            border-right: 1px solid var(--border-color);
            padding-right: 20px;
        }
        .toc-bar {
            position: sticky;
            top: 76px;
            height: calc(100vh - 100px);
            overflow-y: auto;
            border-left: 1px solid var(--border-color);
            padding-left: 20px;
        }
        .prose-content {
            min-width: 0;
            line-height: 1.7;
            font-size: 15px;
        }
        .glass-panel {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: var(--rounding);
            box-shadow: var(--shadow-sm);
            padding: 32px;
            margin-bottom: 24px;
        }
    """
}

# ==============================================================================
# Markdown Parser Class
# ==============================================================================

class MarkdownParser:
    def __init__(self, theme_name):
        self.theme = theme_name
        self.headers = []

    def parse_frontmatter(self, md_text):
        frontmatter = {}
        content = md_text
        if md_text.startswith("---"):
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n", md_text, re.DOTALL)
            if match:
                fm_raw = match.group(1)
                content = md_text[match.end():]
                for line in fm_raw.split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        frontmatter[k.strip().lower()] = v.strip().strip('"').strip("'")
        return frontmatter, content

    def parse(self, md_content, doc_title=""):
        text = md_content

        # Custom containers ::: card
        def parse_cards(match):
            title = match.group(1).strip()
            body = match.group(2)
            header = f'<h4 class="text-base font-bold mb-2 text-[var(--text-primary)]">{title}</h4>' if title else ""
            return f'<div class="bg-[var(--bg-surface-alt)] border border-[var(--border-color)] p-5 rounded-lg my-4">{header}{body}</div>'
        
        text = re.compile(r":::\s*card\s*([^\n]*)\n(.*?)\n:::", re.DOTALL).sub(parse_cards, text)

        # Protect fenced code blocks
        code_blocks = []
        def save_code_block(match):
            lang = match.group(1) or "txt"
            code_text = match.group(2)
            code_idx = len(code_blocks)
            code_blocks.append((lang, code_text))
            return f"<!--CODE_BLOCK_{code_idx}-->"
        text = re.compile(r"```+(\w*)\n(.*?)```+", re.DOTALL).sub(save_code_block, text)

        # Protect inline code
        inline_codes = []
        def save_inline_code(match):
            code_idx = len(inline_codes)
            inline_codes.append(match.group(1))
            return f"<!--INLINE_CODE_{code_idx}-->"
        text = re.compile(r"`([^`\n]+)`").sub(save_inline_code, text)

        # Parse Headers cleanly
        def parse_header(match):
            level = len(match.group(1))
            title = match.group(2).strip()
            h_id = re.sub(r"[^a-zA-Z0-9\-]+", "-", title.lower()).strip("-")
            self.headers.append({"level": level, "title": title, "id": h_id})
            
            if level == 1:
                return f'<h1 id="{h_id}" class="text-2xl font-bold mb-4 pb-2 border-b border-[var(--border-color)] text-[var(--text-primary)]">{title}</h1>'
            elif level == 2:
                return f'<h2 id="{h_id}" class="text-xl font-bold mt-8 mb-3 text-[var(--text-primary)]">{title}</h2>'
            elif level == 3:
                return f'<h3 id="{h_id}" class="text-lg font-semibold mt-6 mb-2 text-[var(--text-primary)]">{title}</h3>'
            else:
                return f'<h{level} id="{h_id}" class="font-semibold mt-4 mb-2 text-[var(--text-primary)]">{title}</h{level}>'

        text = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE).sub(parse_header, text)

        # Links
        def render_links(match):
            label = match.group(1)
            url = match.group(2)
            if "file:///" in url or url.endswith(".md"):
                filename = os.path.basename(url)
                base, _ = os.path.splitext(filename)
                return f'<a href="{base}.html" class="nav-link-item">{label}</a>'
            return f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="external-link">{label}</a>'
        text = re.compile(r"\[([^\]]+)\]\(([^)]+)\)").sub(render_links, text)

        # Lines and Tables
        html_lines = []
        in_list = False
        in_table = False
        table_rows = []

        def parse_inline(ln):
            ln = re.compile(r"\*\*([^*]+)\*\*").sub(r"<strong>\1</strong>", ln)
            ln = re.compile(r"\*([^*]+)\*").sub(r"<em>\1</em>", ln)
            return ln

        for line in text.split("\n"):
            stripped = line.strip()

            if "|" in line and stripped.startswith("|") and stripped.endswith("|"):
                if re.match(r"^\|[\s\-:|]+\|$", stripped):
                    continue
                in_table = True
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                table_rows.append(cells)
                continue
            else:
                if in_table:
                    in_table = False
                    html_lines.append('<div class="overflow-x-auto my-4"><table class="rich-table">')
                    if table_rows:
                        html_lines.append('<thead><tr>')
                        for cell in table_rows[0]:
                            html_lines.append(f'<th>{parse_inline(cell)}</th>')
                        html_lines.append('</tr></thead><tbody>')
                        for row in table_rows[1:]:
                            html_lines.append('<tr>')
                            for cell in row:
                                html_lines.append(f'<td>{parse_inline(cell)}</td>')
                            html_lines.append('</tr>')
                    html_lines.append('</tbody></table></div>')
                    table_rows = []

            if stripped.startswith("- ") or stripped.startswith("* "):
                if not in_list:
                    in_list = True
                    html_lines.append('<ul class="list-disc pl-5 my-3 space-y-1">')
                item_content = stripped[2:]
                html_lines.append(f'<li>{parse_inline(item_content)}</li>')
                continue
            else:
                if in_list:
                    in_list = False
                    html_lines.append('</ul>')

            if not stripped:
                continue

            if stripped.startswith("<h") or stripped.startswith("<!--") or stripped.startswith("<div") or stripped.startswith("</div"):
                html_lines.append(line)
            else:
                html_lines.append(f'<p class="mb-4 text-[var(--text-secondary)]">{parse_inline(line)}</p>')

        if in_table:
            html_lines.append('<div class="overflow-x-auto my-4"><table class="rich-table">')
            if table_rows:
                html_lines.append('<thead><tr>')
                for cell in table_rows[0]:
                    html_lines.append(f'<th>{parse_inline(cell)}</th>')
                html_lines.append('</tr></thead><tbody>')
                for row in table_rows[1:]:
                    html_lines.append('<tr>')
                    for cell in row:
                        html_lines.append(f'<td>{parse_inline(cell)}</td>')
                    html_lines.append('</tr>')
            html_lines.append('</tbody></table></div>')

        text = "\n".join(html_lines)

        # Restore Inline Code
        for idx, ic in enumerate(inline_codes):
            escaped_code = html.escape(ic)
            text = text.replace(f"<!--INLINE_CODE_{idx}-->", f'<code class="inline-code">{escaped_code}</code>')

        # Restore Fenced Code Blocks
        for idx, (lang, block) in enumerate(code_blocks):
            escaped_block = html.escape(block)
            code_html = f"""
            <div class="code-container my-4">
                <div class="code-header">
                    <span>{lang.upper()}</span>
                    <button class="copy-btn" onclick="copyCode(this)">Copy</button>
                </div>
                <pre><code class="language-{lang}">{escaped_block}</code></pre>
            </div>
            """
            text = text.replace(f"<!--CODE_BLOCK_{idx}-->", code_html)

        return text

# ==============================================================================
# HTML Assembly Helper
# ==============================================================================

def assemble_html(title, desc, parsed_body, sidebar_nav, toc_html, theme, raw_markdown_src):
    css_tokens = THEME_CSS.get(theme, THEME_CSS["technical"])
    escaped_markdown = html.escape(raw_markdown_src)

    return f"""<!DOCTYPE html>
<html lang="en" class="{theme}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title if title else "Document Portal"}</title>
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Outfit:wght@500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    
    <style>
        {css_tokens}
        
        body {{
            margin: 0;
            padding: 0;
            background-color: var(--bg-canvas);
            color: var(--text-primary);
        }}
        
        .header-bar {{
            position: sticky;
            top: 0;
            z-index: 40;
            background: var(--header-bg);
            border-bottom: 1px solid var(--border-color);
            padding: 12px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .tab-btn {{
            padding: 5px 14px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--text-secondary);
            transition: all 0.15s ease;
        }}
        .tab-btn:hover {{
            color: var(--text-primary);
            background: var(--bg-surface-alt);
        }}
        .tab-btn.tab-active {{
            background: var(--color-accent-glow);
            color: var(--color-accent);
            border: 1px solid var(--border-color);
        }}
        
        .external-link, .nav-link-item {{
            color: var(--color-accent);
            text-decoration: underline;
            text-underline-offset: 2px;
            font-weight: 500;
        }}
        
        .rich-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
            border-radius: var(--rounding);
            border: 1px solid var(--border-color);
        }}
        .rich-table th {{
            background-color: var(--bg-surface-alt);
            color: var(--text-primary);
            font-weight: 600;
            text-align: left;
            padding: 10px 14px;
            border-bottom: 1px solid var(--border-color);
        }}
        .rich-table td {{
            padding: 10px 14px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-secondary);
        }}
        .rich-table th:first-child, .rich-table td:first-child {{
            white-space: nowrap !important;
        }}
        
        .code-container {{
            background-color: #0f172a;
            border: 1px solid var(--border-color);
            border-radius: var(--rounding);
            overflow: hidden;
            color: #f8fafc;
        }}
        .code-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 14px;
            background-color: #020617;
            border-bottom: 1px solid #1e293b;
            font-family: var(--font-mono);
            font-size: 0.75rem;
            color: #94a3b8;
        }}
        .copy-btn {{
            background: transparent;
            border: 1px solid #334155;
            padding: 2px 8px;
            border-radius: 4px;
            cursor: pointer;
            color: #cbd5e1;
            font-size: 0.7rem;
        }}
        pre {{
            margin: 0;
            padding: 16px;
            overflow-x: auto;
        }}
        code {{
            font-family: var(--font-mono);
            font-size: 0.85rem;
        }}
        .inline-code {{
            background-color: var(--bg-surface-alt);
            padding: 2px 5px;
            border-radius: 4px;
            font-family: var(--font-mono);
            font-size: 0.85em;
            color: var(--color-accent);
            border: 1px solid var(--border-color);
        }}
        
        .sidebar-link {{
            display: block;
            padding: 6px 10px;
            border-radius: var(--rounding);
            color: var(--text-secondary);
            font-size: 0.875rem;
            font-weight: 500;
            margin-bottom: 2px;
            text-decoration: none;
            transition: all 0.15s ease;
        }}
        .sidebar-link:hover {{
            background-color: var(--bg-surface-alt);
            color: var(--text-primary);
        }}
        .sidebar-link.active {{
            background-color: var(--color-accent-glow);
            color: var(--color-accent);
            font-weight: 600;
            border-left: 3px solid var(--color-accent);
        }}
    </style>
</head>
<body>

    <header class="header-bar">
        <div class="flex items-center gap-2">
            <span class="text-sm font-bold text-[var(--text-primary)]">{title if title else "Document"}</span>
        </div>
        <div class="flex gap-1 bg-[var(--bg-surface-alt)] border border-[var(--border-color)] rounded-md p-0.5">
            <button id="btn-ui-view" onclick="showView('ui')" class="tab-btn tab-active">🖥️ Reading View</button>
            <button id="btn-md-view" onclick="showView('md')" class="tab-btn">📄 Markdown Source</button>
        </div>
    </header>

    <div class="main-container">
        
        <aside class="sidebar">
            <div class="pb-3 border-b border-[var(--border-color)] mb-3">
                <span class="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">Navigation</span>
            </div>
            <nav>
                {sidebar_nav}
            </nav>
        </aside>

        <main class="prose-content">
            <div id="ui-view">
                <article class="glass-panel">
                    {parsed_body}
                </article>
            </div>

            <div id="markdown-view" class="hidden">
                <div class="glass-panel">
                    <div class="flex justify-between items-center pb-2 border-b border-[var(--border-color)] mb-4">
                        <span class="text-sm font-bold">Raw Markdown Source</span>
                        <button onclick="copyRawMarkdown(this)" class="copy-btn">Copy</button>
                    </div>
                    <pre class="bg-[#020617] border border-[#1e293b] rounded-md p-4 overflow-x-auto"><code class="language-markdown text-[#f8fafc]">{escaped_markdown}</code></pre>
                </div>
            </div>
        </main>

        <aside class="toc-bar">
            <span class="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">On This Page</span>
            <nav class="mt-3 space-y-1">
                {toc_html}
            </nav>
        </aside>

    </div>

    <script>
        function showView(view) {{
            const ui = document.getElementById('ui-view');
            const md = document.getElementById('markdown-view');
            const btnUi = document.getElementById('btn-ui-view');
            const btnMd = document.getElementById('btn-md-view');
            
            if (view === 'ui') {{
                ui.classList.remove('hidden');
                md.classList.add('hidden');
                btnUi.classList.add('tab-active');
                btnMd.classList.remove('tab-active');
            }} else {{
                ui.classList.add('hidden');
                md.classList.remove('hidden');
                btnUi.classList.remove('tab-active');
                btnMd.classList.add('tab-active');
            }}
        }}

        function copyCode(btn) {{
            const pre = btn.closest('.code-container').querySelector('code');
            navigator.clipboard.writeText(pre.innerText).then(() => {{
                btn.innerText = "Copied!";
                setTimeout(() => btn.innerText = "Copy", 1500);
            }});
        }}

        function copyRawMarkdown(btn) {{
            const code = document.querySelector('#markdown-view code');
            navigator.clipboard.writeText(code.innerText).then(() => {{
                btn.innerText = "Copied!";
                setTimeout(() => btn.innerText = "Copy", 1500);
            }});
        }}
    </script>
</body>
</html>
"""

# ==============================================================================
# Main Logic
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Clean Markdown to HTML Compiler")
    parser.add_argument("--file", help="Specific markdown file to compile")
    parser.add_argument("--dir", default="./docs", help="Directory where markdown files live")
    args = parser.parse_args()

    markdown_files = []
    if args.file:
        if os.path.exists(args.file):
            markdown_files.append(args.file)
    else:
        if os.path.exists(args.dir):
            for file in os.listdir(args.dir):
                if file.endswith(".md"):
                    markdown_files.append(os.path.join(args.dir, file))

    sidebar_links = []
    for f_path in sorted(markdown_files):
        basename = os.path.basename(f_path)
        base, _ = os.path.splitext(basename)
        sidebar_links.append(f'<a href="{base}.html" class="sidebar-link">{base.replace("_", " ").title()}</a>')
    sidebar_nav_html = "\n".join(sidebar_links)

    for f_path in markdown_files:
        with open(f_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        basename = os.path.basename(f_path)
        base, _ = os.path.splitext(basename)

        parser_instance = MarkdownParser("technical")
        fm, content = parser_instance.parse_frontmatter(raw_text)

        doc_title = fm.get("title", base.replace("_", " ").title())
        doc_desc = fm.get("description", "")
        doc_theme = fm.get("theme", "technical").lower()

        if doc_theme not in THEME_CSS:
            doc_theme = "technical"

        parser_instance.theme = doc_theme
        parsed_body = parser_instance.parse(content, doc_title=doc_title)

        toc_links = []
        for header in parser_instance.headers:
            if header["level"] == 2:
                toc_links.append(f'<a href="#{header["id"]}" class="sidebar-link text-xs">{header["title"]}</a>')
            elif header["level"] == 3:
                toc_links.append(f'<a href="#{header["id"]}" class="sidebar-link text-xs ml-2">{header["title"]}</a>')
        toc_html = "\n".join(toc_links)

        active_sidebar_nav = sidebar_nav_html.replace(
            f'href="{base}.html" class="sidebar-link"',
            f'href="{base}.html" class="sidebar-link active"'
        )

        final_html = assemble_html(
            doc_title,
            doc_desc,
            parsed_body,
            active_sidebar_nav,
            toc_html,
            doc_theme,
            raw_markdown_src=raw_text
        )

        out_folder = os.path.dirname(f_path)
        out_path = os.path.join(out_folder, f"{base}.html")
        with open(out_path, "w", encoding="utf-8") as f_out:
            f_out.write(final_html)

if __name__ == "__main__":
    main()
