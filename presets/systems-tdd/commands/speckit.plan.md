---
description: "Execute contract-first systems implementation planning (C, C++, Rust, Go) with strict compiler, memory, concurrency, and verification gates."
strategy: wrap
---

## Systems Contract-First Planning Rules (`systems-tdd`)

Before and during the core planning workflow below, enforce these **non-negotiable systems design rules**:

1. **Zero Unresolved Spec Ambiguities**: If `spec.md` still contains `[NEEDS CLARIFICATION]` markers or lacks explicit memory/ownership, concurrency, or error-handling invariants, surface them immediately in `research.md` and resolve them cleanly rather than guessing silently.
2. **Concrete Public Contracts First (`contracts/`)**: Phase 1 MUST produce concrete, language-idiomatic public interface files in `FEATURE_DIR/contracts/`:
   - **C (`C11`/`C17`/`C23`)**: `.h` header contracts with include guards, opaque handle structs where appropriate, explicit `create`/`destroy` lifecycle pairs, enum status codes, `(ptr, size_t len)` bounds, and `const` correctness. Ban `gets`, `strcpy`, `sprintf`, and unchecked pointer arithmetic.
   - **C++ (`C++17`/`C++20`/`C++23`)**: `.hpp`/`.h` public class/function interfaces, RAII ownership (zero raw owning `new`/`delete`), `std::span`/`std::string_view` bounds discipline, and explicit `std::expected`/status/exception error contracts.
   - **Rust**: Public module/trait/struct/enum signatures, typed `Result<T, E>` error enums, `#![forbid(unsafe_code)]` by default (any `unsafe` requires a row in `Unsafe / Complexity Justification` with exact `// SAFETY:` preconditions), and zero `.unwrap()`/`.expect()` on fallible library inputs.
   - **Go**: Exported package interfaces/types, `context.Context` first-parameter propagation for blocking/I/O work, goroutine termination guarantees, and structured `error` wrapping.
3. **Deterministic Toolchain & Sanitizer Profile**: Explicitly specify build commands, warning-as-error flags (`-Wall -Wextra -Werror` / `clippy -D warnings` / `go vet`), and sanitizer/race flags (`-fsanitize=address,undefined` for C/C++ Debug test targets, `-race` for Go) in `plan.md`.
4. **Traceability Matrix**: Populate the `Requirement-to-Verification Traceability Matrix` in `plan.md` mapping every `REQ-###` in `spec.md` to a concrete contract symbol and target test file.

{CORE_TEMPLATE}
