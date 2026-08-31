# ADR-001: Flat-File JSONL Storage for Session Memory Distillation

## Status
Accepted

## Date
2026-08-29

## Context
The `continuous-alignment` skill and its Antigravity `Stop` hooks must run synchronously across different developer environments with sub-second latency (< 200ms) without introducing external database daemons or platform-specific binary dependencies.

## Decision
We store extracted semantic memories in flat-file `.gemini/knowledge/memories.jsonl` and use Python standard library modules (`json`, `re`, `hashlib`, `tempfile`) for atomic updates and rule merging.

## Consequences
- Positive: Zero external dependencies; 100% portable across macOS, Linux, and Windows.
- Positive: Sub-100ms execution times inside synchronous Antigravity hooks.
- Positive: Native Git versioning and transparent diff visibility.
- Negative: Querying requires sequential JSONL scanning, which is completely negligible for single-repository project scopes (< 5,000 rules).
