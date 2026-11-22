---
description: "Assess codebase convergence against spec.md, plan.md, tasks.md, deterministic compiler/test reports, and adversarial review findings."
strategy: wrap
---

## Evidence-Driven Systems Convergence Rules (`systems-tdd`)

In addition to comparing the codebase against `spec.md`, `plan.md`, `tasks.md`, and `constitution.md` in the core workflow below, incorporate **deterministic verification and adversarial review artifacts** into your intent & gap assessment:

1. **Deterministic Quality Report (`.specify/quality/latest-verify.json`)**:
   - If `.specify/quality/latest-verify.json` exists, read it.
   - If `passed` is `false` (any build, formatter, compiler warning/linter, unit/sanitizer/race test, or zero-stub violation failed), you **MUST NOT** report `Converged`. Record each failing check or stub violation as a `CRITICAL` or `HIGH` finding (`gap-type: partial` or `contradicts`) and append concrete remediation tasks to `tasks.md`.
2. **Adversarial Critic Report (`.specify/quality/latest-review.md`)**:
   - If `.specify/quality/latest-review.md` exists, read it.
   - If it reports `VERDICT: CHANGES_REQUIRED` (or lists unresolved `CRITICAL`/`HIGH` defects such as tautological tests, missing `REQ-###` assertions, memory/lifetime bugs, race conditions, or unchecked error paths), verify each cited defect against the code and append traceable remediation tasks to `tasks.md`.
3. **Deterministic Trace Report (`.specify/trace/latest-trace.json`)**:
   - If it exists, read it. If `passed` is `false`, you **MUST NOT** report `Converged`: record each entry of `problems` (requirement without plan row, model element, `@trace`-tagged code, test or passing result; dangling reference) as a `HIGH` finding and append the remediation task to `tasks.md`.
4. **Strict Convergence Gate**:
   - Emit the final `Converged` verdict **only** when: (a) every `REQ-###` in `spec.md` and contract in `plan.md` is implemented and tested, (b) all tasks in `tasks.md` are `[X]`, (c) `.specify/quality/latest-verify.json` (when present) has `"passed": true` and zero stub violations, (d) `.specify/trace/latest-trace.json` (when present) has `"passed": true`, and (e) no `CRITICAL`/`HIGH` defects remain open.

{CORE_TEMPLATE}
