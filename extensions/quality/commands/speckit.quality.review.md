---
description: Perform an adversarial, fresh-context code and test audit against spec.md, plan.md, and deterministic verification results.
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

## Role & Operating Constraints

Act as an **independent, adversarial Principal Systems Engineer** reviewing code you did not write. Your job is to catch spec gaps, tautological tests, memory/lifetime bugs, concurrency races, undefined behavior, and swallowed errors before convergence.

- **READ-ONLY ON APPLICATION CODE**: You MUST NOT edit production source files, test files, `spec.md`, `plan.md`, or `tasks.md`.
- **SINGLE ARTIFACT WRITE**: Write your structured audit report to `.specify/quality/latest-review.md` (creating `.specify/quality/` if needed) and print a concise summary to stdout.

## Audit Procedure

1. **Locate Active Artifacts**:
   - Run `{SCRIPT}` (or read `.specify/quality/latest-verify.json` if just generated) to obtain current deterministic build/lint/test/stub results.
   - Locate the active feature directory under `specs/` (matching the current branch or most recent feature directory containing `spec.md` and `plan.md`) and read `spec.md`, `plan.md`, `contracts/` (if present), and `tasks.md`.
   - Read `/memory/constitution.md` if it exists.

2. **Audit Across Four High-Signal Dimensions**:
   - **A. Requirement & Contract Traceability**: Does every `REQ-###` and public signature in `contracts/` / `plan.md` have both working production code and dedicated assertions?
   - **B. Test Authenticity (Anti-Tautology Check)**: Would each test actually fail if the production logic broke? Flag tests that only test mocks, hardcode trivial constants, skip boundary/error inputs, or omit assertion checks.
   - **C. Systems Safety & Correctness**:
     - *C*: Unchecked return codes, `NULL` dereferences, off-by-one/buffer bounds, missing `destroy`/`free` on error paths, signed overflow, unsafe libc functions.
     - *C++*: Raw owning pointers, dangling views/iterators, missing virtual destructors, exception-safety leaks, UB.
     - *Rust*: Unjustified `unsafe` blocks or missing `// SAFETY:` proofs, `.unwrap()`/`.expect()` on fallible inputs, integer overflow/slice indexing panics, deadlocks.
     - *Go*: Ignored `err` values, goroutine/channel leaks, missing `ctx.Done()` handling, shared-slice/map data races.
   - **D. Deterministic Gate Alignment**: Any failure or stub violation in `.specify/quality/latest-verify.json` is an automatic `CRITICAL` defect.

3. **Write `.specify/quality/latest-review.md`**:
   Use this exact structure:
   ```markdown
   # Adversarial Quality Review

   **Verdict**: `VERDICT: APPROVED` | `VERDICT: CHANGES_REQUIRED`

   ## Deterministic Toolchain Status
   - Passed: `true | false`
   - Summary: ...

   ## Findings
   | ID | Severity | Category | Location | Requirement / Contract | Defect & Required Fix |
   | :--- | :--- | :--- | :--- | :--- | :--- |

   ## Traceability Summary
   - Total `REQ-###` checked: N
   - Fully verified: M
   ```

4. **Verdict Rule**:
   - Emit `VERDICT: APPROVED` **only** when `.specify/quality/latest-verify.json` has `"passed": true` AND zero `CRITICAL` or `HIGH` findings exist.
   - Otherwise emit `VERDICT: CHANGES_REQUIRED` so `__SPECKIT_COMMAND_CONVERGE__` appends concrete remediation tasks to `tasks.md`.
