---
description: "Execute tasks.md using strict Red-before-Green TDD, compiler/sanitizer gates, and zero-stub discipline."
strategy: wrap
---

## Systems TDD Execution Discipline (`systems-tdd`)

While executing `tasks.md` in the core workflow below, you **MUST** obey these execution gates:

1. **Honor Red-Before-Green**:
   - Complete **Contract Stub** tasks first so signatures compile.
   - Execute **Red Phase** test tasks next and run the test suite to confirm the new tests compile and **fail against the stubs** (proving the tests actually exercise real behavior rather than tautological mocks).
   - Only then implement the **Green Phase** production code until all tests pass.
2. **Never Weaken Tests or Warnings to Force Green**:
   - Do **not** delete assertions, comment out failing edge-case tests, suppress compiler warnings (`#pragma clang diagnostic ignored`, `#[allow(clippy::all)]`, `_ = err`), or leak memory to bypass a check. Fix the root cause in the implementation.
3. **Systems Safety & Zero-Stub Bar**:
   - C: Pair every allocation/handle creation with deterministic cleanup on both success and error paths; validate `NULL` pointers and buffer lengths; check every return status.
   - C++: Enforce RAII, `const` correctness, bounds-safe views/containers, and clean `ASan`/`UBSan` execution.
   - Rust: Propagate errors via `Result<T, E>`; avoid `.unwrap()`/`.expect()` on untrusted or fallible inputs; respect `#![forbid(unsafe_code)]` unless explicitly authorized in `plan.md` with `// SAFETY:` comments.
   - Go: Check and wrap every `error`, honor `ctx.Done()`, close channels/resources deterministically, and pass `go test -race`.
   - Remove all `todo!()`, `unimplemented!()`, `/* TODO */`, `// TODO`, and `// FIXME` markers from completed production modules before marking Green tasks `[X]`.

{CORE_TEMPLATE}
