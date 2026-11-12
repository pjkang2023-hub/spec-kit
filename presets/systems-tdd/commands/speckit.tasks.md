---
description: "Generate a strict Contract-First & Red-Green-Refactor TDD tasks.md mapped to REQ-### identifiers."
strategy: wrap
---

## Mandatory Systems TDD Task Generation Rules (`systems-tdd`)

**OVERRIDE OF CORE OPTIONAL-TEST DEFAULT**: In the core instructions below, ignore any statement saying "Tests are OPTIONAL". Under `systems-tdd`, **automated tests are MANDATORY for every foundational module and every user story**.

Enforce these strict ordering invariants in the generated `tasks.md`:

1. **Toolchain & Sanitizer Harness First (Phase 1)**: Include tasks to configure the build manifest (`Cargo.toml`, `go.mod`, `CMakeLists.txt`, `meson.build`, or `Makefile`), strict warning-as-error flags, and `ASan`+`UBSan` / `-race` test targets before feature code.
2. **Three-Subphase Vertical Slices (`Contract -> Red -> Green`)**: Every user story phase MUST split into:
   - **Step A — Public Contract Stubs**: Materialize compilable headers/traits/interfaces/types matching `contracts/` with explicit unimplemented stubs so tests can compile against the real API.
   - **Step B — Red Phase (Failing Tests First)**: Write unit, boundary, error-path, resource-cleanup, and concurrency tests referencing `REQ-###` IDs. Explicitly require verifying that tests compile and **fail for the expected behavioral reason** before Step C begins.
   - **Step C — Green & Harden Phase**: Implement production code to make all tests pass, eliminate every stub/placeholder (`TODO`, `FIXME`, `todo!()`, `unimplemented!()`), and pass formatter + linter + sanitizer checks with zero warnings.
3. **100% Requirement Coverage**: Every `REQ-###` in `spec.md` MUST appear on at least one Red-phase test task and one Green-phase implementation task.

{CORE_TEMPLATE}
