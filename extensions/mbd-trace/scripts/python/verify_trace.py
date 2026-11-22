#!/usr/bin/env python3
"""Deterministic two-way traceability gate for Spec Kit (stdlib only).

Forward, per requirement in ``specs/*/spec.md``:
    spec (REQ-###) -> plan matrix row -> model element -> code (@trace tag) -> test -> result
Backward:
    code and test references to requirements that do not exist (dangling), and source files
    that carry no trace at all (untraced code).

Sources read from the project root:
    specs/<feature>/spec.md     **REQ-001**: ...   (also SC-###, NG-### are listed, not required)
    specs/<feature>/plan.md     the Requirement-to-Verification Traceability Matrix table
    specs/<feature>/tasks.md    task lines naming REQ-### and their [x] state
    source files (config)       // @trace REQ-001, 001-feature/REQ-002  (to the end of the comment)
    test files (config)         any REQ-### reference: @trace tags, pytest.mark.req("REQ-001"), names
    JUnit XML (config)          testcases whose name, classname or properties name a REQ-###
    model JSON (config)         pemb-imported models; a plan Model Element must exist in one of them
    pemb trace (config)         optionally run ``pemb.trace.check`` over its own trace.toml

Writes ``.specify/trace/latest-trace.json`` and ``.specify/trace/trace-matrix.md``.

    verify_trace.py [--json] [--soft-exit | --strict] [--project-root DIR] [--query REQ-001 | FILE:LINE]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

REQ_RE = re.compile(r"(?:(?P<feat>\d{3}-[a-z0-9-]+)/)?(?P<id>REQ-\d{3})\b")
DEF_RE = re.compile(r"\*\*((?:REQ|SC|NG)-\d{3})\*\*:?\s*(.*)")
TAG_RE = re.compile(r"@trace\s+(.*?)\s*(?:\*/|-->|$)", re.M)
TASK_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(T\d{3,})?(.*)$")

NO_MODEL = {"", "-", "--", "\u2014", "n/a", "N/A", "none"}   # "no model element" markers in the plan matrix

DEFAULT_CONFIG: dict[str, Any] = {
    "source_globs": ["src/**/*", "include/**/*", "lib/**/*"],
    "source_extensions": [".c", ".h", ".cc", ".cpp", ".hpp", ".rs", ".go", ".py", ".m"],
    "test_globs": ["tests/**/*", "test/**/*"],
    "junit_globs": [],
    "model_json": [],
    "require": ["plan", "code", "tests"],     # also: "model", "results", "tasks_done"
    "untraced_code": "warn",                 # "warn" | "fail" | "ignore"
    "pemb_python": "",                       # pemb's interpreter (its own venv); default: this one
    "pemb_src": "",                          # path to pemb/src, to run pemb.trace
    "pemb_trace_config": "",                 # path to pemb's trace.toml
}


def load_config(root: Path) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    for p in (root / ".specify" / "trace-config.json",
              root / ".specify" / "extensions" / "mbd-trace" / "trace-config.json"):
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if not k.startswith("_")})
            break
    return cfg


def _files(root: Path, globs: list[str], exts: list[str] | None = None) -> list[Path]:
    out = set()
    for g in globs:
        for p in root.glob(g):
            if p.is_file() and (exts is None or p.suffix in exts) and ".specify" not in p.parts:
                out.add(p)
    return sorted(out)


def _rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


# ----------------------------------------------------------------------------- spec-kit artifacts
def read_specs(root: Path) -> dict[str, dict]:
    """REQ/SC/NG definitions per feature: key 'feature/REQ-001'."""
    reqs: dict[str, dict] = {}
    for spec in sorted((root / "specs").glob("*/spec.md")):
        feat = spec.parent.name
        for n, line in enumerate(spec.read_text(encoding="utf-8").splitlines(), 1):
            m = DEF_RE.search(line)
            if m:
                key = f"{feat}/{m.group(1)}"
                reqs[key] = {"key": key, "id": m.group(1), "feature": feat, "text": m.group(2).strip()[:160],
                             "where": f"{_rel(root, spec)}:{n}", "plan": [], "model": [], "code": [], "tests": [],
                             "results": [], "tasks": []}
    return reqs


def _cells(line: str) -> list[str]:
    return [c.strip().strip("`").strip() for c in line.strip().strip("|").split("|")]


def read_plans(root: Path, reqs: dict, resolve) -> None:
    """Rows of the traceability matrix: a header row naming the columns, then REQ rows."""
    for plan in sorted((root / "specs").glob("*/plan.md")):
        feat = plan.parent.name
        header: list[str] | None = None
        for n, line in enumerate(plan.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip().startswith("|"):
                header = None
                continue
            cells = _cells(line)
            if header is None:
                if any("requirement" in c.lower() for c in cells):
                    header = [c.lower() for c in cells]
                continue
            if set("".join(cells)) <= set(":- "):
                continue
            ids = REQ_RE.findall(cells[0]) if cells else []
            for f, rid in ids:
                for key in resolve(f or feat, rid, prefer=feat):
                    row = {header[i] if i < len(header) else f"col{i}": cells[i] for i in range(len(cells))}
                    row["where"] = f"{_rel(root, plan)}:{n}"
                    reqs[key]["plan"].append(row)
                    for col, val in row.items():
                        if "model" in col and val.strip() not in NO_MODEL and not val.startswith("["):
                            reqs[key]["model"].append({"element": val, "where": row["where"], "exists": None})


def read_tasks(root: Path, reqs: dict, resolve) -> None:
    for tasks in sorted((root / "specs").glob("*/tasks.md")):
        feat = tasks.parent.name
        for n, line in enumerate(tasks.read_text(encoding="utf-8").splitlines(), 1):
            m = TASK_RE.match(line)
            if not m:
                continue
            for f, rid in REQ_RE.findall(line):
                for key in resolve(f or feat, rid, prefer=feat):
                    reqs[key]["tasks"].append({"task": (m.group(2) or "").strip(), "done": m.group(1) in "xX",
                                               "where": f"{_rel(root, tasks)}:{n}"})


# ----------------------------------------------------------------------------- code, tests, results
def scan_refs(root: Path, files: list[Path], tags_only: bool):
    """(file:line, feature-or-'', REQ-id) for each reference; tags_only for production code."""
    refs = []
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            chunks = TAG_RE.findall(line) if tags_only else [line]
            for ch in chunks:
                for f, rid in REQ_RE.findall(ch):
                    refs.append((f"{_rel(root, p)}:{n}", f, rid))
    return refs


def read_junit(root: Path, globs: list[str]) -> list[dict]:
    out = []
    for p in _files(root, globs):
        try:
            tree = ET.parse(p)
        except ET.ParseError:
            continue
        for tc in tree.iter("testcase"):
            text = " ".join([tc.get("name", ""), tc.get("classname", "")] +
                            [pr.get("value", "") for pr in tc.iter("property")])
            failed = tc.find("failure") is not None or tc.find("error") is not None
            skipped = tc.find("skipped") is not None
            out.append({"name": f"{tc.get('classname', '')}::{tc.get('name', '')}", "text": text,
                        "passed": None if skipped else not failed, "where": _rel(root, p)})
    return out


def model_elements(root: Path, paths: list[str]) -> set[str]:
    """Block paths of pemb-imported models ('lib/folder/block'), for checking plan Model Elements."""
    elems = set()
    for rel in paths:
        p = (root / rel) if not Path(rel).is_absolute() else Path(rel)
        if not p.is_file():
            continue
        m = json.loads(p.read_text(encoding="utf-8"))
        lib = m.get("name", p.stem)

        def walk(system, path):
            for b in system.get("blocks", []):
                q = f"{path}/{b['name']}".strip("/")
                elems.add(q)
                elems.add(f"{lib}/{q}")
                if "system" in b:
                    walk(b["system"], q)
        walk(m["system"], "")
    return elems


def run_pemb(cfg: dict, root: Path) -> list[str]:
    """Run ``pemb.trace check`` in pemb's own environment (it needs numpy for its test cases)
    and return its problems prefixed 'pemb: '."""
    src, tc = cfg.get("pemb_src"), cfg.get("pemb_trace_config")
    if not (src and tc):
        return []
    srcp = (root / src) if not Path(src).is_absolute() else Path(src)
    tcp = (root / tc) if not Path(tc).is_absolute() else Path(tc)
    exe = cfg.get("pemb_python") or sys.executable
    env = dict(os.environ, PYTHONPATH=str(srcp) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    try:
        r = subprocess.run([exe, "-m", "pemb.trace", "check", str(tcp)], capture_output=True, text=True,
                           env=env, cwd=str(tcp.parent), timeout=int(cfg.get("pemb_timeout_s", 900)))
    except (OSError, subprocess.TimeoutExpired) as e:
        return [f"pemb: trace check could not run ({e})"]
    lines = [ln[6:] for ln in r.stdout.splitlines() if ln.startswith("TRACE ")]
    if r.returncode not in (0, 1):
        return [f"pemb: trace check failed (exit {r.returncode}): {(r.stderr or r.stdout).strip()[-300:]}"]
    return [f"pemb: {ln}" for ln in lines]


# ----------------------------------------------------------------------------- assemble
def verify(root: Path) -> dict[str, Any]:
    cfg = load_config(root)
    reqs = read_specs(root)
    by_id: dict[str, list[str]] = {}
    for k, r in reqs.items():
        by_id.setdefault(r["id"], []).append(k)
    problems: list[str] = []
    warnings: list[str] = []
    dangling: list[dict] = []

    def resolve(feat: str, rid: str, prefer: str | None = None) -> list[str]:
        if feat and f"{feat}/{rid}" in reqs:
            return [f"{feat}/{rid}"]
        if prefer and f"{prefer}/{rid}" in reqs:
            return [f"{prefer}/{rid}"]
        return by_id.get(rid, [])

    read_plans(root, reqs, resolve)
    read_tasks(root, reqs, resolve)

    src_files = _files(root, cfg["source_globs"], cfg["source_extensions"])
    test_files = _files(root, cfg["test_globs"], cfg["source_extensions"])
    test_set = set(test_files)
    src_files = [p for p in src_files if p not in test_set]

    traced_files = set()
    for where, f, rid in scan_refs(root, src_files, tags_only=True):
        keys = resolve(f, rid)
        traced_files.add(where.rsplit(":", 1)[0])
        if not keys:
            dangling.append({"where": where, "ref": f"{f}/{rid}".strip("/"), "layer": "code"})
        elif len(keys) > 1:
            warnings.append(f"{where}: {rid} is defined in {len(keys)} features; qualify it as <feature>/{rid}")
        for k in keys:
            reqs[k]["code"].append(where)
    for where, f, rid in scan_refs(root, test_files, tags_only=False):
        keys = resolve(f, rid)
        if not keys:
            dangling.append({"where": where, "ref": f"{f}/{rid}".strip("/"), "layer": "tests"})
        for k in keys:
            if where not in reqs[k]["tests"]:
                reqs[k]["tests"].append(where)
    for tc in read_junit(root, cfg["junit_globs"]):
        for f, rid in REQ_RE.findall(tc["text"]):
            for k in resolve(f, rid):
                reqs[k]["results"].append(tc)

    elems = model_elements(root, cfg["model_json"]) if cfg["model_json"] else None
    for r in reqs.values():
        for m in r["model"]:
            if elems is not None:
                m["exists"] = m["element"] in elems
                if not m["exists"]:
                    problems.append(f"{r['key']}: model element '{m['element']}' ({m['where']}) not found in the models")

    require = cfg["require"]
    for r in reqs.values():
        if r["id"].startswith("NG-"):
            continue
        if r["id"].startswith("SC-"):
            continue
        checks = {
            "plan": bool(r["plan"]),
            "model": bool(r["model"]),
            "code": bool(r["code"]),
            "tests": bool(r["tests"]),
            "results": bool(r["results"]) and all(t["passed"] is not False for t in r["results"]),
            "tasks_done": bool(r["tasks"]) and all(t["done"] for t in r["tasks"]),
        }
        r["status"] = checks
        for layer in require:
            if not checks.get(layer, True):
                what = {"results": "no passing test result", "tasks_done": "open tasks"}.get(layer, f"no {layer}")
                problems.append(f"{r['key']}: {what}")
        if any(t["passed"] is False for t in r["results"]):
            problems.append(f"{r['key']}: failing test " + ", ".join(t["name"] for t in r["results"] if t["passed"] is False))
    for d in dangling:
        problems.append(f"{d['where']}: {d['layer']} references unknown requirement {d['ref']}")
    untraced = sorted(_rel(root, p) for p in src_files if _rel(root, p) not in traced_files)
    if cfg["untraced_code"] == "fail":
        problems.extend(f"{u}: source file carries no @trace tag" for u in untraced)
    elif cfg["untraced_code"] == "warn":
        warnings.extend(f"{u}: source file carries no @trace tag" for u in untraced)
    problems.extend(run_pemb(cfg, root))

    n_req = sum(1 for r in reqs.values() if r["id"].startswith("REQ-"))
    summary = {
        "requirements": n_req,
        "planned": sum(1 for r in reqs.values() if r["id"].startswith("REQ-") and r["plan"]),
        "with_model": sum(1 for r in reqs.values() if r["id"].startswith("REQ-") and r["model"]),
        "implemented": sum(1 for r in reqs.values() if r["id"].startswith("REQ-") and r["code"]),
        "tested": sum(1 for r in reqs.values() if r["id"].startswith("REQ-") and r["tests"]),
        "dangling": len(dangling),
        "untraced_files": len(untraced),
    }
    return {"passed": not problems and n_req > 0, "summary": summary, "problems": problems, "warnings": warnings,
            "requirements": list(reqs.values()), "dangling": dangling, "untraced_files": untraced,
            "config": {k: cfg[k] for k in ("require", "untraced_code")}}


def write_reports(root: Path, report: dict) -> None:
    out = root / ".specify" / "trace"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest-trace.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Requirement traceability", "",
             "| Requirement | Plan | Model | Code | Tests | Results | Text |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in report["requirements"]:
        if not r["id"].startswith("REQ-"):
            continue
        res = r["results"]
        rtxt = (f"{sum(t['passed'] is True for t in res)} pass / {sum(t['passed'] is False for t in res)} fail"
                if res else "-")
        model = ", ".join(m["element"] + ("" if m["exists"] in (None, True) else " (missing)") for m in r["model"]) or "-"
        lines.append(f"| `{r['key']}` | {len(r['plan'])} | {model} | {len(r['code'])} | {len(r['tests'])} | {rtxt} | "
                     f"{r['text'][:60]} |")
    if report["dangling"]:
        lines += ["", "## Dangling references", ""] + [f"- `{d['where']}` -> {d['ref']}" for d in report["dangling"]]
    (out / "trace-matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def query(report: dict, term: str) -> str:
    """REQ-001 (or feature/REQ-001): its trace forward.  file:line: the requirements it serves."""
    out = []
    m = re.match(r"^(.*):(\d+)$", term)
    for r in report["requirements"]:
        if m:
            hits = [w for w in r["code"] + r["tests"] if w == term or (w.rsplit(":", 1)[0] == m.group(1))]
            if hits:
                out.append(f"{r['key']}  {r['text']}  <- {', '.join(hits)}")
        elif term in (r["key"], r["id"]):
            out.append(f"{r['key']}  {r['text']}  ({r['where']})")
            for row in r["plan"]:
                out.append(f"  plan    {row['where']}")
            for mm in r["model"]:
                out.append(f"  model   {mm['element']}" + ("" if mm["exists"] in (None, True) else "  (missing)"))
            for w in r["code"]:
                out.append(f"  code    {w}")
            for w in r["tests"]:
                out.append(f"  test    {w}")
            for t in r["results"]:
                out.append(f"  result  {t['name']}  {'PASS' if t['passed'] else 'FAIL' if t['passed'] is False else 'SKIP'}")
            for t in r["tasks"]:
                out.append(f"  task    {t['task']} {'done' if t['done'] else 'open'}  {t['where']}")
    return "\n".join(out) or f"nothing traces to {term!r}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--soft-exit", action="store_true", help="exit 0 even when the trace has problems")
    mode.add_argument("--strict", action="store_true", help="exit 1 on problems (default)")
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--query", help="REQ-001, <feature>/REQ-001 or FILE:LINE")
    a = ap.parse_args(argv)
    root = Path(a.project_root).resolve()
    if not root.is_dir():
        print(f"project root not found: {root}", file=sys.stderr)
        return 2
    report = verify(root)
    write_reports(root, report)
    if a.query:
        print(query(report, a.query))
        return 0
    if a.json:
        print(json.dumps({k: report[k] for k in ("passed", "summary", "problems", "warnings", "dangling",
                                                 "untraced_files")}, indent=2))
    else:
        s = report["summary"]
        print(f"TRACE: {s['requirements']} requirements, {s['planned']} planned, {s['with_model']} with a model "
              f"element, {s['implemented']} implemented, {s['tested']} tested; {s['dangling']} dangling, "
              f"{s['untraced_files']} untraced files")
        for p in report["problems"]:
            print(f"  PROBLEM {p}")
        for w in report["warnings"]:
            print(f"  warning {w}")
        print("TRACE_VERIFY: PASSED" if report["passed"] else "TRACE_VERIFY: FAILED")
    return 0 if (report["passed"] or a.soft_exit) else 1


if __name__ == "__main__":
    sys.exit(main())
