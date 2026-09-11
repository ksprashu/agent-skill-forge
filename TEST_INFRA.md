# Markdown DAG Workflow Engine: End-to-End Test Infrastructure Specification (`TEST_INFRA.md`)

## 1. Executive Summary & Purpose

This document establishes the authoritative End-to-End (E2E) test infrastructure, validation methodology, and verification matrix for the **Markdown-driven Directed Acyclic Graph (DAG) Workflow Engine and Harness Protocol** in `agent-skill-forge`.

The E2E test suite operates as an **opaque-box, requirement-driven verification harness**. It exercises the public CLI and interface contracts of the DAG workflow engine (`skills/work/scripts/dag_validator.py`) without coupling to internal private abstractions, ensuring that any compliant implementation of the specification behaves identically across Windows and POSIX environments under `python3.12`.

---

## 2. System Architecture & Testing Boundaries

### 2.1 Component Under Test
The primary system under test is the DAG engine CLI and harness utility:
```bash
python3.12 skills/work/scripts/dag_validator.py <markdown_file> [options]
```

### 2.2 CLI Interface Contract
| CLI Option | Description | Target Behavior |
|---|---|---|
| `<file>` | Positional path to Markdown DAG specification file | Parses task table, verifies acyclicity, returns status |
| `--stdin` | Read Markdown content directly from standard input | Supports piped workflows and dynamic validation |
| `--check-artifacts` | Verify physical on-disk file existence for inputs/outputs | Gates status checks against filesystem truth |
| `--base-dir <dir>` | Base directory for relative artifact paths (default: `.`) | Ensures workspace-relative path portability |
| `--mermaid` | Print regenerated Mermaid diagram to stdout | Validates graph TD flowchart syntax |
| `--update-file` | In-place file update for Markdown table and Mermaid block | Atomically syncs file with new statuses and diagram |
| `--set-status <id>=<status>` | Update status of specific task node(s) | Transitions `PENDING` -> `RUNNING` -> `PASSED` etc. |
| `--ready-frontier` | Output list of unblocked tasks ready for dispatch | Returns immediate parallel execution wave |
| `--json` | Output structured validation report as JSON payload | Enables programmatic inspection by orchestrators |
| `--quiet`, `-q` | Suppress human prose, rely strictly on exit code | Used for scripting and CI gates |

### 2.3 Exit Code Contract
- **`0`**: Valid DAG. Graph is acyclic, all dependencies exist, artifact paths are well-formed, and physical artifacts exist (if `--check-artifacts` is set).
- **`1`**: Validation Failure. Cycle detected, missing dependency target, duplicate task ID, illegal path characters, or missing physical artifact file.
- **`2`**: Invocation Error. File not found, invalid CLI argument syntax, unreadable file, or unparseable input.

### 2.4 JSON Schema Contract
When invoked with `--json`, the engine emits a JSON document matching this schema:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "valid": { "type": "boolean" },
    "tasks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string" },
          "title": { "type": "string" },
          "mode": { "type": "string", "enum": ["series", "parallel", "async_background"] },
          "depends_on": { "type": "array", "items": { "type": "string" } },
          "inputs": { "type": "array", "items": { "type": "string" } },
          "outputs": { "type": "array", "items": { "type": "string" } },
          "gate": { "type": "string" },
          "status": { "type": "string", "enum": ["PENDING", "RUNNING", "PASSED", "BLOCKED", "FAILED"] }
        },
        "required": ["id", "mode", "depends_on", "status"]
      }
    },
    "topological_order": { "type": "array", "items": { "type": "string" } },
    "cycle": { "type": ["array", "null"], "items": { "type": "string" } },
    "errors": { "type": "array", "items": { "type": "string" } },
    "ready_frontier": { "type": "array", "items": { "type": "string" } },
    "mermaid": { "type": "string" }
  },
  "required": ["valid", "tasks", "ready_frontier"]
}
```

---

## 3. Systematic 4-Tier Testing Methodology

The E2E test suite is organized into four hierarchical verification tiers, providing comprehensive coverage from individual features to complex multi-agent workflows.

```
┌────────────────────────────────────────────────────────────────────────┐
│               TIER 4: Real-World Workload Scenarios                     │
│  • Focused Bugfix Swarm Full Lifecycle Simulation                      │
│  • Multi-Milestone Swarm with Tournament Branching Simulation          │
├────────────────────────────────────────────────────────────────────────┤
│               TIER 3: Cross-Feature Combinations                       │
│  • Pairwise: Concurrent Parallel Tasks with Shared Inputs              │
│  • Pairwise: async_background Watchdogs with Barrier Gates             │
│  • Pairwise: In-Place Status Updates with Dynamic Node Mutations       │
│  • Pairwise: Ready Frontier Resolution with Physical Artifact Check    │
├────────────────────────────────────────────────────────────────────────┤
│               TIER 2: Boundary & Corner Cases                          │
│  • Empty DAGs, Head-Only Tables, Single-Task DAGs, Disconnected DAGs   │
│  • Cycles of Lengths 1, 2, 3, and 5+ with Exact Path Tracing           │
│  • Missing Targets, Duplicate IDs, Windows/POSIX Path Separators        │
│  • Unicode, Emoji, CRLF vs LF, Escaped Markdown Table Pipes            │
├────────────────────────────────────────────────────────────────────────┤
│               TIER 1: Feature Coverage (>=5 tests per feature)         │
│  • Feature 1: Markdown Task Table Parsing (5 tests)                    │
│  • Feature 2: Task Execution Modes (5 tests)                           │
│  • Feature 3: Dependency Ordering & Topological Sorting (5 tests)      │
│  • Feature 4: Artifact Contracts & Physical Validation (5 tests)       │
│  • Feature 5: Mermaid Visualization & In-Place Updates (5 tests)       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Test Catalog & Detailed Test Matrix

### Tier 1: Feature Coverage (25 Tests)

#### Feature 1: Markdown Task Table Parsing
| Test ID | Method Name | Input Description | Authoritative Expected Behavior |
|---|---|---|---|
| `T1.1.1` | `test_parse_canonical_8col_table` | GFM table with columns: ID, Task Name, Mode, Depends On, Inputs, Outputs, Gate, Status | Parses all 8 columns into structured TaskNode objects with clean attributes. |
| `T1.1.2` | `test_parse_flexible_column_order` | Markdown table where `Mode` precedes `Task Name` and `Gate` precedes `Outputs` | Dynamically maps column headers regardless of column order; nodes parsed correctly. |
| `T1.1.3` | `test_parse_empty_token_normalization` | Cells containing `none`, `-`, `[]`, `n/a`, or whitespace | Normalizes empty indicators to empty lists `[]` or default `"none"`. |
| `T1.1.4` | `test_parse_comma_separated_lists` | `Depends On: task_01, task_02` and `Inputs: path/a.txt, path/b.txt` | Correctly tokenizes multiple dependencies and file paths, stripping whitespace and backticks. |
| `T1.1.5` | `test_parse_ragged_whitespace_alignment` | Unaligned pipes, variable column padding, and extra divider rows | Tolerates ragged whitespace without corrupting cell content or missing rows. |

#### Feature 2: Task Execution Modes
| Test ID | Method Name | Input Description | Authoritative Expected Behavior |
|---|---|---|---|
| `T1.2.1` | `test_mode_series_enforcement` | Linear pipeline with `mode: series` | Nodes marked `series` block downstream tasks until their status is `PASSED`. |
| `T1.2.2` | `test_mode_parallel_concurrency` | Multiple sibling tasks with `mode: parallel` depending on same root | Sibling tasks enter `ready_frontier` simultaneously once parent is `PASSED`. |
| `T1.2.3` | `test_mode_async_background_nonblocking` | Background watchdog with `mode: async_background` | Watchdog does not block downstream milestone progression; runs independently. |
| `T1.2.4` | `test_mode_mixed_heterogeneous_dag` | Graph with combination of `series`, `parallel`, and `async_background` | Each node respects its respective mode semantics during frontier calculation. |
| `T1.2.5` | `test_mode_case_insensitive_normalization` | Modes specified as `SERIES`, `Parallel`, `Async_Background` | Normalizes to canonical lowercase (`series`, `parallel`, `async_background`). |

#### Feature 3: Dependency Ordering & Topological Sorting
| Test ID | Method Name | Input Description | Authoritative Expected Behavior |
|---|---|---|---|
| `T1.3.1` | `test_order_linear_pipeline` | Three tasks: `T1 -> T2 -> T3` | `topological_order` is exactly `["T1", "T2", "T3"]`. |
| `T1.3.2` | `test_order_diamond_concurrency` | Diamond: `T1 -> [T2, T3] -> T4` | `T1` first, `T4` last, `T2` and `T3` between them; valid topological sequence. |
| `T1.3.3` | `test_order_multi_parent_join` | Multi-parent convergence: `[T1, T2, T3] -> T4` | All three parents precede `T4` in topological order. |
| `T1.3.4` | `test_order_multi_root_fork` | Two roots `T1` and `T2` branching into separate downstream subgraphs | Both roots have in-degree 0; all dependencies topologically satisfied. |
| `T1.3.5` | `test_order_transitive_invariance` | Deep graph with transitive relations (`A -> B -> C -> D` and `A -> D`) | Topological order satisfies all direct and transitive dependency constraints. |

#### Feature 4: Artifact Contracts & Physical Validation
| Test ID | Method Name | Input Description | Authoritative Expected Behavior |
|---|---|---|---|
| `T1.4.1` | `test_artifact_relative_paths_accepted` | Inputs/Outputs with relative paths (`src/auth.py`, `.agents/handoff.md`) | Accepted as valid workspace-relative artifact paths. |
| `T1.4.2` | `test_artifact_virtual_tokens_recognized` | Virtual tokens (`none`, `-`, `stdout`, `git:branch`) | Recognized as non-filesystem virtual targets; no filesystem check performed. |
| `T1.4.3` | `test_check_artifacts_passed_files_exist` | `--check-artifacts` when all declared output files physically exist on disk | Returns exit code 0; `valid: true`. |
| `T1.4.4` | `test_check_artifacts_missing_input_fails` | `--check-artifacts` when declared input for `RUNNING` node does not exist | Returns exit code 1; reports `MISSING_INPUT_ARTIFACT`. |
| `T1.4.5` | `test_check_artifacts_missing_output_fails` | `--check-artifacts` when declared output for `PASSED` node does not exist | Returns exit code 1; reports `MISSING_OUTPUT_ARTIFACT`. |

#### Feature 5: Mermaid Visualization & In-Place Updates
| Test ID | Method Name | Input Description | Authoritative Expected Behavior |
|---|---|---|---|
| `T1.5.1` | `test_mermaid_graph_td_header` | CLI invocation with `--mermaid` | Outputs valid Mermaid diagram starting with `graph TD`. |
| `T1.5.2` | `test_mermaid_nodes_and_edges_present` | Graph with nodes and directed dependencies | Output contains all node definitions and directed edges (`-->`). |
| `T1.5.3` | `test_mermaid_status_css_classes` | Graph with nodes in various statuses | Includes CSS class definitions (`classDef passed`, `classDef running`, etc.) and bindings. |
| `T1.5.4` | `test_update_file_replaces_existing_mermaid` | File already containing ```` ```mermaid ... ``` ```` block | `--update-file` replaces interior lines of existing block without duplicating. |
| `T1.5.5` | `test_update_file_appends_missing_mermaid` | File with task table but NO existing Mermaid block | `--update-file` appends generated Mermaid block immediately following table. |

---

### Tier 2: Boundary & Corner Cases (30 Tests)

#### Category 1: Empty & Minimal Graphs
| Test ID | Method Name | Input Description | Authoritative Expected Behavior |
|---|---|---|---|
| `T2.1.1` | `test_boundary_empty_file` | Empty 0-byte Markdown file | Returns exit code 1 or 2; reports no task graph found. |
| `T2.1.2` | `test_boundary_no_table_prose_only` | Markdown file with narrative headers and prose, zero tables | Returns exit code 1 or 2; reports missing task table. |
| `T2.1.3` | `test_boundary_header_only_table` | Table with header and divider rows, zero data rows | Returns exit code 1 or 2; reports empty task list. |
| `T2.1.4` | `test_boundary_single_isolated_task` | Table with exactly 1 task with `depends_on: none` | Returns exit code 0; `topological_order: ["T1"]`; `ready_frontier: ["T1"]`. |
| `T2.1.5` | `test_boundary_all_independent_tasks` | Table with 5 disconnected tasks, all with `depends_on: none` | Returns exit code 0; all 5 tasks included in `ready_frontier`. |

#### Category 2: Cycle Detection of Various Lengths
| Test ID | Method Name | Input Description | Authoritative Expected Behavior |
|---|---|---|---|
| `T2.2.1` | `test_cycle_length_1_self_reference` | Task `T1` depends on `T1` | Returns exit code 1; reports cycle `T1 -> T1`. |
| `T2.2.2` | `test_cycle_length_2_direct` | `T1 -> T2` and `T2 -> T1` | Returns exit code 1; reports cycle `T1 -> T2 -> T1`. |
| `T2.2.3` | `test_cycle_length_3_indirect` | `T1 -> T2 -> T3 -> T1` | Returns exit code 1; reports cycle path through all 3 nodes. |
| `T2.2.4` | `test_cycle_length_5_deep` | `T1 -> T2 -> T3 -> T4 -> T5 -> T2` | Returns exit code 1; identifies back-edge into `T2`. |
| `T2.2.5` | `test_cycle_disconnected_subgraph` | Main component acyclic (`A -> B`), side component cyclic (`X -> Y -> X`) | Returns exit code 1; detects cycle in disconnected subgraph. |

#### Category 3: Missing Targets & Duplicate IDs
| Test ID | Method Name | Input Description | Authoritative Expected Behavior |
|---|---|---|---|
| `T2.3.1` | `test_missing_dep_single_ghost` | `T1` depends on non-existent `task_ghost` | Returns exit code 1; reports `MISSING_DEPENDENCY: task_ghost`. |
| `T2.3.2` | `test_missing_dep_partial_valid` | `T2` depends on `[T1, task_nonexistent]` where `T1` exists | Returns exit code 1; specifies `task_nonexistent` as missing. |
| `T2.3.3` | `test_duplicate_task_id_rejected` | Two distinct table rows with identical ID `task_worker` | Returns exit code 1; reports `DUPLICATE_TASK_ID`. |
| `T2.3.4` | `test_missing_dep_multiple_ghosts` | Tasks depend on multiple undefined targets | Returns exit code 1; all missing targets identified in errors list. |
| `T2.3.5` | `test_empty_string_task_id_rejected` | Row with blank or whitespace-only task ID | Returns exit code 1; rejected as invalid task row. |

#### Category 4: Path Styles & Escaping
| Test ID | Method Name | Input Description | Authoritative Expected Behavior |
|---|---|---|---|
| `T2.4.1` | `test_path_windows_backslashes_handled` | Artifact paths using `src\\core\\engine.py` | Normalized cleanly without regex or escaping crashes. |
| `T2.4.2` | `test_path_posix_forward_slashes_handled` | Artifact paths using `src/core/engine.py` | Handled natively across both Windows and POSIX. |
| `T2.4.3` | `test_path_mixed_slashes_normalized` | Artifact paths with mixed separators `src/foo\\bar/baz.py` | Normalized consistently to standard path representation. |
| `T2.4.4` | `test_path_forbidden_characters_rejected` | Paths containing illegal characters (`<`, `>`, `"`, `|`, `?`, `*`) | Returns exit code 1; reports malformed/illegal path. |
| `T2.4.5` | `test_path_absolute_root_leaked_rejected` | Hardcoded machine root path (`C:\Users\...` or `/etc/...`) | Returns exit code 1; rejects absolute path outside workspace contract. |

#### Category 5: Unicode, Formatting & Adversarial Inputs
| Test ID | Method Name | Input Description | Authoritative Expected Behavior |
|---|---|---|---|
| `T2.5.1` | `test_unicode_titles_and_emoji` | Task title `🚀 Engine & ⚡ Performance`, Gate `✓ Passed` | UTF-8 preserved cleanly without cp1252 crash or character corruption. |
| `T2.5.2` | `test_brackets_and_quotes_in_titles` | Titles containing `[Admin] Service (V2) "Auth"` | Mermaid and table parsers escape quotes/brackets without breaking syntax. |
| `T2.5.3` | `test_escaped_pipes_in_table_cells` | Table cells containing `grep \| wc -l` | Escaped pipes `\|` treated as cell literals, not column delimiters. |
| `T2.5.4` | `test_crlf_and_lf_line_endings` | Files with Windows `\r\n` vs Unix `\n` line endings | Line endings normalized transparently; identical parsing behavior. |
| `T2.5.5` | `test_blank_lines_within_table` | Markdown tables with intervening blank lines or comments | Tolerated cleanly without prematurely truncating table parsing. |

#### Category 6: Mode Boundaries & Scaling
| Test ID | Method Name | Input Description | Authoritative Expected Behavior |
|---|---|---|---|
| `T2.6.1` | `test_invalid_execution_mode_rejected` | Row specifying `mode: hyper_concurrent` | Returns exit code 1; reports `INVALID_MODE`. |
| `T2.6.2` | `test_invalid_status_value_rejected` | Row specifying `status: HALFWAY_DONE` | Returns exit code 1; reports `INVALID_STATUS`. |
| `T2.6.3` | `test_status_case_insensitivity` | Mixed casing: `passed`, `Passed`, `RUNNING`, `Pending` | Normalized correctly to canonical uppercase statuses. |
| `T2.6.4` | `test_large_dag_scaling_100_nodes` | Synthetic DAG with 100 nodes in 10 sequential waves of 10 | Parses and topologically sorts in < 1.0 second. |
| `T2.6.5` | `test_deep_linear_chain_recursion_limit` | Linear chain of 150 tasks | Topological sort and cycle detector complete without stack overflow. |

---

### Tier 3: Cross-Feature Combinations (Pairwise Coverage, 12 Tests)

| Test ID | Method Name | Combination Pair | Authoritative Expected Behavior |
|---|---|---|---|
| `T3.1` | `test_combo_shared_inputs_parallel_frontier` | Concurrent parallel tasks sharing identical input files | When prerequisite passes and file exists, ALL parallel siblings enter ready frontier together. |
| `T3.2` | `test_combo_overlapping_input_subsets` | Sibling parallel tasks with overlapping but distinct input subsets | Tasks with satisfied inputs are ready; tasks with any missing input remain dormant. |
| `T3.3` | `test_combo_async_watchdog_alongside_series` | `async_background` watchdog running while series pipeline proceeds | Milestone barrier gate evaluates only series tasks; watchdog does not block milestone gate. |
| `T3.4` | `test_combo_async_watchdog_artifact_check` | `async_background` task with declared output file | `--check-artifacts` verifies background task's output file if status is `PASSED`. |
| `T3.5` | `test_combo_failure_propagation_to_blocked` | Upstream task marked `FAILED` while background watchdog runs | Downstream series tasks transition to `BLOCKED`; background watchdog status unaffected. |
| `T3.6` | `test_combo_inplace_status_update_mermaid_sync` | `--set-status T1=PASSED --update-file` | Updates both Markdown table cell AND Mermaid diagram CSS class atomically in-place. |
| `T3.7` | `test_combo_dynamic_remediation_node_injection` | Inserting remediation node `T_rem` between failed node and downstream gate | Recalculates topological order and Mermaid diagram; downstream waits for `T_rem`. |
| `T3.8` | `test_combo_ready_frontier_dynamic_evolution` | Inspecting `--ready-frontier` across sequential status updates | Frontier evolves dynamically: `[T1]` -> `[T2, T3]` -> `[T4]` as tasks complete. |
| `T3.9` | `test_combo_artifact_check_with_status_transitions` | Node marked `PASSED` tested before and after creating output file | Fails with exit code 1 when file absent; passes with exit code 0 once file created. |
| `T3.10` | `test_combo_ready_frontier_gated_by_physical_input` | Upstream task `PASSED` but required physical input file missing on disk | Node omitted from `--ready-frontier` until physical file is written (anti-polling invariant). |
| `T3.11` | `test_combo_stdin_cyclic_dag_json` | Piping cyclic DAG content via `--stdin` with `--json` | Returns exit code 1; JSON contains `valid: false`, `cycle: [...]`, and error message. |
| `T3.12` | `test_combo_stdin_valid_diamond_dag_json` | Piping diamond DAG content via `--stdin` with `--json` | Returns exit code 0; JSON contains `valid: true`, full `topological_order`, and `ready_frontier`. |

---

### Tier 4: Real-World Workload Scenarios (10 Tests)

#### Scenario A: Focused Bugfix Full Workflow Simulation (Topology 2)
Simulates the complete 6-turn lifecycle of a focused bugfix swarm:
- **Turn 1**: Initial State. Worker is `PENDING`, Reviewer/Challenger/Auditor are `BLOCKED`, Victory Auditor is `BLOCKED`.
  - `T4.1`: `test_scenario_focused_bugfix_initial_state`
- **Turn 2**: Worker Dispatched & Completed. Worker produces patch and handoff; status updated to `PASSED`.
  - `T4.2`: `test_scenario_focused_bugfix_worker_completion_unblocks_committee`
- **Turn 3**: Committee Parallel Execution. Reviewer, Challenger, and Auditor execute concurrently and complete.
  - `T4.3`: `test_scenario_focused_bugfix_committee_concurrency_unblocks_victory`
- **Turn 4**: Terminal Victory Audit. Victory Auditor validates clean-slate build and confirms victory.
  - `T4.4`: `test_scenario_focused_bugfix_victory_certification_terminates`
- **Turn 5**: Adversarial Rejection & Dynamic Remediation. Challenger rejects worker fix; dynamic remediation node injected.
  - `T4.5`: `test_scenario_focused_bugfix_remediation_branch_injection`

#### Scenario B: Multi-Milestone Swarm with Tournament Branching (Topology 1)
Simulates a multi-milestone platform engineering swarm:
- **Milestone 0 (Survey)**: 3 parallel explorers (`exp1`, `exp2`, `exp3`) unblock simultaneously at root.
  - `T4.6`: `test_scenario_swarm_m0_parallel_explorers`
- **Milestone 1 (Implementation + Committee)**: Core storage engine implementation unblocks adversarial committee.
  - `T4.7`: `test_scenario_swarm_m1_implementation_and_committee`
- **Milestone 2 (Competitive Tournament)**: Worker Alpha vs Worker Beta run in parallel branches from M1 committee.
  - `T4.8`: `test_scenario_swarm_m2_competitive_branching_tournament`
- **Milestone 2 Arbiter Synthesis**: Arbiter synthesizes candidate code, unblocks M2 committee and final victory.
  - `T4.9`: `test_scenario_swarm_m2_arbiter_synthesis_to_victory`
- **Full Lifecycle End-to-End Simulation**: Step-by-step state machine transition updating in-place Mermaid diagram at each stage.
  - `T4.10`: `test_scenario_swarm_full_lifecycle_simulation`

---

## 5. Test Fixtures Specifications

All fixtures reside in `tests/e2e/fixtures/`:
1. `focused_bugfix_dag.md`: Canonical Topology 2 (Worker -> [Reviewer, Challenger, Forensic] -> Victory).
2. `multi_milestone_swarm_dag.md`: Canonical Topology 1 (Explorers -> M1 -> Competitive M2 -> Arbiter -> Victory).
3. `diamond_dag.md`: Minimal 4-node diamond concurrency pattern.
4. `linear_dag.md`: Minimal 3-node sequential pipeline.
5. `cyclic_dag.md`: Canonical 3-node cycle (`A -> B -> C -> A`).
6. `async_watchdog_dag.md`: Mixed pipeline with continuous background watchdog.
7. `unicode_dag.md`: Non-ASCII characters, emoji, and escaped markdown formatting.
8. `missing_dep_dag.md`: Table with broken/ghost dependency references.
9. `duplicate_id_dag.md`: Table containing duplicate task IDs.
10. `empty_table_dag.md`: Table containing zero task rows.

---

## 6. Execution Command & Environment Requirements

### Command Line Invocation
Execute the complete E2E test suite using Python 3.12:
```bash
python3.12 tests/e2e/run_e2e_tests.py
```

### Targeted Tier Execution
```bash
# Run specific tier
python3.12 tests/e2e/run_e2e_tests.py --tier 1
python3.12 tests/e2e/run_e2e_tests.py --tier 2
python3.12 tests/e2e/run_e2e_tests.py --tier 3
python3.12 tests/e2e/run_e2e_tests.py --tier 4

# Structural verification mode (validates fixtures and test suite compilation)
python3.12 tests/e2e/run_e2e_tests.py --verify-fixtures
```

### Invariants & Requirements
1. **Python Binary**: Host executable is `python3.12` (`~/.local/bin/python3.12.exe`).
2. **Console Encoding**: Windows console defaults to cp1252; test runner wraps stdout/stderr with UTF-8 `TextIOWrapper`.
3. **Zero External Dependencies**: Test suite and runner rely strictly on Python standard libraries (`unittest`, `subprocess`, `tempfile`, `json`, `pathlib`, `os`, `sys`, `re`).
4. **Opaque-Box Testing**: All tests invoke `skills/work/scripts/dag_validator.py` via subprocess CLI calls or standard JSON/exit code contracts. No internal modules are imported or mocked.
