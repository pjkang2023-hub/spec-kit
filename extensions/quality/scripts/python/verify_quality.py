#!/usr/bin/env python3
"""Deterministic systems quality verification gate for Spec Kit.

Auto-detects C/C++ (CMake, Meson, Make), Rust (Cargo), and Go (Go Modules),
executes configured or default compiler/linter/test/sanitizer checks without
invoking a shell, scans production code for leftover stub markers, and writes
a structured report to ``.specify/quality/latest-verify.json``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".specify",
        "specs",
        "build",
        "cmake-build-debug",
        "cmake-build-release",
        "out",
        "dist",
        "target",
        "vendor",
        "third_party",
        "external",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "tests",
        "test",
        "benches",
        "examples",
    }
)

SOURCE_EXTENSIONS = frozenset(
    {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hxx", ".rs", ".go"}
)

STUB_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("rust_todo_macro", re.compile(r"\btodo!\s*\(")),
    ("rust_unimplemented_macro", re.compile(r"\bunimplemented!\s*\(")),
    (
        "not_implemented_panic",
        re.compile(r'\bpanic!\s*\(\s*"(?:not implemented|todo|fixme)', re.IGNORECASE),
    ),
    (
        "c_assert_todo",
        re.compile(r"\bassert\s*\(\s*(?:0|false)\s*&&", re.IGNORECASE),
    ),
    (
        "comment_todo_fixme",
        re.compile(r"(?://|/\*+|\*)\s*(?:TODO|FIXME)\b"),
    ),
)

RUST_CFG_TEST_RE = re.compile(r"^\s*#\s*\[\s*cfg\s*\(\s*test\s*\)\s*\]")
MAKEFILE_TARGET_RE_TEMPLATE = r"^{target}\s*:"


def _resolve_project_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"Project root is not a directory: {explicit}")
        return root

    init_dir = os.environ.get("SPECIFY_INIT_DIR", "").strip()
    if init_dir:
        root = Path(init_dir).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"SPECIFY_INIT_DIR is not a directory: {init_dir}")
        return root

    return Path.cwd().resolve()


def _parse_simple_yaml_config(path: Path) -> dict[str, Any]:
    """Load quality-config.yml via PyYAML if installed, else minimal stdlib fallback."""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-not-found]

        loaded = yaml.safe_load(text)
        return loaded if isinstance(loaded, dict) else {}
    except ImportError:
        pass

    result: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line or line.startswith("-"):
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if val.lower() in ("true", "yes", "on"):
            result[key] = True
        elif val.lower() in ("false", "no", "off"):
            result[key] = False
        elif val == "[]":
            result[key] = []
        elif val.isdigit():
            result[key] = int(val)
        elif val:
            result[key] = val.strip("\"'")
    return result


def load_quality_config(project_root: Path) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "sanitizers": True,
        "go_race": True,
        "stub_scan": True,
        "timeout_seconds": 300,
        "checks": [],
    }
    json_cfg = project_root / ".specify" / "quality-config.json"
    yml_cfg = (
        project_root / ".specify" / "extensions" / "quality" / "quality-config.yml"
    )

    loaded: dict[str, Any] = {}
    if json_cfg.is_file():
        data = json.loads(json_cfg.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            loaded.update(data)
    elif yml_cfg.is_file():
        loaded.update(_parse_simple_yaml_config(yml_cfg))

    env_san = os.environ.get("SPECKIT_QUALITY_SANITIZERS", "").strip().lower()
    if env_san in ("1", "true", "yes", "on"):
        loaded["sanitizers"] = True
    elif env_san in ("0", "false", "no", "off"):
        loaded["sanitizers"] = False

    merged = {**defaults, **loaded}
    timeout = merged.get("timeout_seconds", 300)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        merged["timeout_seconds"] = 300
    return merged


def _makefile_has_target(makefile: Path, target: str) -> bool:
    pattern = re.compile(MAKEFILE_TARGET_RE_TEMPLATE.format(target=re.escape(target)), re.MULTILINE)
    try:
        content = makefile.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(pattern.search(content))


def build_check_plan(
    project_root: Path, config: dict[str, Any]
) -> tuple[list[str], list[dict[str, Any]]]:
    """Return ``(stacks, check_specs)`` for the target project."""
    custom_checks = config.get("checks")
    if isinstance(custom_checks, list) and custom_checks:
        specs: list[dict[str, Any]] = []
        for idx, entry in enumerate(custom_checks, start=1):
            if isinstance(entry, str) and entry.strip():
                argv = shlex.split(entry, posix=(os.name != "nt"))
                specs.append({"name": f"custom-{idx}", "argv": argv, "mode": "exit_zero"})
            elif isinstance(entry, dict) and entry.get("cmd"):
                cmd_val = entry["cmd"]
                argv = (
                    [str(x) for x in cmd_val]
                    if isinstance(cmd_val, list)
                    else shlex.split(str(cmd_val), posix=(os.name != "nt"))
                )
                specs.append(
                    {
                        "name": str(entry.get("name") or f"custom-{idx}"),
                        "argv": argv,
                        "mode": str(entry.get("mode") or "exit_zero"),
                    }
                )
        if specs:
            return ["custom"], specs

    stacks: list[str] = []
    specs = []

    if (project_root / "Cargo.toml").is_file():
        stacks.append("rust")
        specs.extend(
            [
                {
                    "name": "rust-fmt",
                    "argv": ["cargo", "fmt", "--all", "--", "--check"],
                    "mode": "exit_zero",
                },
                {
                    "name": "rust-clippy",
                    "argv": [
                        "cargo",
                        "clippy",
                        "--all-targets",
                        "--all-features",
                        "--",
                        "-D",
                        "warnings",
                    ],
                    "mode": "exit_zero",
                },
                {
                    "name": "rust-test",
                    "argv": ["cargo", "test", "--all-targets"],
                    "mode": "exit_zero",
                },
            ]
        )

    if (project_root / "go.mod").is_file():
        stacks.append("go")
        specs.append(
            {
                "name": "go-fmt",
                "argv": ["gofmt", "-l", "."],
                "mode": "empty_stdout",
            }
        )
        specs.append(
            {
                "name": "go-vet",
                "argv": ["go", "vet", "./..."],
                "mode": "exit_zero",
            }
        )
        if shutil.which("golangci-lint"):
            specs.append(
                {
                    "name": "go-golangci-lint",
                    "argv": ["golangci-lint", "run"],
                    "mode": "exit_zero",
                }
            )
        go_test_argv = ["go", "test"]
        if bool(config.get("go_race", True)) and os.name != "nt":
            go_test_argv.append("-race")
        go_test_argv.append("./...")
        specs.append(
            {
                "name": "go-test",
                "argv": go_test_argv,
                "mode": "exit_zero",
            }
        )

    cmake_file = project_root / "CMakeLists.txt"
    meson_file = project_root / "meson.build"
    makefile = (
        project_root / "GNUmakefile"
        if (project_root / "GNUmakefile").is_file()
        else project_root / "Makefile"
    )

    if cmake_file.is_file():
        stacks.append("c-cpp-cmake")
        cmake_cfg_argv = [
            "cmake",
            "-B",
            "build",
            "-DCMAKE_BUILD_TYPE=Debug",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        ]
        if bool(config.get("sanitizers", True)) and os.name != "nt":
            san_flags = "-fsanitize=address,undefined -fno-omit-frame-pointer"
            cmake_cfg_argv.extend(
                [
                    f"-DCMAKE_C_FLAGS_DEBUG=-g -O1 {san_flags}",
                    f"-DCMAKE_CXX_FLAGS_DEBUG=-g -O1 {san_flags}",
                    f"-DCMAKE_EXE_LINKER_FLAGS_DEBUG={san_flags}",
                ]
            )
        specs.extend(
            [
                {
                    "name": "cmake-configure",
                    "argv": cmake_cfg_argv,
                    "mode": "exit_zero",
                },
                {
                    "name": "cmake-build",
                    "argv": ["cmake", "--build", "build"],
                    "mode": "exit_zero",
                },
                {
                    "name": "ctest",
                    "argv": ["ctest", "--test-dir", "build", "--output-on-failure"],
                    "mode": "exit_zero",
                },
            ]
        )
    elif meson_file.is_file():
        stacks.append("c-cpp-meson")
        if not (project_root / "build" / "build.ninja").is_file():
            setup_argv = ["meson", "setup", "build"]
            if bool(config.get("sanitizers", True)) and os.name != "nt":
                setup_argv.append("-Db_sanitize=address,undefined")
            specs.append(
                {
                    "name": "meson-setup",
                    "argv": setup_argv,
                    "mode": "exit_zero",
                }
            )
        specs.extend(
            [
                {
                    "name": "meson-compile",
                    "argv": ["meson", "compile", "-C", "build"],
                    "mode": "exit_zero",
                },
                {
                    "name": "meson-test",
                    "argv": ["meson", "test", "-C", "build", "--print-errorlogs"],
                    "mode": "exit_zero",
                },
            ]
        )
    elif makefile.is_file():
        stacks.append("c-cpp-make")
        specs.append(
            {
                "name": "make-build",
                "argv": ["make"],
                "mode": "exit_zero",
            }
        )
        if _makefile_has_target(makefile, "test"):
            specs.append(
                {
                    "name": "make-test",
                    "argv": ["make", "test"],
                    "mode": "exit_zero",
                }
            )
        elif _makefile_has_target(makefile, "check"):
            specs.append(
                {
                    "name": "make-check",
                    "argv": ["make", "check"],
                    "mode": "exit_zero",
                }
            )

    return stacks, specs


def _execute_check(
    project_root: Path, spec: dict[str, Any], timeout_seconds: int
) -> dict[str, Any]:
    argv = [str(part) for part in spec["argv"]]
    name = str(spec["name"])
    mode = str(spec.get("mode", "exit_zero"))
    cmd_display = " ".join(argv)
    started = time.monotonic()

    try:
        proc = subprocess.run(
            argv,
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        combined = "\n".join(
            part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip()
        )
        if mode == "empty_stdout":
            passed = proc.returncode == 0 and proc.stdout.strip() == ""
            exit_code = proc.returncode if passed else (proc.returncode or 1)
        else:
            passed = proc.returncode == 0
            exit_code = proc.returncode
        return {
            "name": name,
            "command": cmd_display,
            "exit_code": exit_code,
            "passed": passed,
            "duration_ms": duration_ms,
            "output_excerpt": combined[:4000],
        }
    except FileNotFoundError:
        duration_ms = int((time.monotonic() - started) * 1000)
        return {
            "name": name,
            "command": cmd_display,
            "exit_code": 127,
            "passed": False,
            "duration_ms": duration_ms,
            "output_excerpt": f"Required tool not found on PATH: {argv[0]}",
        }
    except subprocess.TimeoutExpired:
        duration_ms = int((time.monotonic() - started) * 1000)
        return {
            "name": name,
            "command": cmd_display,
            "exit_code": 124,
            "passed": False,
            "duration_ms": duration_ms,
            "output_excerpt": f"Command timed out after {timeout_seconds}s: {cmd_display}",
        }


def scan_production_stubs(project_root: Path) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for current_root, dirnames, filenames in os.walk(project_root):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in EXCLUDED_DIRS and not d.startswith(".")
        )
        root_path = Path(current_root)
        for filename in sorted(filenames):
            file_path = root_path / filename
            suffix = file_path.suffix.lower()
            if suffix not in SOURCE_EXTENSIONS:
                continue
            if suffix == ".go" and filename.endswith("_test.go"):
                continue
            if filename.startswith("test_") or filename.endswith(
                ("_test.c", "_test.cc", "_test.cpp", "_tests.cpp")
            ):
                continue

            try:
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue

            rel_path = file_path.relative_to(project_root).as_posix()
            for lineno, line in enumerate(lines, start=1):
                if suffix == ".rs" and RUST_CFG_TEST_RE.match(line):
                    break
                for marker, pattern in STUB_PATTERNS:
                    if pattern.search(line):
                        violations.append(
                            {
                                "file": rel_path,
                                "line": lineno,
                                "marker": marker,
                                "text": line.strip()[:200],
                            }
                        )
                        break
    return violations


def run_verification(project_root: Path) -> dict[str, Any]:
    config = load_quality_config(project_root)
    stacks, check_specs = build_check_plan(project_root, config)
    timeout_seconds = int(config.get("timeout_seconds", 300))

    checks: list[dict[str, Any]] = []
    for spec in check_specs:
        result = _execute_check(project_root, spec, timeout_seconds)
        checks.append(result)

    stub_violations = (
        scan_production_stubs(project_root) if bool(config.get("stub_scan", True)) else []
    )

    if not stacks:
        passed = False
        summary = (
            "No supported systems build manifest found "
            "(Cargo.toml, go.mod, CMakeLists.txt, meson.build, or Makefile)."
        )
    else:
        failed_checks = [c["name"] for c in checks if not c["passed"]]
        passed = len(failed_checks) == 0 and len(stub_violations) == 0
        if passed:
            summary = (
                f"PASSED: all {len(checks)} check(s) succeeded across "
                f"{', '.join(stacks)} with 0 production stub violations."
            )
        else:
            parts: list[str] = []
            if failed_checks:
                parts.append(f"failed checks: {', '.join(failed_checks)}")
            if stub_violations:
                parts.append(f"{len(stub_violations)} production stub violation(s)")
            summary = f"FAILED ({'; '.join(parts)})."

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "passed": passed,
        "stacks": stacks,
        "project_root": str(project_root),
        "checks": checks,
        "stub_violations": stub_violations,
        "summary": summary,
    }

    report_dir = project_root / ".specify" / "quality"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "latest-verify.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _format_human_report(report: dict[str, Any]) -> str:
    lines = [
        f"Quality Verification: {'PASSED' if report['passed'] else 'FAILED'}",
        f"Stacks: {', '.join(report['stacks']) if report['stacks'] else 'none'}",
        f"Summary: {report['summary']}",
    ]
    for check in report["checks"]:
        status = "[PASS]" if check["passed"] else "[FAIL]"
        lines.append(
            f"  {status} {check['name']} ({check['duration_ms']}ms): {check['command']}"
        )
        if not check["passed"] and check["output_excerpt"]:
            lines.append(f"    {check['output_excerpt'][:500]}")
    for violation in report["stub_violations"]:
        lines.append(
            f"  [STUB] {violation['file']}:{violation['line']} "
            f"({violation['marker']}): {violation['text']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic systems quality verification gates."
    )
    parser.add_argument("--json", action="store_true", help="Output JSON report to stdout")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--soft-exit",
        action="store_true",
        help="Exit 0 even when checks fail (for workflow JSON capture)",
    )
    mode.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when checks fail (default)",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Target project directory (defaults to SPECIFY_INIT_DIR or cwd)",
    )
    args = parser.parse_args(argv)

    try:
        project_root = _resolve_project_root(args.project_root)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    report = run_verification(project_root)
    if args.json:
        sys.stdout.write(json.dumps(report) + "\n")
    else:
        print(_format_human_report(report))

    if args.soft_exit:
        return 0
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
