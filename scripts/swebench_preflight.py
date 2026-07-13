#!/usr/bin/env python3
"""Preflight checks before running SWE-bench Pro evaluation.

Validates patch JSON, run_scripts layout, and known harness footguns (#101, #93)
before invoking swe_bench_pro_eval.py.

Usage:
  python scripts/swebench_preflight.py --patches gold_patches.json --scripts-dir run_scripts
  python scripts/swebench_preflight.py --patches preds.json --scripts-dir run_scripts --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_PATCH_KEYS = ("instance_id", "patch", "prefix")
KNOWN_WARNINGS: dict[str, str] = {
    "NodeBB": (
        "NodeBB instances may log sendmail-not-found during email tests when running "
        "golden patches (#101). Tests may still pass; see docs/GOLDEN_PATCH.md."
    ),
}


def load_patches(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected JSON array of patch objects")
    return data


def validate_patches(patches: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    gates: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()

    for i, entry in enumerate(patches):
        if not isinstance(entry, dict):
            errors.append(f"entry {i}: expected object")
            continue
        missing = [k for k in REQUIRED_PATCH_KEYS if k not in entry]
        if missing:
            errors.append(f"entry {i}: missing keys {missing}")
            continue
        iid = entry["instance_id"]
        if iid in seen:
            errors.append(f"duplicate instance_id: {iid}")
        seen.add(iid)
        if not str(entry.get("patch", "")).strip():
            errors.append(f"{iid}: empty patch")

    gates.append(
        {
            "name": "patch_schema",
            "passed": not errors,
            "detail": f"{len(patches)} patch(es), {len(seen)} unique instance_id(s)",
        }
    )
    return gates, errors


def validate_run_scripts(
    patches: list[dict[str, Any]], scripts_dir: Path
) -> tuple[list[dict[str, Any]], list[str]]:
    gates: list[dict[str, Any]] = []
    errors: list[str] = []
    missing_scripts: list[str] = []
    missing_parsers: list[str] = []
    valid_count = 0

    for entry in patches:
        if not isinstance(entry, dict):
            continue
        iid = entry.get("instance_id")
        if not iid:
            continue
        valid_count += 1
        inst_dir = scripts_dir / iid
        run_script = inst_dir / "run_script.sh"
        parser = inst_dir / "parser.py"
        if not run_script.is_file():
            missing_scripts.append(iid)
            errors.append(f"{iid}: missing {run_script}")
        if not parser.is_file():
            missing_parsers.append(iid)
            errors.append(f"{iid}: missing {parser}")

    layout_ok = not missing_scripts and not missing_parsers
    gates.append(
        {
            "name": "run_scripts_layout",
            "passed": layout_ok,
            "detail": (
                f"all {valid_count} instance run_scripts and parsers present"
                if layout_ok
                else (
                    f"missing run_script for {len(missing_scripts)} instance(s), "
                    f"missing parser for {len(missing_parsers)} instance(s)"
                )
            ),
        }
    )
    return gates, errors


def collect_known_warnings(patches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for entry in patches:
        if not isinstance(entry, dict):
            continue
        iid = entry.get("instance_id")
        if not iid:
            continue
        for needle, message in KNOWN_WARNINGS.items():
            if needle in iid:
                warnings.append({"instance_id": iid, "warning": message})
    return warnings


def check_binary_patch_sections(patches: list[dict[str, Any]]) -> dict[str, Any]:
    binary_hits = 0
    for entry in patches:
        patch = entry.get("patch", "")
        if re.search(r"^Binary files .* differ$", patch, re.MULTILINE):
            binary_hits += 1
    return {
        "name": "binary_patch_sections",
        "passed": True,
        "detail": (
            f"{binary_hits} patch(es) contain binary hunks (stripped at eval time)"
            if binary_hits
            else "no binary hunks detected"
        ),
        "warn": binary_hits > 0,
    }


def run_preflight(patches_path: Path, scripts_dir: Path) -> dict[str, Any]:
    patches = load_patches(patches_path)
    gates: list[dict[str, Any]] = []
    all_errors: list[str] = []

    g1, e1 = validate_patches(patches)
    gates.extend(g1)
    all_errors.extend(e1)

    g2, e2 = validate_run_scripts(patches, scripts_dir)
    gates.extend(g2)
    all_errors.extend(e2)

    gates.append(check_binary_patch_sections(patches))
    warnings = collect_known_warnings(patches)

    active = [g for g in gates if not g.get("warn")]
    passed = all(g["passed"] for g in active)

    return {
        "patches": str(patches_path.resolve()),
        "scripts_dir": str(scripts_dir.resolve()),
        "patch_count": len(patches),
        "gates": gates,
        "warnings": warnings,
        "errors": all_errors,
        "passed": passed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SWE-bench Pro eval preflight")
    parser.add_argument("--patches", type=Path, required=True, help="Patch JSON for eval")
    parser.add_argument(
        "--scripts-dir",
        type=Path,
        default=Path("run_scripts"),
        help="Directory with per-instance run_script.sh (default: run_scripts)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable report")
    args = parser.parse_args(argv)

    if not args.patches.is_file():
        print(f"error: patches file not found: {args.patches}", file=sys.stderr)
        return 1
    if not args.scripts_dir.is_dir():
        print(f"error: scripts dir not found: {args.scripts_dir}", file=sys.stderr)
        return 1

    report = run_preflight(args.patches, args.scripts_dir)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"SWE-bench Pro preflight — {status}")
        for gate in report["gates"]:
            mark = "PASS" if gate["passed"] else "FAIL"
            if gate.get("warn"):
                mark = "WARN"
            print(f"  [{mark}] {gate['name']}: {gate['detail']}")
        for w in report["warnings"]:
            print(f"  [WARN] {w['instance_id']}: {w['warning']}")
        for err in report["errors"]:
            print(f"  [ERR] {err}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
