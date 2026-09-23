# Selective RAG Context Grounding via OKF Index

To prevent prompt-token bloat and ensure fast execution, the Open Knowledge Format (OKF) implements **Selective Context Grounding (On-Demand RAG)**.

---

## 1. The Selective Hydration Lifecycle

Instead of ingesting an entire knowledge bundle into agent memory, agents traverse a lightweight progressive disclosure index:

```
+---------------------------------------------------------------------------------+
|                        SELECTIVE RAG HYDRATION FLOW                             |
+---------------------------------------------------------------------------------+
|                                                                                 |
|  1. Index Inspection: Read `index.md` (high-level map + concept lookup matrix)  |
|  2. Target Slicing: Identify matching Concept IDs needed for current task node  |
|  3. On-Demand View: Ingest only target concept files via `view_file`            |
|  4. Resource Drill-Down: Inspect underlying code via `resource:` target         |
|  5. Promotion & Sync: Author/update concept docs and index upon milestone PASS  |
|                                                                                 |
+---------------------------------------------------------------------------------+
```

---

## 2. Bidirectional Audit Flow

Knowledge bases decay when index pointers break or newly authored documents are omitted from the index. OKF enforces a **Bidirectional Audit Flow** via `verify_okf.py --all`:

```
               +-------------------------------------------+
               |          Progressive Index (index.md)     |
               +-------------------------------------------+
                       |                           ^
         Forward Check |                           | Backward Check
       (Dead Link Scan)|                           | (Orphan Concept Scan)
                       v                           |
         +-----------------------------+     +-----------------------------+
         | Every link in index.md      |     | Every concept on disk       |
         | MUST resolve to a real file |     | MUST be linked in index.md  |
         +-----------------------------+     +-----------------------------+
                       \                           /
                        v                         v
               +-------------------------------------------+
               |     Disk Storage (.gemini/knowledge/)     |
               +-------------------------------------------+
                                     |
                                     | Code Grounding & Drift
                                     v
                       +---------------------------+
                       | Underlying Source Files   |
                       | (resource + SHA-256 hash) |
                       +---------------------------+
```

### 1. Forward Verification: Dead Link Detection
- Traverses all Markdown links and table pointers in `index.md`.
- Normalizes paths relative to the knowledge bundle root.
- Fails if any referenced document does not exist on disk (prevents 404 navigation errors during agent runs).

### 2. Backward Verification: Orphaned Concept Detection
- Recursively discovers all `.md` files across bundle subdirectories (`scout/`, `analyst/`, `architecture/`, `builder/`, `sentry/`).
- Excludes bundle metadata files (`index.md`, `log.md`).
- Fails if any concept document is missing from `index.md` (prevents "dark knowledge" invisible to selective RAG).

### 3. Resource Grounding & Drift Tracking
- Validates that `resource:` pointers resolve to existing codebase files.
- Computes SHA-256 checksums to flag code drift when source implementations evolve independently of concept documentation (`scaffold_okf.py --check-drift`).

---

## 3. Cross-Harness Mapping & Portability

OKF bundles are designed for complete cross-platform portability across major agent harnesses without modifying links:

| Agent Harness | Default Knowledge Root | Primary Role |
| :--- | :--- | :--- |
| **Antigravity / Gemini CLI** | `.gemini/knowledge/` | Google Antigravity & Gemini workflows (default) |
| **Agent Skill Forge / Swarms** | `.agents/knowledge/` | Universal vendor-agnostic multi-agent orchestration |
| **Anthropic Claude Code** | `.claude/knowledge/` | Claude Code project memory |

### Portability Principles
1. **Universal Workspace-Relative Paths**:
   - Never use host-specific absolute paths (e.g. `file:///Users/username/...` or `C:\Users\...`). <!-- host-path-ok -->
   - Use paths relative to the knowledge root (e.g. `scout/codebase_map.md`, `architecture/data_contracts.md`).
2. **Deterministic Root Discovery**:
   - The verifier and scaffolder resolve targets in candidate priority: `--dir <explicit_path>` -> `.gemini/knowledge/` -> `.agents/knowledge/` -> `.claude/knowledge/`.
3. **Symlink Synchronization**:
   - In heterogeneous environments running multiple agent CLIs concurrently, directory junctions (Windows) or symlinks (POSIX) link `.agents/knowledge/` and `.claude/knowledge/` to `.gemini/knowledge/`, ensuring single-source-of-truth knowledge updates.

---

## 4. Verification Protocol & CLI Reference

```bash
# Verify a single concept document
python3.12 skills/catalog/scripts/verify_okf.py .gemini/knowledge/scout/codebase_map.md

# Run full bidirectional audit across default bundle (.gemini/knowledge/)
python3.12 skills/catalog/scripts/verify_okf.py --all

# Run bidirectional audit on a custom harness directory
python3.12 skills/catalog/scripts/verify_okf.py --all --dir .agents/knowledge/

# Check source code drift against embedded SHA-256 hashes
python3.12 skills/catalog/scripts/scaffold_okf.py --check-drift
```
