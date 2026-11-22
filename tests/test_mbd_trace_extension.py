"""Tests for the bundled `mbd-trace` extension (two-way requirement traceability).

Covers registration (locator, catalog, wheel force-include, systems-sdd bundle), the preset
changes it relies on (Model Element column, @trace instructions, convergence gate), and the
deterministic `verify_trace.py` behaviour: forward coverage, dangling references, failing
results, model-element checks, feature-qualified IDs, queries both ways, exit codes, and Bash
parity.  An optional test runs the pemb MBD trace when the pemb checkout is present.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from specify_cli import _locate_bundled_extension
from specify_cli.bundles.manifest import BundleManifest
from specify_cli.bundles.validator import validate_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXT_DIR = REPO_ROOT / "extensions" / "mbd-trace"
PY = EXT_DIR / "scripts" / "python" / "verify_trace.py"
SH = EXT_DIR / "scripts" / "bash" / "verify-trace.sh"
PRESET_DIR = REPO_ROOT / "presets" / "systems-tdd"
PEMB = Path("/home/pj/Projects/pemb")


def _mod():
    spec = importlib.util.spec_from_file_location("verify_trace", PY)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _project(root: Path, *, tag_req3: bool = True, junit_fail: bool = False) -> Path:
    feat = root / "specs" / "001-grid-sync"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text(
        "# Feature\n\n## Requirements\n\n"
        "- **REQ-001**: The PLL MUST lock within 50 ms of a phase jump.\n"
        "- **REQ-002**: The PLL MUST freeze below 0.1 pu.\n"
        "- **REQ-003**: The current limiter MUST hold 1.2 pu.\n"
        "- **NG-001**: No grid forming.\n"
        "- **SC-001**: 100% of REQ verified.\n", encoding="utf-8")
    (feat / "plan.md").write_text(
        "## Requirement-to-Verification Traceability Matrix\n\n"
        "| Requirement ID | Model Element | Contract Symbol / Module | Planned Test Type | Target Test File |\n"
        "| :--- | :--- | :--- | :--- | :--- |\n"
        "| `REQ-001` | `sync/ct_ctl10_pll` | `pll_step` | Unit | `tests/test_pll.c` |\n"
        "| `REQ-002` | `sync/ct_ctl10_pll` | `pll_step` | Boundary | `tests/test_pll.c` |\n"
        "| `REQ-003` | `-` | `ilim_step` | Unit | `tests/test_ilim.c` |\n", encoding="utf-8")
    (feat / "tasks.md").write_text(
        "- [x] T009 [US1] Implement PLL (`REQ-001`, `REQ-002`)\n"
        "- [ ] T010 [US2] Implement limiter (`REQ-003`)\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "pll.c").write_text(
        "/* @trace REQ-001, REQ-002 */\nfloat pll_step(float v) { return v; }\n", encoding="utf-8")
    (root / "src" / "ilim.c").write_text(
        ("/* @trace REQ-003 */\n" if tag_req3 else "") + "float ilim_step(float i) { return i; }\n",
        encoding="utf-8")
    (root / "src" / "util.c").write_text("int util(void) { return 0; }\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_pll.c").write_text("// REQ-001 lock time\n// REQ-002 freeze\n", encoding="utf-8")
    (root / "tests" / "test_ilim.c").write_text("// REQ-003 limit\n", encoding="utf-8")
    (root / "results").mkdir()
    (root / "results" / "junit.xml").write_text(
        '<testsuite><testcase classname="pll" name="REQ-001 lock"/>'
        '<testcase classname="pll" name="REQ-002 freeze"/>'
        f'<testcase classname="ilim" name="REQ-003 limit">{"<failure/>" if junit_fail else ""}</testcase>'
        "</testsuite>", encoding="utf-8")
    cfg = root / ".specify" / "extensions" / "mbd-trace"
    cfg.mkdir(parents=True)
    (cfg / "trace-config.json").write_text(json.dumps({
        "junit_globs": ["results/*.xml"], "require": ["plan", "code", "tests", "results"]}), encoding="utf-8")
    return root


class TestRegistration:
    def test_locator_catalog_pyproject_bundle(self) -> None:
        assert _locate_bundled_extension("mbd-trace") == EXT_DIR
        cat = json.loads((REPO_ROOT / "extensions" / "catalog.json").read_text(encoding="utf-8"))
        assert cat["extensions"]["mbd-trace"]["bundled"] is True
        force = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        force = force["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
        assert force["extensions/mbd-trace"] == "specify_cli/core_pack/extensions/mbd-trace"
        manifest = BundleManifest.from_file(REPO_ROOT / "bundles" / "systems-sdd" / "bundle.yml")
        assert "mbd-trace" in [e.id for e in manifest.extensions]
        assert validate_manifest(manifest).ok
        bcat = json.loads((REPO_ROOT / "bundles" / "catalog.json").read_text(encoding="utf-8"))
        assert bcat["bundles"]["systems-sdd"]["provides"]["extensions"] == 2

    def test_extension_files_exist(self) -> None:
        import yaml
        ext = yaml.safe_load((EXT_DIR / "extension.yml").read_text(encoding="utf-8"))
        for cmd in ext["provides"]["commands"]:
            assert (EXT_DIR / cmd["file"]).is_file()
        assert {h["command"] for h in ext["hooks"].values()} == {"speckit.mbd-trace.verify"}
        assert (EXT_DIR / "config-template.json").is_file()

    def test_preset_carries_model_column_and_trace_gate(self) -> None:
        plan = (PRESET_DIR / "templates" / "plan-template.md").read_text(encoding="utf-8")
        assert "| Requirement ID | Model Element |" in plan
        assert "@trace REQ-###" in (PRESET_DIR / "commands" / "speckit.implement.md").read_text(encoding="utf-8")
        assert "latest-trace.json" in (PRESET_DIR / "commands" / "speckit.converge.md").read_text(encoding="utf-8")


class TestVerifyTrace:
    def test_complete_project_passes(self, tmp_path: Path) -> None:
        r = _mod().verify(_project(tmp_path))
        assert r["passed"], r["problems"]
        s = r["summary"]
        assert (s["requirements"], s["planned"], s["implemented"], s["tested"], s["dangling"]) == (3, 3, 3, 3, 0)
        assert s["with_model"] == 2                         # REQ-003 has '-' in the Model Element column
        assert r["untraced_files"] == ["src/util.c"]        # warned, not failed
        assert any("util.c" in w for w in r["warnings"])

    def test_missing_code_and_failing_result_fail(self, tmp_path: Path) -> None:
        r = _mod().verify(_project(tmp_path, tag_req3=False, junit_fail=True))
        assert not r["passed"]
        assert "001-grid-sync/REQ-003: no code" in r["problems"]
        assert any("REQ-003: failing test" in p for p in r["problems"])

    def test_dangling_references_fail(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / "src" / "extra.c").write_text("// @trace REQ-009\nint x;\n", encoding="utf-8")
        (root / "tests" / "test_x.c").write_text("// checks REQ-010\n", encoding="utf-8")
        r = _mod().verify(root)
        assert not r["passed"]
        refs = {(d["layer"], d["ref"]) for d in r["dangling"]}
        assert refs == {("code", "REQ-009"), ("tests", "REQ-010")}

    def test_model_elements_checked_against_models(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        model = {"name": "sst_ctrl_lib", "system": {"blocks": [
            {"name": "sync", "system": {"blocks": [{"name": "ct_ctl10_pll", "system": {"blocks": []}}]}}]}}
        (root / "model.json").write_text(json.dumps(model), encoding="utf-8")
        cfgp = root / ".specify" / "extensions" / "mbd-trace" / "trace-config.json"
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        cfg.update(model_json=["model.json"], require=["plan", "code", "tests"])
        cfgp.write_text(json.dumps(cfg), encoding="utf-8")
        m = _mod()
        assert m.verify(root)["passed"]
        plan = root / "specs" / "001-grid-sync" / "plan.md"
        plan.write_text(plan.read_text(encoding="utf-8").replace("sync/ct_ctl10_pll", "sync/ct_ctl99", 1), encoding="utf-8")
        r = m.verify(root)
        assert not r["passed"] and any("'sync/ct_ctl99'" in p for p in r["problems"])

    def test_feature_qualified_and_ambiguous_ids(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        other = root / "specs" / "002-limiter"
        other.mkdir()
        (other / "spec.md").write_text("- **REQ-001**: Another feature's first requirement.\n", encoding="utf-8")
        (root / "src" / "lim2.c").write_text("/* @trace 002-limiter/REQ-001 */\nint y;\n", encoding="utf-8")
        (root / "src" / "amb.c").write_text("/* @trace REQ-001 */\nint z;\n", encoding="utf-8")
        r = _mod().verify(root)
        req = {x["key"]: x for x in r["requirements"]}
        assert "src/lim2.c:1" in req["002-limiter/REQ-001"]["code"]
        assert "src/lim2.c:1" not in req["001-grid-sync/REQ-001"]["code"]
        assert any("amb.c:1: REQ-001 is defined in 2 features" in w for w in r["warnings"])

    def test_query_both_ways(self, tmp_path: Path) -> None:
        m = _mod()
        r = m.verify(_project(tmp_path))
        fwd = m.query(r, "REQ-001")
        assert "code    src/pll.c:1" in fwd and "test    tests/test_pll.c:1" in fwd and "PASS" in fwd
        assert "model   sync/ct_ctl10_pll" in fwd
        back = m.query(r, "src/pll.c:2")
        assert "001-grid-sync/REQ-001" in back and "001-grid-sync/REQ-002" in back

    def test_cli_reports_and_exit_codes(self, tmp_path: Path) -> None:
        root = _project(tmp_path, tag_req3=False)
        run = lambda *a: subprocess.run([sys.executable, str(PY), "--project-root", str(root), *a],  # noqa: E731
                                        capture_output=True, text=True)
        strict = run("--json")
        assert strict.returncode == 1 and json.loads(strict.stdout)["passed"] is False
        assert run("--json", "--soft-exit").returncode == 0
        assert (root / ".specify" / "trace" / "latest-trace.json").is_file()
        assert "001-grid-sync/REQ-003" in (root / ".specify" / "trace" / "trace-matrix.md").read_text(encoding="utf-8")
        missing = subprocess.run([sys.executable, str(PY), "--project-root", str(tmp_path / "nope")],
                                 capture_output=True, text=True)
        assert missing.returncode == 2

    @pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
    def test_bash_parity(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        py = subprocess.run([sys.executable, str(PY), "--project-root", str(root), "--json"], capture_output=True, text=True)
        sh = subprocess.run(["bash", str(SH), "--project-root", str(root), "--json"], capture_output=True, text=True)
        assert py.returncode == sh.returncode == 0
        assert json.loads(py.stdout)["summary"] == json.loads(sh.stdout)["summary"]


@pytest.mark.skipif(not (PEMB / "trace.toml").exists(), reason="pemb checkout not present")
def test_pemb_mbd_trace_is_included(tmp_path: Path) -> None:
    root = _project(tmp_path)
    cfgp = root / ".specify" / "extensions" / "mbd-trace" / "trace-config.json"
    cfg = json.loads(cfgp.read_text(encoding="utf-8"))
    cfg.update(pemb_python=str(PEMB / ".venv" / "bin" / "python"), pemb_src=str(PEMB / "src"),
               pemb_trace_config=str(PEMB / "trace.toml"))
    cfgp.write_text(json.dumps(cfg), encoding="utf-8")
    r = _mod().verify(root)
    pemb = [p for p in r["problems"] if p.startswith("pemb: ")]
    assert pemb and any("CTL-" in p or "PRT-" in p for p in pemb)
