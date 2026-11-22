---
description: Trace one requirement forward (plan, model, code, tests, results, tasks) or one source location back to the requirements it serves.
scripts:
  sh: scripts/bash/verify-trace.sh --query
  ps: scripts/powershell/verify-trace.ps1 -Query
  py: scripts/python/verify_trace.py --query
---

## User Input

```text
$ARGUMENTS
```

## Outline

1. Take the requirement (`REQ-001` or `<feature>/REQ-001`) or the location (`path/file.c:120`) from the user input.
2. Execute `{SCRIPT} "<that term>"` from the repository root and show its output unchanged, then a one-line reading of it (which layers are present, which are missing).
