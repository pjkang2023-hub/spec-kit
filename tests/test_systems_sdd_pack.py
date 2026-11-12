"""Comprehensive tests for the bundled Systems High-Assurance SDD pack.

Covers:
- Bundled asset discovery, catalog entries, pyproject wheel force-includes, and bundle validation
- Preset (`systems-tdd`) template overrides and wrap-strategy skill generation with `agy`
- Extension (`quality`) installation, hooks, and `verify_quality` positive/negative behavior
  across C/C++ (CMake, Meson, Make), Rust ( including #[cfg(test)] cutoff), and Go, plus Bash parity
- Workflow (`systems-sdd`) schema validation, human gates, multi-iteration self-healing
  do-while convergence loop, and hard failure when max_iterations is exhausted unconverged
- End-to-end `bundle install` into an Antigravity (`agy`) project
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from specify_cli import (
    _locate_bundled_extension,
    _locate_bundled_preset,
    _locate_bundled_workflow,
    app,
)
from specify_cli.bundles.manifest import BundleManifest
from specify_cli.bundles.validator import validate_manifest
from specify_cli.workflows.base import RunStatus, StepContext, StepResult, StepStatus
from specify_cli.workflows.engine import WorkflowDefinition, WorkflowEngine, validate_workflow

REPO_ROOT = Path(__file__).resolve().parent.parent
PRESET_DIR = REPO_ROOT / "presets" / "systems-tdd"
EXT_DIR = REPO_ROOT / "extensions" / "quality"
WF_DIR = REPO_ROOT / "workflows" / "systems-sdd"
BUNDLE_DIR = REPO_ROOT / "bundles" / "systems-sdd"
VERIFY_PY = EXT_DIR / "scripts" / "python" / "verify_quality.py"
VERIFY_SH = EXT_DIR / "scripts" / "bash" / "verify-quality.sh"


def _load_verify_module():
    spec = importlib.util.spec_from_file_location("verify_quality", VERIFY_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestBundledRegistrationAndManifests:
    def test_bundled_locators_find_all_three_primitives(self) -> None:
        assert _locate_bundled_preset("systems-tdd") == PRESET_DIR
        assert _locate_bundled_extension("quality") == EXT_DIR
        assert _locate_bundled_workflow("systems-sdd") == WF_DIR

    def test_pyproject_force_includes_systems_pack(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        force_inc = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
        assert force_inc["presets/systems-tdd"] == "specify_cli/core_pack/presets/systems-tdd"
        assert force_inc["extensions/quality"] == "specify_cli/core_pack/extensions/quality"
        assert force_inc["workflows/systems-sdd"] == "specify_cli/core_pack/workflows/systems-sdd"

    def test_catalogs_list_bundled_entries(self) -> None:
        presets_cat = json.loads((REPO_ROOT / "presets" / "catalog.json").read_text(encoding="utf-8"))
        ext_cat = json.loads((REPO_ROOT / "extensions" / "catalog.json").read_text(encoding="utf-8"))
        wf_cat = json.loads((REPO_ROOT / "workflows" / "catalog.json").read_text(encoding="utf-8"))
        bundles_cat = json.loads((REPO_ROOT / "bundles" / "catalog.json").read_text(encoding="utf-8"))

        assert presets_cat["presets"]["systems-tdd"]["bundled"] is True
        assert ext_cat["extensions"]["quality"]["bundled"] is True
        assert wf_cat["workflows"]["systems-sdd"]["bundled"] is True
        assert bundles_cat["bundles"]["systems-sdd"]["verified"] is True

    def test_bundle_directory_validates_cleanly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        manifest = BundleManifest.from_file(BUNDLE_DIR / "bundle.yml")
        assert manifest.bundle.id == "systems-sdd"
        report = validate_manifest(manifest)
        assert report.ok, report.errors
        monkeypatch.chdir(BUNDLE_DIR)
        runner = CliRunner()
        res = runner.invoke(app, ["bundle", "validate", "--offline"])
        assert res.exit_code == 0, res.output


class TestVerifyQualityDeterministicBehavior:
    def test_empty_directory_fails_strict_and_exits_zero_on_soft_exit(self, tmp_path: Path) -> None:
        strict_proc = subprocess.run(
            [sys.executable, str(VERIFY_PY), "--json", "--strict", "--project-root", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert strict_proc.returncode == 1
        data = json.loads(strict_proc.stdout)
        assert data["passed"] is False
        assert data["stacks"] == []
        assert (tmp_path / ".specify" / "quality" / "latest-verify.json").is_file()

        soft_proc = subprocess.run(
            [sys.executable, str(VERIFY_PY), "--json", "--soft-exit", "--project-root", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert soft_proc.returncode == 0
        soft_data = json.loads(soft_proc.stdout)
        assert soft_data["passed"] is False

    def test_missing_project_root_exits_two(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist"
        proc = subprocess.run(
            [sys.executable, str(VERIFY_PY), "--project-root", str(missing)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 2

    def test_build_plan_detects_c_cpp_cmake_meson_make_rust_and_go(self, tmp_path: Path) -> None:
        vq = _load_verify_module()
        cfg = vq.load_quality_config(tmp_path)

        # CMake (C/C++)
        cmake_dir = tmp_path / "cmake_proj"
        cmake_dir.mkdir()
        (cmake_dir / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n", encoding="utf-8")
        stacks, specs = vq.build_check_plan(cmake_dir, cfg)
        assert stacks == ["c-cpp-cmake"]
        assert [s["name"] for s in specs] == ["cmake-configure", "cmake-build", "ctest"]
        if sys.platform != "win32":
            assert any("address,undefined" in arg for arg in specs[0]["argv"])

        # Meson (C/C++)
        meson_dir = tmp_path / "meson_proj"
        meson_dir.mkdir()
        (meson_dir / "meson.build").write_text("project('demo', 'c')\n", encoding="utf-8")
        stacks, specs = vq.build_check_plan(meson_dir, cfg)
        assert stacks == ["c-cpp-meson"]
        assert [s["name"] for s in specs] == ["meson-setup", "meson-compile", "meson-test"]

        # Makefile (C/C++)
        make_dir = tmp_path / "make_proj"
        make_dir.mkdir()
        (make_dir / "Makefile").write_text("all:\n\t@true\ntest:\n\t@true\n", encoding="utf-8")
        stacks, specs = vq.build_check_plan(make_dir, cfg)
        assert stacks == ["c-cpp-make"]
        assert [s["name"] for s in specs] == ["make-build", "make-test"]

        # Rust + Go polyglot repo
        poly_dir = tmp_path / "poly"
        poly_dir.mkdir()
        (poly_dir / "Cargo.toml").write_text('[package]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8")
        (poly_dir / "go.mod").write_text("module example.com/demo\n\ngo 1.22\n", encoding="utf-8")
        stacks, specs = vq.build_check_plan(poly_dir, cfg)
        assert stacks == ["rust", "go"]
        names = [s["name"] for s in specs]
        assert "rust-clippy" in names
        assert "go-fmt" in names
        assert "go-vet" in names
        assert "go-test" in names

    def test_stub_scanner_flags_production_stubs_and_ignores_tests(self, tmp_path: Path) -> None:
        vq = _load_verify_module()
        (tmp_path / "src").mkdir()
        (tmp_path / "include").mkdir()
        (tmp_path / "tests").mkdir()

        # C header & implementation with stub markers
        (tmp_path / "include" / "ringbuf.h").write_text(
            "#ifndef RINGBUF_H\n#define RINGBUF_H\nint ringbuf_push(int v); /* TODO: bounds */\n#endif\n",
            encoding="utf-8",
        )
        (tmp_path / "src" / "ringbuf.c").write_text(
            "#include <assert.h>\nint ringbuf_push(int v) { assert(0 && \"unimplemented\"); return v; }\n",
            encoding="utf-8",
        )
        # Rust file with clean prod code and todo!() only inside #[cfg(test)]
        (tmp_path / "src" / "lib.rs").write_text(
            "pub fn add(a: i32, b: i32) -> i32 { a + b }\n\n#[cfg(test)]\nmod tests {\n    #[test]\n    fn helper() { todo!() }\n}\n",
            encoding="utf-8",
        )
        # Go _test.go and tests/ directory should be ignored
        (tmp_path / "src" / "lib_test.go").write_text("// TODO: add fuzzing\npackage demo\n", encoding="utf-8")
        (tmp_path / "tests" / "unit.cpp").write_text("// FIXME: test fixture\n", encoding="utf-8")

        violations = vq.scan_production_stubs(tmp_path)
        flagged_files = {v["file"] for v in violations}
        assert flagged_files == {"include/ringbuf.h", "src/ringbuf.c"}

    @pytest.mark.skipif(
        shutil.which("cc") is None or shutil.which("make") is None or shutil.which("bash") is None,
        reason="Requires cc, make, and bash for live C17 build + test + bash parity check",
    )
    def test_live_c_makefile_project_and_bash_parity(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "src" / "clamp.h").write_text(
            "#ifndef CLAMP_H\n#define CLAMP_H\nint clamp_i32(int v, int lo, int hi);\n#endif\n",
            encoding="utf-8",
        )
        (tmp_path / "src" / "clamp.c").write_text(
            '#include "clamp.h"\n'
            "int clamp_i32(int v, int lo, int hi) {\n"
            "    if (v < lo) return lo;\n"
            "    if (v > hi) return hi;\n"
            "    return v;\n"
            "}\n",
            encoding="utf-8",
        )
        (tmp_path / "tests" / "test_clamp.c").write_text(
            '#include "../src/clamp.h"\n'
            "#include <assert.h>\n"
            "int main(void) {\n"
            "    assert(clamp_i32(5, 0, 10) == 5);\n"
            "    assert(clamp_i32(-3, 0, 10) == 0);\n"
            "    assert(clamp_i32(99, 0, 10) == 10);\n"
            "    return 0;\n"
            "}\n",
            encoding="utf-8",
        )
        (tmp_path / "Makefile").write_text(
            "CC := cc\n"
            "CFLAGS := -std=c11 -Wall -Wextra -Werror\n"
            "all: test_bin\n"
            "test_bin: src/clamp.c tests/test_clamp.c\n"
            "\t$(CC) $(CFLAGS) src/clamp.c tests/test_clamp.c -o test_bin\n"
            "test: test_bin\n"
            "\t./test_bin\n",
            encoding="utf-8",
        )

        py_proc = subprocess.run(
            [sys.executable, str(VERIFY_PY), "--json", "--strict", "--project-root", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert py_proc.returncode == 0, py_proc.stderr
        py_report = json.loads(py_proc.stdout)
        assert py_report["passed"] is True
        assert py_report["stacks"] == ["c-cpp-make"]

        sh_proc = subprocess.run(
            ["bash", str(VERIFY_SH), "--json", "--strict", "--project-root", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert sh_proc.returncode == 0, sh_proc.stderr
        sh_report = json.loads(sh_proc.stdout)
        assert sh_report["passed"] is True
        assert sh_report["stacks"] == py_report["stacks"]


class TestSystemsWorkflowExecution:
    def test_systems_sdd_workflow_validates_cleanly(self) -> None:
        definition = WorkflowDefinition.from_yaml(WF_DIR / "workflow.yml")
        assert validate_workflow(definition) == []
        assert [s["id"] for s in definition.steps] == [
            "specify",
            "review-spec",
            "plan",
            "analyze",
            "review-plan",
            "tasks",
            "build-verify-converge",
            "enforce-convergence",
        ]

    def test_workflow_self_heals_across_iterations_and_converges(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Install the quality extension scripts into tmp_path so the real shell verify step runs!
        ext_scripts_dst = tmp_path / ".specify" / "extensions" / "quality" / "scripts"
        shutil.copytree(EXT_DIR / "scripts", ext_scripts_dst)
        (tmp_path / ".specify" / "quality-config.json").write_text(
            json.dumps(
                {
                    "checks": [
                        {
                            "name": "unit-smoke",
                            "cmd": [sys.executable, "-c", "import sys; sys.exit(0)"],
                        }
                    ],
                    "stub_scan": True,
                }
            ),
            encoding="utf-8",
        )
        # Start with a production C file containing a TODO stub so Iteration 1 fails verify!
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        c_file = src_dir / "engine.c"
        c_file.write_text("int step(void) { /* TODO: implement */ return 0; }\n", encoding="utf-8")

        impl_calls = 0
        converge_calls = 0

        def fake_command_execute(self_step: Any, config: dict[str, Any], context: StepContext) -> StepResult:
            nonlocal impl_calls, converge_calls
            cmd = config.get("command", "")
            if cmd == "speckit.implement":
                impl_calls += 1
                if impl_calls >= 2:
                    # On second iteration, fix the stub!
                    c_file.write_text("int step(void) { return 42; }\n", encoding="utf-8")
                return StepResult(status=StepStatus.COMPLETED, output={"exit_code": 0, "stdout": "implemented", "stderr": ""})
            if cmd == "speckit.quality.review":
                return StepResult(status=StepStatus.COMPLETED, output={"exit_code": 0, "stdout": "VERDICT: APPROVED", "stderr": ""})
            if cmd == "speckit.converge":
                converge_calls += 1
                verify_json = json.loads(
                    (tmp_path / ".specify" / "quality" / "latest-verify.json").read_text(encoding="utf-8")
                )
                if verify_json["passed"]:
                    msg = "✅ Converged — the implementation satisfies the spec, plan, and tasks."
                else:
                    msg = "Appended 1 remediation task under Phase 5: Convergence."
                return StepResult(status=StepStatus.COMPLETED, output={"exit_code": 0, "stdout": msg, "stderr": ""})
            return StepResult(status=StepStatus.COMPLETED, output={"exit_code": 0, "stdout": f"ran {cmd}", "stderr": ""})

        from specify_cli.workflows.step.command import CommandStep

        monkeypatch.setattr(CommandStep, "execute", fake_command_execute)

        definition = WorkflowDefinition.from_yaml(WF_DIR / "workflow.yml")
        engine = WorkflowEngine(tmp_path)
        state = engine.execute(
            definition,
            inputs={
                "spec": "Build deterministic ring buffer in C17",
                "integration": "agy",
                "systems_review_spec_verdict": "approve",
                "systems_review_plan_verdict": "approve",
            },
        )

        assert state.status is RunStatus.COMPLETED
        assert impl_calls == 2
        assert converge_calls == 2
        assert state.step_results["verify"]["output"]["data"]["passed"] is True

    def test_workflow_fails_hard_when_max_iterations_exhausted_unconverged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ext_scripts_dst = tmp_path / ".specify" / "extensions" / "quality" / "scripts"
        shutil.copytree(EXT_DIR / "scripts", ext_scripts_dst)
        # Empty repo with no Cargo.toml/CMakeLists.txt/Makefile -> verify always fails!
        from specify_cli.workflows.step.command import CommandStep

        def fake_command_execute(self_step: Any, config: dict[str, Any], context: StepContext) -> StepResult:
            return StepResult(
                status=StepStatus.COMPLETED,
                output={"exit_code": 0, "stdout": "tasks_appended: still missing build manifest", "stderr": ""},
            )

        monkeypatch.setattr(CommandStep, "execute", fake_command_execute)

        definition = WorkflowDefinition.from_yaml(WF_DIR / "workflow.yml")
        engine = WorkflowEngine(tmp_path)
        state = engine.execute(
            definition,
            inputs={
                "spec": "Unfinished component",
                "integration": "agy",
                "systems_review_spec_verdict": "approve",
                "systems_review_plan_verdict": "approve",
            },
        )

        assert state.status is RunStatus.FAILED
        assert state.step_results["fail-unconverged"]["status"] == "failed"


class TestEndToEndBundleInstallWithAntigravity:
    def test_init_agy_and_bundle_install_systems_sdd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        proj = tmp_path / "c_engine"

        init_res = runner.invoke(
            app,
            [
                "init",
                str(proj),
                "--integration",
                "agy",
                "--script",
                "py",
                "--ignore-agent-tools",
            ],
        )
        assert init_res.exit_code == 0, init_res.output

        monkeypatch.chdir(proj)
        bundle_res = runner.invoke(app, ["bundle", "install", str(BUNDLE_DIR)])
        assert bundle_res.exit_code == 0, bundle_res.output

        # Verify Antigravity skills exist for core + quality extension commands
        skills_dir = proj / ".agents" / "skills"
        assert (skills_dir / "speckit-specify" / "SKILL.md").is_file()
        assert (skills_dir / "speckit-plan" / "SKILL.md").is_file()
        assert (skills_dir / "speckit-tasks" / "SKILL.md").is_file()
        assert (skills_dir / "speckit-implement" / "SKILL.md").is_file()
        assert (skills_dir / "speckit-converge" / "SKILL.md").is_file()
        assert (skills_dir / "speckit-quality-verify" / "SKILL.md").is_file()
        assert (skills_dir / "speckit-quality-review" / "SKILL.md").is_file()

        # Verify wrapped commands contain our systems-tdd rules AND preserved core body
        tasks_skill = (skills_dir / "speckit-tasks" / "SKILL.md").read_text(encoding="utf-8")
        assert "Mandatory Systems TDD Task Generation Rules (`systems-tdd`)" in tasks_skill
        assert "setup_tasks.py" in tasks_skill

        converge_skill = (skills_dir / "speckit-converge" / "SKILL.md").read_text(encoding="utf-8")
        assert "Evidence-Driven Systems Convergence Rules (`systems-tdd`)" in converge_skill
        assert "latest-verify.json" in converge_skill

        # Verify workflow is installed in .specify/workflows/
        assert (proj / ".specify" / "workflows" / "systems-sdd" / "workflow.yml").is_file()
