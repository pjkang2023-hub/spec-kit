# Systems High-Assurance SDD Bundle (`systems-sdd`)

Provisions the complete Spec-to-Code stack for **C, C++, Rust, and Go** in a single step:

- **Preset (`systems-tdd` `1.0.0`)**: Systems invariants in `spec.md`, public header/trait/interface contracts in `plan.md`, and mandatory `Contract -> Red -> Green` task ordering in `tasks.md`.
- **Extension (`quality` `1.0.0`)**: Deterministic toolchain runner (`verify_quality`) + fresh-context adversarial Principal Systems Engineer critic (`speckit.quality.review`).
- **Workflow (`systems-sdd` `1.0.0`)**: Human gates on `spec.md` and `plan.md` followed by an autonomous `do-while` loop (`implement` → `verify` → `review` → `converge`) with a hard post-loop verification gate.
