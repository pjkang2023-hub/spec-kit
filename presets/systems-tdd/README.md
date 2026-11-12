# Systems Contract-First & TDD Preset (`systems-tdd`)

A high-assurance Spec-Driven Development preset tailored for **C (`C11`/`C17`/`C23`), C++ (`C++17`/`C++20`/`C++23`), Rust, and Go**.

## What It Enforces

1. **Systems Invariants in Specifications (`spec-template.md`):**
   - Testable Given/When/Then acceptance criteria with traceable `REQ-###` identifiers.
   - Explicit ownership/lifetime/memory rules, thread-safety/concurrency guarantees, deterministic error/status semantics, and resource bounds.
2. **Contract-First Planning (`plan-template.md` & `speckit.plan`):**
   - Public `.h` headers, C++ interfaces, Rust `trait`/`Result` types, or Go package interfaces must be specified under `contracts/` *before* implementation tasks are generated.
   - Compiler warnings (`-Wall -Wextra -Werror`, `clippy -D warnings`, `go vet`) and sanitizers (`ASan`/`UBSan`, `-race`) are planned upfront.
3. **Mandatory Red-Green-Refactor Tasks (`tasks-template.md` & `speckit.tasks`):**
   - Tests are **mandatory**, never optional.
   - Every vertical slice orders tasks strictly as: **Contract Stubs → Failing Tests (Red) → Implementation & Hardening (Green)**.
4. **Evidence-Driven Convergence (`speckit.implement` & `speckit.converge`):**
   - Reads `.specify/quality/latest-verify.json` and `.specify/quality/latest-review.md` (when present) so compiler, sanitizer, test, stub, and adversarial critic findings become traceable tasks until convergence.
