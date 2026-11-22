---
description: Build the deterministic two-way requirement trace (spec, plan, model, code, tests, results) and persist .specify/trace/latest-trace.json.
scripts:
  sh: scripts/bash/verify-trace.sh --json --soft-exit
  ps: scripts/powershell/verify-trace.ps1 -Json -SoftExit
  py: scripts/python/verify_trace.py --json --soft-exit
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

1. Execute `{SCRIPT}` from the repository root and parse its JSON output (`passed`, `summary`, `problems`, `warnings`, `dangling`, `untraced_files`). It also writes `.specify/trace/latest-trace.json` and `.specify/trace/trace-matrix.md`.
2. Present a concise summary: the counts in `summary`, then every entry of `problems`, then `dangling` references and `untraced_files`.
3. **Read-only**: do not edit sources, specs or tests in this command. The trace is computed, never asserted: do not claim a requirement is covered unless the report says so.
4. If `passed` is `true`, state `TRACE_VERIFY: PASSED`. Otherwise state `TRACE_VERIFY: FAILED` and, per problem, the concrete fix: add a plan matrix row, add an `@trace REQ-###` tag to the implementing code, add a test that names the requirement, or correct a reference to an unknown requirement.
