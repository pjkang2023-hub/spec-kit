# Systems High-Assurance SDD Workflow (`systems-sdd`)

Orchestrates **Contract-First & Red-Green-Refactor SDD** for C, C++, Rust, and Go with human approval gates on design artifacts and an autonomous self-healing build-verify-review-converge loop.

## Usage

```bash
# Initialize a project with Antigravity (or another CLI-capable integration)
specify init my-engine --integration agy --preset systems-tdd
cd my-engine
specify extension add quality
specify workflow add systems-sdd

# Or install all three in one command from a local/remote bundle:
specify bundle install /path/to/spec-kit/bundles/systems-sdd

# Run the hybrid workflow
specify workflow run systems-sdd --input spec="Build a thread-safe bounded ring buffer in C17 with CMake + CTest"

# Resume after reviewing spec.md and plan.md
specify workflow resume <run_id> --input systems_review_spec_verdict=approve
specify workflow resume <run_id> --input systems_review_plan_verdict=approve
```
