# Systems Quality Gates & Adversarial Review Extension (`quality`)

Provides deterministic compiler/linter/test/sanitizer verification and fresh-context adversarial code review for **C, C++, Rust, and Go** projects.

## Commands

- `/speckit.quality.verify` (`/speckit-quality-verify` in skills-based agents like Antigravity):
  Executes deterministic toolchain checks (`cargo fmt`/`clippy`/`test`, `gofmt`/`go vet`/`go test -race`, `cmake`+`ctest`, `meson`, or `make`) plus a production zero-stub scan (`TODO`, `FIXME`, `todo!()`, `unimplemented!()`), writing `.specify/quality/latest-verify.json`.
- `/speckit.quality.review` (`/speckit-quality-review` in skills-based agents):
  Audits the implementation against `spec.md`, `plan.md`, and `.specify/quality/latest-verify.json` for tautological tests, missing `REQ-###` coverage, memory/lifetime hazards, race conditions, and unchecked error paths, writing `.specify/quality/latest-review.md`.

## Script Modes

- `--json --soft-exit`: Always exits `0` while outputting structured JSON (`passed: true|false`) for workflow `do-while` loop conditions.
- `--strict` (default): Exits `1` whenever any deterministic check or stub scan fails.
