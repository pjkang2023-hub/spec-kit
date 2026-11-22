---
description: "Mandatory Contract-First & Red-Green-Refactor TDD task list template for systems software"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`

**Prerequisites**: `plan.md` (required), `spec.md` (required), `contracts/` (required public signatures), `data-model.md`, `research.md`

**Tests (MANDATORY — NEVER OPTIONAL)**: Every user story and foundational module MUST follow strict **Contract Stubs -> Failing Tests (Red) -> Implementation & Hardening (Green)** ordering. Do NOT write production logic before its corresponding failing tests exist and compile against the contract.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (disjoint files, no unmet dependencies)
- **[Story]**: User story label (e.g., `[US1]`, `[US2]`) and traced `REQ-###` IDs
- Always include exact file paths (`include/...`, `src/...`, `tests/...`)

---

## Phase 1: Build System & Toolchain Setup

**Purpose**: Reproducible build, strict compiler warnings, formatter/linter config, and test/sanitizer harness

- [ ] T001 Create directory layout and build manifest (`Cargo.toml` / `go.mod` / `CMakeLists.txt` / `meson.build` / `Makefile`) per `plan.md`
- [ ] T002 Configure strict compiler warning flags (`-Wall -Wextra -Werror` / `clippy -D warnings` / `go vet`) and sanitizer/race test targets (`ASan`+`UBSan` / `-race`)
- [ ] T003 [P] Add minimal smoke build check verifying empty/harness target compiles and test runner executes

---

## Phase 2: Foundational Types & Error Infrastructure (Blocking Prerequisites)

**Purpose**: Core error types, status codes, memory/RAII helpers, and shared interfaces required by all stories

- [ ] T004 Define core error enum/status codes and result types in `[path]` per `contracts/`
- [ ] T005 Write unit tests for foundational invariants/error formatting in `[test-path]` (Red -> Green)

**Checkpoint**: Build & test harness green; user story slices can proceed.

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

**Goal**: [What this slice delivers and which `REQ-###` IDs it satisfies]

**Independent Test**: [Exact build + test command verifying US1]

### Step 3A — Public Contract Stubs (Compilable Signatures Only)

- [ ] T006 [US1] Materialize public header/trait/interface signatures and stubbed bodies in `[src/include path]` matching `contracts/` (`REQ-001`, `REQ-002`)

### Step 3B — Red Phase: Failing Tests First *(MUST compile and FAIL before Step 3C)*

- [ ] T007 [P] [US1] Write happy-path contract & acceptance tests for `REQ-001` in `[tests/path]` and verify they fail against stubs
- [ ] T008 [P] [US1] Write boundary, invalid-input, error-path, and lifecycle/concurrency tests for `REQ-002` in `[tests/path]` and verify they fail

### Step 3C — Green & Harden Phase: Production Implementation

- [ ] T009 [US1] Implement core logic in `[src/path]` to satisfy `REQ-001` and `REQ-002`, tagging each implementing function `@trace REQ-001` / `@trace REQ-002`, removing all placeholder stubs
- [ ] T010 [US1] Run full compiler warnings, linter, unit/integration tests, and race/sanitizer checks; refactor for clarity and bounds safety while keeping tests green

**Checkpoint**: User Story 1 compiles with zero warnings, zero stubs, and 100% passing tests.

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [What this slice delivers and traced `REQ-###` IDs]

**Independent Test**: [Exact build + test command verifying US2]

### Step 4A — Public Contract Stubs

- [ ] T011 [US2] Materialize public signatures and compilable stubs in `[src/include path]` (`REQ-003`)

### Step 4B — Red Phase: Failing Tests First

- [ ] T012 [P] [US2] Write acceptance, boundary, and fault-path tests for `REQ-003` in `[tests/path]` and confirm expected failure

### Step 4C — Green & Harden Phase: Production Implementation

- [ ] T013 [US2] Implement production logic in `[src/path]`, eliminate stubs, and pass compiler/linter/sanitizer test suite

---

## Final Phase: Systems Hardening & Verification Gate

- [ ] T014 Run `speckit.mbd-trace.verify` until `TRACE_VERIFY: PASSED`: every `REQ-###` planned, implemented (`@trace`), tested and passing, no dangling references
- [ ] T015 Execute full deterministic quality gate (format, strict warnings/lints, race/ASan+UBSan tests, zero-stub scan)
