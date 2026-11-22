# mbd-trace: two-way traceability

Deterministic requirement traceability for Spec Kit, in both directions:

- **Forward**, for each `REQ-###` in `specs/<feature>/spec.md`: a plan matrix row, a model
  element (model-based projects), code tagged `@trace REQ-###`, a test that names it, a passing
  result.
- **Backward**: every `@trace` tag and test reference must point at a defined requirement
  (dangling references fail); source files with no tag are listed as untraced.

The gate is a script, not a prompt: `speckit.mbd-trace.verify` runs it and reports its JSON, so a
requirement counts as covered only when the artifacts show it.

## Conventions

```c
/* @trace REQ-003, 002-grid-sync/REQ-001 */      // references run to the end of the comment
float pll_step(...)
```

- A bare `REQ-003` resolves to the feature that defines it; qualify it as `<feature>/REQ-003`
  when several features define the same number (the report warns about ambiguous tags).
- Tests may name requirements anywhere: `@trace` tags, `pytest.mark.req("REQ-003")`, test names.
- JUnit XML (`junit_globs`) gives results: a testcase counts for every REQ its name, class or
  properties mention.
- The plan's **Requirement-to-Verification Traceability Matrix** carries a `Model Element`
  column (systems-tdd preset); `-` means no model. With `model_json` set, each element must
  exist in the pemb-imported models.

## Commands

| Command | Does |
| --- | --- |
| `speckit.mbd-trace.verify` | Builds the trace, writes `.specify/trace/latest-trace.json` and `trace-matrix.md`, reports `TRACE_VERIFY: PASSED` or `FAILED` |
| `speckit.mbd-trace.query` | `REQ-001` forward (plan, model, code, tests, results, tasks), or `path/file.c:120` back to its requirements |

Hooks run `verify` after implement and before converge; the systems-tdd converge command will
not report `Converged` while the trace report fails.

## Configuration

`.specify/extensions/mbd-trace/trace-config.json` (template: `config-template.json`):

- `require`: layers every requirement must reach: `plan`, `model`, `code`, `tests`, `results`,
  `tasks_done` (default `plan`, `code`, `tests`).
- `untraced_code`: `warn` (default), `fail` or `ignore`.
- `source_globs`, `test_globs`, `junit_globs`, `model_json`.

For model-based projects set `pemb_python`, `pemb_src` and `pemb_trace_config` to add the full
pemb trace (Requirements Toolbox sets, imported Simulink libraries, C controller, PSCAD benchmark)
to the gate. It runs as a subprocess in pemb's own environment; its problems are reported with a
`pemb:` prefix.
