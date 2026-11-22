# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `__SPECKIT_COMMAND_PLAN__` command.

## Summary

[Primary requirement + concrete systems architecture and verification approach]

## Technical Context

**Language & Standard**: [e.g., C17, C++20, Rust 1.80+ (Edition 2021), Go 1.23+]

**Build System**: [e.g., CMake + CTest, Meson, Makefile, Cargo, Go Modules]

**Primary Dependencies**: [Minimal, vetted dependencies or stdlib-only]

**Compiler & Lint Flags**:
- *C*: `-Wall -Wextra -Werror -Wpedantic -Wconversion -Wshadow -Wstrict-prototypes`
- *C++*: `-Wall -Wextra -Werror -Wpedantic -Wconversion -Wnon-virtual-dtor`
- *Rust*: `cargo fmt --check`, `cargo clippy --all-targets --all-features -- -D warnings`, `#![forbid(unsafe_code)]` (unless justified below)
- *Go*: `gofmt`, `go vet ./...`, `golangci-lint`

**Sanitizer / Race Profile**: [e.g., `-fsanitize=address,undefined` (`ASan`+`UBSan`) for C/C++ Debug tests; `go test -race` for Go; Miri/proptest if applicable for Rust]

**Target Platform & ABI**: [e.g., Linux x86_64/aarch64, POSIX, cross-platform]

**Performance & Memory Budget**: [e.g., allocation strategy, latency/throughput targets, bounded buffers]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 contract design.*

[Gates determined based on constitution file and Systems Invariants]

## Public Interface & ABI Contracts *(mandatory before tasks)*

Document and materialize exact public signatures under `specs/[###-feature]/contracts/` (e.g., `.h` headers, `.hpp` interfaces, `.rs` trait/type definitions, or `.go` interface definitions):

- **Public Types / Handles**: [Exact structs, opaque pointers, enums, traits/interfaces]
- **Function / Method Signatures**: [Inputs, preconditions, ownership transfer, return/error types]
- **Error Taxonomy**: [Every error variant/code and caller recovery contract]
- **Lifecycle & Thread-Safety Contract**: [Init/destroy pairing, RAII guarantees, concurrency rules]

## Requirement-to-Verification Traceability Matrix

| Requirement ID | Model Element | Contract Symbol / Module | Planned Test Type (Unit / Boundary / Race / Integration) | Target Test File |
| :--- | :--- | :--- | :--- | :--- |
| `REQ-001` | `[library/folder/block or -]` | `[module::fn]` | Unit + Boundary | `[tests/...]` |
| `REQ-002` | `[library/folder/block or -]` | `[module::err]` | Negative / Fault-Injection | `[tests/...]` |

*Model Element*: in model-based projects, the model block (path in the imported model) that realizes the requirement and from which the code is generated or checked; `-` when there is no model. The `mbd-trace` extension checks every row against `spec.md`, the models, the `@trace` tags in code and the tests, in both directions.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (__SPECKIT_COMMAND_PLAN__ command output)
├── research.md          # Phase 0 output (__SPECKIT_COMMAND_PLAN__ command)
├── data-model.md        # Phase 1 output (__SPECKIT_COMMAND_PLAN__ command)
├── quickstart.md        # Phase 1 output (__SPECKIT_COMMAND_PLAN__ command)
├── contracts/           # Phase 1 output: compilable public headers/traits/interfaces
└── tasks.md             # Phase 2 output (__SPECKIT_COMMAND_TASKS__ command)
```

### Source Code (repository root)

```text
# Replace with concrete layout for C / C++ / Rust / Go:
include/ or src/
tests/
CMakeLists.txt | meson.build | Makefile | Cargo.toml | go.mod
```

**Structure Decision**: [Document selected directory and build-target layout]

## Unsafe / Complexity Justification

> **Fill ONLY if `unsafe` blocks, raw owning pointers, lock-free atomics, or Constitution exceptions are required**

| Construct / Location | Invariant Required for Soundness | Why Safe Abstraction Was Insufficient |
| :--- | :--- | :--- |
| [e.g., FFI boundary in `src/ffi.c`] | [Non-null pointer + bounded `len` checked at entry] | [Required by C ABI contract] |
