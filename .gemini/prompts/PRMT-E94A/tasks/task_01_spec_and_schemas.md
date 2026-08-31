# Task 01: Design 4-Tier Memory Schema & Hook Protocol

## Objective
Define the schemas and formal specifications for extracted session memory, rule categorization, and hook payloads.

## Files to Create
- `skills/continuous-alignment/references/memory_schema.json`
- `skills/continuous-alignment/references/hook_protocol.md`

## Key Specifications
- Memory categories: `command`, `constraint`, `pattern`, `decision`.
- Hook protocol: Standard input parsing for `transcriptPath`, `workspacePaths`, `artifactDirectoryPath`.
- Rule uniqueness: SHA-256 hash or deterministic slug based on rule statement.
