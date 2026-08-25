#!/usr/bin/env python3
"""
Antigravity Prompt-Writer Registry Manager & Dashboard Generator

Provides CLI and programmatic management for .gemini/prompts/registry.json,
auto-syncing background tasks and subagents with prompt execution statuses.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone

REGISTRY_RELATIVE_PATH = os.path.join(".gemini", "prompts", "registry.json")
DASHBOARD_RELATIVE_PATH = os.path.join(".gemini", "prompts", "dashboard.html")


def get_app_data_dir():
    """Retrieve Antigravity CLI app data directory."""
    home = os.path.expanduser("~")
    return os.environ.get("ANTIGRAVITY_APP_DATA_DIR", os.path.join(home, ".gemini", "antigravity-cli"))


def find_project_root(start_dir=None):
    """Find the active workspace root containing .gemini or git repo."""
    curr = os.path.abspath(start_dir or os.getcwd())
    while curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, ".gemini")) or os.path.exists(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)
    return os.path.abspath(start_dir or os.getcwd())


def get_registry_path(project_root=None):
    root = project_root or find_project_root()
    prompts_dir = os.path.join(root, ".gemini", "prompts")
    os.makedirs(prompts_dir, exist_ok=True)
    return os.path.join(prompts_dir, "registry.json")


def load_registry(project_root=None):
    reg_path = get_registry_path(project_root)
    if not os.path.exists(reg_path):
        initial = {
            "project_root": project_root or find_project_root(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "prompts": []
        }
        save_registry(initial, project_root)
        return initial
    try:
        with open(reg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        sys.stderr.write(f"Error loading registry at {reg_path}: {e}\n")
        return {"project_root": project_root or find_project_root(), "last_updated": datetime.now(timezone.utc).isoformat(), "prompts": []}


def save_registry(registry, project_root=None):
    reg_path = get_registry_path(project_root)
    registry["last_updated"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(reg_path), exist_ok=True)
    with open(reg_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def register_prompt(prompt_id, title, mode="interactive", status="WAITING_IMPLEMENTATION", parent_id=None, tags=None, project_root=None):
    registry = load_registry(project_root)
    now = datetime.now(timezone.utc).isoformat()
    
    existing = next((p for p in registry["prompts"] if p["id"] == prompt_id), None)
    if existing:
        existing["title"] = title or existing.get("title", prompt_id)
        existing["mode"] = mode or existing.get("mode", "interactive")
        existing["status"] = status or existing.get("status", "WAITING_IMPLEMENTATION")
        existing["updated_at"] = now
        if parent_id is not None:
            existing["parent_id"] = parent_id
        if tags is not None:
            existing["tags"] = tags
        entry = existing
    else:
        entry = {
            "id": prompt_id,
            "title": title or f"Prompt {prompt_id}",
            "mode": mode,
            "status": status,
            "created_at": now,
            "updated_at": now,
            "parent_id": parent_id,
            "tags": tags or [],
            "execution_runtime": None
        }
        registry["prompts"].append(entry)
        
    save_registry(registry, project_root)
    return entry


def set_status(prompt_id, status, conversation_id=None, task_id=None, log_file=None, project_root=None):
    registry = load_registry(project_root)
    now = datetime.now(timezone.utc).isoformat()
    
    prompt = next((p for p in registry["prompts"] if p["id"] == prompt_id), None)
    if not prompt:
        prompt = register_prompt(prompt_id, f"Prompt {prompt_id}", status=status, project_root=project_root)
        registry = load_registry(project_root)
        prompt = next((p for p in registry["prompts"] if p["id"] == prompt_id), None)

    prompt["status"] = status.upper()
    prompt["updated_at"] = now

    if conversation_id or task_id or log_file or status == "EXECUTING":
        if not prompt.get("execution_runtime"):
            prompt["execution_runtime"] = {}
        runtime = prompt["execution_runtime"]
        if conversation_id:
            runtime["conversation_id"] = conversation_id
        if task_id:
            runtime["task_id"] = task_id
        if log_file:
            runtime["log_file"] = log_file
        if status == "EXECUTING" and "started_at" not in runtime:
            runtime["started_at"] = now
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            runtime["completed_at"] = now

    save_registry(registry, project_root)
    return prompt


def auto_sync_registry(project_root=None):
    root = project_root or find_project_root()
    registry = load_registry(root)
    updated_count = 0

    prompts_items = registry["prompts"].values() if isinstance(registry.get("prompts"), dict) else registry.get("prompts", [])

    for prompt in prompts_items:
        prompt_id = prompt.get("id")
        if not prompt_id:
            continue
        status = prompt.get("status", "WAITING_IMPLEMENTATION")
        
        # Check task_graph.json DAG deck progress
        prompt_dir = os.path.join(root, ".gemini", "prompts", prompt_id)
        task_graph_path = os.path.join(prompt_dir, "task_graph.json")
        if os.path.exists(task_graph_path):
            try:
                with open(task_graph_path, "r", encoding="utf-8") as tgf:
                    tg_data = json.load(tgf)
                    nodes = tg_data.get("nodes", [])
                    total_nodes = len(nodes)
                    verified_nodes = sum(1 for n in nodes if n.get("status") in ("VERIFIED", "COMPLETED"))
                    prompt["dag_progress"] = f"{verified_nodes}/{total_nodes} nodes"
                    if total_nodes > 0 and verified_nodes == total_nodes and status == "EXECUTING":
                        prompt["status"] = "COMPLETED"
                        prompt["updated_at"] = datetime.now(timezone.utc).isoformat()
                        updated_count += 1
            except Exception:
                pass

        # Check disk artifact completion
        task_dir = os.path.join(root, ".gemini", "tasks", prompt_id)
        walkthrough_path = os.path.join(task_dir, "walkthrough.md")
        root_walkthrough = os.path.join(root, "walkthrough.md")

        if status == "EXECUTING":
            # Check if walkthrough was produced
            if os.path.exists(walkthrough_path) or os.path.exists(root_walkthrough):
                prompt["status"] = "COMPLETED"
                prompt["updated_at"] = datetime.now(timezone.utc).isoformat()
                if prompt.get("execution_runtime"):
                    prompt["execution_runtime"]["completed_at"] = datetime.now(timezone.utc).isoformat()
                updated_count += 1
                continue

            # Check conversation transcript status if available
            runtime = prompt.get("execution_runtime") or {}
            conv_id = runtime.get("conversation_id")
            if conv_id:
                app_data = get_app_data_dir()
                transcript_path = os.path.join(app_data, "brain", conv_id, ".system_generated", "logs", "transcript.jsonl")
                if os.path.exists(transcript_path):
                    try:
                        with open(transcript_path, "r", encoding="utf-8") as tf:
                            lines = tf.readlines()
                            last_lines = "".join(lines[-20:])
                            if "GOAL_COMPLETE" in last_lines or "walkthrough.md" in last_lines:
                                prompt["status"] = "COMPLETED"
                                prompt["updated_at"] = datetime.now(timezone.utc).isoformat()
                                updated_count += 1
                            elif "GOAL_CANCELLED" in last_lines:
                                prompt["status"] = "CANCELLED"
                                prompt["updated_at"] = datetime.now(timezone.utc).isoformat()
                                updated_count += 1
                    except Exception:
                        pass

    if updated_count > 0:
        save_registry(registry, root)
        
    return registry, updated_count


def generate_html_dashboard(project_root=None, output_path=None):
    root = project_root or find_project_root()
    registry, _ = auto_sync_registry(root)
    
    out_path = output_path or os.path.join(root, DASHBOARD_RELATIVE_PATH)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    prompts = registry.get("prompts", [])
    
    # Counts
    total = len(prompts)
    waiting = sum(1 for p in prompts if p.get("status") == "WAITING_IMPLEMENTATION")
    executing = sum(1 for p in prompts if p.get("status") == "EXECUTING")
    completed = sum(1 for p in prompts if p.get("status") == "COMPLETED")
    failed = sum(1 for p in prompts if p.get("status") in ("FAILED", "CANCELLED"))

    prompts_json = json.dumps(prompts, indent=2, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Prompt Registry & Status Portal</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-primary: #0f172a;
      --bg-surface: #1e293b;
      --bg-surface-hover: #334155;
      --border-color: #334155;
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --accent-blue: #38bdf8;
      --accent-green: #34d399;
      --accent-yellow: #fbbf24;
      --accent-red: #f87171;
      --accent-purple: #c084fc;
      --badge-bg: rgba(255,255,255,0.06);
    }}

    [data-theme="light"] {{
      --bg-primary: #f8fafc;
      --bg-surface: #ffffff;
      --bg-surface-hover: #f1f5f9;
      --border-color: #e2e8f0;
      --text-primary: #0f172a;
      --text-secondary: #64748b;
      --accent-blue: #0284c7;
      --accent-green: #10b981;
      --accent-yellow: #d97706;
      --accent-red: #ef4444;
      --accent-purple: #9333ea;
      --badge-bg: rgba(0,0,0,0.05);
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: 'Inter', system-ui, sans-serif;
      background-color: var(--bg-primary);
      color: var(--text-primary);
      transition: background-color 0.3s, color 0.3s;
      min-height: 100vh;
      padding: 2rem;
    }}

    .container {{
      max-width: 1200px;
      margin: 0 auto;
    }}

    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 2rem;
    }}

    .title-group h1 {{
      font-family: 'Outfit', sans-serif;
      font-size: 1.8rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}

    .title-group p {{
      color: var(--text-secondary);
      font-size: 0.9rem;
      margin-top: 0.25rem;
    }}

    .theme-toggle {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      color: var(--text-primary);
      padding: 0.6rem 1.2rem;
      border-radius: 9999px;
      cursor: pointer;
      font-weight: 500;
      font-size: 0.85rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      transition: all 0.2s ease;
    }}

    .theme-toggle:hover {{
      background: var(--bg-surface-hover);
    }}

    /* Stats Grid */
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-bottom: 2rem;
    }}

    .metric-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 1.25rem;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}

    .metric-card .label {{
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-secondary);
      font-weight: 600;
    }}

    .metric-card .value {{
      font-family: 'Outfit', sans-serif;
      font-size: 2rem;
      font-weight: 700;
      margin-top: 0.5rem;
    }}

    .val-total {{ color: var(--text-primary); }}
    .val-waiting {{ color: var(--accent-yellow); }}
    .val-executing {{ color: var(--accent-blue); }}
    .val-completed {{ color: var(--accent-green); }}
    .val-failed {{ color: var(--accent-red); }}

    /* Controls & Filters */
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.5rem;
    }}

    .search-box input {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      color: var(--text-primary);
      padding: 0.6rem 1rem;
      border-radius: 8px;
      font-size: 0.9rem;
      width: 280px;
      outline: none;
    }}

    .search-box input:focus {{
      border-color: var(--accent-blue);
    }}

    .filter-tabs {{
      display: flex;
      gap: 0.5rem;
      background: var(--bg-surface);
      padding: 0.25rem;
      border-radius: 8px;
      border: 1px solid var(--border-color);
    }}

    .tab-btn {{
      background: transparent;
      border: none;
      color: var(--text-secondary);
      padding: 0.4rem 0.9rem;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 500;
      transition: all 0.2s;
    }}

    .tab-btn.active {{
      background: var(--bg-primary);
      color: var(--text-primary);
      font-weight: 600;
    }}

    /* Table Formatting Rules */
    .table-container {{
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      overflow-x: auto;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.9rem;
    }}

    th, td {{
      padding: 1rem 1.25rem;
      border-bottom: 1px solid var(--border-color);
    }}

    th {{
      background: var(--bg-surface-hover);
      color: var(--text-secondary);
      font-weight: 600;
      text-transform: uppercase;
      font-size: 0.75rem;
      letter-spacing: 0.05em;
    }}

    /* Workspace Rule: First Column No Wrap */
    th:first-child, td:first-child {{
      white-space: nowrap;
    }}
    td:first-child code {{
      white-space: nowrap !important;
      word-break: normal !important;
    }}

    tr:last-child td {{
      border-bottom: none;
    }}

    tr:hover {{
      background: var(--bg-surface-hover);
    }}

    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.25rem 0.65rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }}

    .status-WAITING_IMPLEMENTATION {{ background: rgba(251, 191, 36, 0.15); color: var(--accent-yellow); }}
    .status-EXECUTING {{ background: rgba(56, 189, 248, 0.15); color: var(--accent-blue); }}
    .status-COMPLETED {{ background: rgba(52, 211, 153, 0.15); color: var(--accent-green); }}
    .status-FAILED, .status-CANCELLED {{ background: rgba(248, 113, 113, 0.15); color: var(--accent-red); }}

    .mode-badge {{
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-size: 0.75rem;
      font-family: monospace;
      background: var(--badge-bg);
      color: var(--text-secondary);
    }}

    .code-id {{
      font-family: monospace;
      font-weight: 600;
      color: var(--accent-purple);
    }}

    .runtime-info {{
      font-size: 0.8rem;
      color: var(--text-secondary);
      font-family: monospace;
    }}

    .empty-state {{
      text-align: center;
      padding: 3rem;
      color: var(--text-secondary);
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>🚀 Prompt Registry Portal</h1>
        <p>Active project prompts, background executions, and implementation statuses</p>
      </div>
      <button class="theme-toggle" id="themeToggleBtn" onclick="toggleTheme()">
        <span id="themeIcon">☀️</span>
        <span id="themeLabel">Light Mode</span>
      </button>
    </header>

    <div class="metrics-grid">
      <div class="metric-card">
        <div class="label">Total Prompts</div>
        <div class="value val-total">{total}</div>
      </div>
      <div class="metric-card">
        <div class="label">Waiting Implementation</div>
        <div class="value val-waiting">{waiting}</div>
      </div>
      <div class="metric-card">
        <div class="label">Executing</div>
        <div class="value val-executing">{executing}</div>
      </div>
      <div class="metric-card">
        <div class="label">Completed</div>
        <div class="value val-completed">{completed}</div>
      </div>
      <div class="metric-card">
        <div class="label">Failed / Cancelled</div>
        <div class="value val-failed">{failed}</div>
      </div>
    </div>

    <div class="controls">
      <div class="search-box">
        <input type="text" id="searchInput" placeholder="Search prompt ID, title, tags..." oninput="renderTable()">
      </div>
      <div class="filter-tabs">
        <button class="tab-btn active" onclick="setFilter('ALL', this)">All</button>
        <button class="tab-btn" onclick="setFilter('WAITING_IMPLEMENTATION', this)">Waiting</button>
        <button class="tab-btn" onclick="setFilter('EXECUTING', this)">Executing</button>
        <button class="tab-btn" onclick="setFilter('COMPLETED', this)">Completed</button>
        <button class="tab-btn" onclick="setFilter('FAILED', this)">Failed</button>
      </div>
    </div>

    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Prompt ID</th>
            <th>Title</th>
            <th>Mode</th>
            <th>Status</th>
            <th>Runtime / Subagent</th>
            <th>Last Updated</th>
          </tr>
        </thead>
        <tbody id="promptTableBody">
          <!-- Dynamically populated -->
        </tbody>
      </table>
    </div>
  </div>

  <script>
    const promptsData = {prompts_json};
    let currentFilter = 'ALL';

    function initTheme() {{
      const savedTheme = localStorage.getItem('prompt_dashboard_theme') || 'dark';
      document.documentElement.setAttribute('data-theme', savedTheme);
      updateThemeButton(savedTheme);
    }}

    function toggleTheme() {{
      const currentTheme = document.documentElement.getAttribute('data-theme');
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('prompt_dashboard_theme', newTheme);
      updateThemeButton(newTheme);
    }}

    function updateThemeButton(theme) {{
      const icon = document.getElementById('themeIcon');
      const label = document.getElementById('themeLabel');
      if (theme === 'dark') {{
        icon.textContent = '☀️';
        label.textContent = 'Light Mode';
      }} else {{
        icon.textContent = '🌙';
        label.textContent = 'Dark Mode';
      }}
    }}

    function setFilter(status, btn) {{
      currentFilter = status;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderTable();
    }}

    function renderTable() {{
      const query = document.getElementById('searchInput').value.toLowerCase();
      const tbody = document.getElementById('promptTableBody');
      tbody.innerHTML = '';

      const filtered = promptsData.filter(p => {{
        const matchesFilter = (currentFilter === 'ALL') || 
                              (currentFilter === 'FAILED' && (p.status === 'FAILED' || p.status === 'CANCELLED')) ||
                              (p.status === currentFilter);
        const matchesQuery = p.id.toLowerCase().includes(query) ||
                             p.title.toLowerCase().includes(query) ||
                             (p.tags && p.tags.some(t => t.toLowerCase().includes(query)));
        return matchesFilter && matchesQuery;
      }});

      if (filtered.length === 0) {{
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No matching prompts found</td></tr>`;
        return;
      }}

      filtered.forEach(p => {{
        const tr = document.createElement('tr');
        
        let runtimeText = '-';
        if (p.execution_runtime) {{
          const rt = p.execution_runtime;
          if (rt.conversation_id) {{
            runtimeText = `<span class="runtime-info">conv: ${{rt.conversation_id.substring(0, 12)}}...</span>`;
          }} else if (rt.task_id) {{
            runtimeText = `<span class="runtime-info">task: ${{rt.task_id}}</span>`;
          }}
        }}

        const updatedDate = new Date(p.updated_at).toLocaleString();

        tr.innerHTML = `
          <td><code class="code-id">${{p.id}}</code></td>
          <td><strong>${{p.title}}</strong></td>
          <td><span class="mode-badge">${{p.mode || 'interactive'}}</span></td>
          <td><span class="status-badge status-${{p.status}}">${{p.status.replace('_', ' ')}}</span></td>
          <td>${{runtimeText}}</td>
          <td style="color: var(--text-secondary); font-size: 0.85rem;">${{updatedDate}}</td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    document.addEventListener('DOMContentLoaded', () => {{
      initTheme();
      renderTable();
    }});
  </script>
</body>
</html>
"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return out_path


def main():
    parser = argparse.ArgumentParser(description="Antigravity Prompt Registry Manager")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # Command: list
    list_parser = subparsers.add_parser("list", help="List registered prompts")
    list_parser.add_argument("--status", help="Filter by status (WAITING_IMPLEMENTATION, EXECUTING, COMPLETED, FAILED)")
    list_parser.add_argument("--active", action="store_true", help="List only active executing prompts")

    # Command: show
    show_parser = subparsers.add_parser("show", help="Show details of a specific prompt")
    show_parser.add_argument("prompt_id", help="Prompt Short ID (e.g., PRMT-8F21)")

    # Command: register
    reg_parser = subparsers.add_parser("register", help="Register or update a prompt entry")
    reg_parser.add_argument("prompt_id", help="Prompt Short ID")
    reg_parser.add_argument("--title", help="Prompt title/summary")
    reg_parser.add_argument("--mode", default="interactive", choices=["interactive", "autonomous"])
    reg_parser.add_argument("--status", default="WAITING_IMPLEMENTATION")
    reg_parser.add_argument("--parent-id", help="Parent prompt ID if revision")

    # Command: set-status
    status_parser = subparsers.add_parser("set-status", help="Set status of a prompt")
    status_parser.add_argument("prompt_id", help="Prompt Short ID")
    status_parser.add_argument("status", help="New status")
    status_parser.add_argument("--conv-id", help="Subagent Conversation ID")
    status_parser.add_argument("--task-id", help="Background Task ID")
    status_parser.add_argument("--log-file", help="Path to execution log file")

    # Command: sync
    subparsers.add_parser("sync", help="Auto-sync prompt statuses with disk artifacts and background subagent logs")

    # Command: dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Generate interactive HTML dashboard")
    dash_parser.add_argument("--output", help="Custom HTML output path")

    args = parser.parse_args()

    if not args.command or args.command == "list":
        registry, _ = auto_sync_registry()
        raw_prompts = registry.get("prompts", [])
        prompts = list(raw_prompts.values()) if isinstance(raw_prompts, dict) else raw_prompts
        status_filter = getattr(args, "status", None)
        active_only = getattr(args, "active", False)

        if active_only:
            prompts = [p for p in prompts if p.get("status") == "EXECUTING"]
        elif status_filter:
            prompts = [p for p in prompts if p.get("status") == status_filter.upper()]

        print(f"\n📋 Prompt Registry Index ({len(prompts)} entry/entries):\n")
        print(f"{'ID':<12} | {'MODE':<12} | {'STATUS':<22} | {'TITLE'}")
        print("-" * 75)
        for p in prompts:
            title = p.get('title', '')
            if len(title) > 35:
                title = title[:32] + "..."
            mode_str = p.get('execution', {}).get('mode') if isinstance(p.get('execution'), dict) else p.get('mode', 'interactive')
            print(f"{p['id']:<12} | {mode_str:<12} | {p.get('status', 'DRAFT'):<22} | {title}")
        print()

    elif args.command == "show":
        registry, _ = auto_sync_registry()
        raw_prompts = registry.get("prompts", [])
        prompts_list = list(raw_prompts.values()) if isinstance(raw_prompts, dict) else raw_prompts
        prompt = next((p for p in prompts_list if p.get("id") == args.prompt_id), None)
        if not prompt:
            print(f"❌ Prompt '{args.prompt_id}' not found in registry.")
            sys.exit(1)
        print(json.dumps(prompt, indent=2, ensure_ascii=False))

    elif args.command == "register":
        entry = register_prompt(
            prompt_id=args.prompt_id,
            title=args.title,
            mode=args.mode,
            status=args.status,
            parent_id=args.parent_id
        )
        print(f"✅ Registered prompt {entry['id']} with status {entry['status']}")

    elif args.command == "set-status":
        entry = set_status(
            prompt_id=args.prompt_id,
            status=args.status,
            conversation_id=args.conv_id,
            task_id=args.task_id,
            log_file=args.log_file
        )
        print(f"✅ Updated prompt {entry['id']} status to {entry['status']}")

    elif args.command == "sync":
        registry, count = auto_sync_registry()
        print(f"🔄 Auto-sync complete. {count} prompt status(es) updated.")

    elif args.command == "dashboard":
        out_path = generate_html_dashboard(output_path=getattr(args, "output", None))
        print(f"📊 Dashboard generated at: file://{os.path.abspath(out_path)}")


if __name__ == "__main__":
    main()
