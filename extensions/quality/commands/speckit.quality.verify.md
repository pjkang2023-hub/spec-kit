---
description: Run deterministic compiler, linter, test/sanitizer, and zero-stub verification gates and persist .specify/quality/latest-verify.json.
scripts:
  sh: scripts/bash/verify-quality.sh --json --soft-exit
  ps: scripts/powershell/verify-quality.ps1 -Json -SoftExit
  py: scripts/python/verify_quality.py --json --soft-exit
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

1. Execute `{SCRIPT}` from the repository root and parse its JSON output (`passed`, `stacks`, `checks`, `stub_violations`, `summary`). Note that `{SCRIPT}` also writes `.specify/quality/latest-verify.json`.
2. Present a concise Markdown table summarizing:
   - Detected stack(s) (`stacks`)
   - Every check (`name`, `command`, `passed`, `exit_code`, `duration_ms`)
   - Any production stub violations (`file`, `line`, `marker`, `text`)
3. **Read-Only Assessment**:
   - Do **not** edit source files inside this verification command.
   - If `passed` is `true`, state clearly: `QUALITY_VERIFY: PASSED`.
   - If `passed` is `false`, list the exact compiler errors, failing tests, or stub locations from `output_excerpt` / `stub_violations` and state clearly: `QUALITY_VERIFY: FAILED` so `__SPECKIT_COMMAND_IMPLEMENT__` or `__SPECKIT_COMMAND_CONVERGE__` can remediate them.
