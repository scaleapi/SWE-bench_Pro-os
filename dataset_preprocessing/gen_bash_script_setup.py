#!/usr/bin/env python3
"""Generate a bash setup script for a SWE-bench Pro Python task.

Produces:

  1. ENV exports (both Dockerfiles, ``ENV K V`` normalized to ``K=V``)
  2. APT      — concatenation of ALL ``RUN apt-get …`` blocks (skippable)
  3. REPO     — base Dockerfile non-apt RUN/WORKDIR steps (skippable)
  4. PREPROCESS — EOFPREP heredoc body (skippable with REPO)
  5. UV VENV  — uv install + venv at ``/opt/venv`` (outside /app, immune to ``git clean``)
  6. PYTHON   — EOFBUILD heredoc body, transformed (pip→uv, date pin, editable fix)

Usage:
    gen_bash_script_setup.py --instance-id <iid>
    gen_bash_script_setup.py --instance-id <iid> --output setup.sh
    gen_bash_script_setup.py --instance-id <iid> --skip-apt --skip-repo-setup
    gen_bash_script_setup.py --all-python --output-dir scripts/
    gen_bash_script_setup.py --list-python
"""
import argparse
import sys
from pathlib import Path

from dataset_preprocessing.dockerfile_to_bash import (
    build_sections,
    is_python_dockerfile,
    iter_python_instance_ids,
    load_local_dockerfiles,
)


def _generate_one(iid: str, args) -> str | None:
    try:
        base, inst = load_local_dockerfiles(iid)
    except FileNotFoundError:
        return None
    if not is_python_dockerfile(base):
        return None
    sections = build_sections(iid, base, inst, no_date_pin=args.no_date_pin)
    return sections.to_bash(skip_apt=args.skip_apt, skip_repo_setup=args.skip_repo_setup)


def cmd_list_python(_args) -> int:
    for iid in iter_python_instance_ids():
        print(iid)
    return 0


def cmd_convert_one(args) -> int:
    script = _generate_one(args.instance_id, args)
    if script is None:
        print(f"Warning: {args.instance_id} is not a Python instance (or Dockerfiles not found).", file=sys.stderr)
        return 1
    if args.output:
        Path(args.output).write_text(script)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(script)
    return 0


def cmd_all_python(args) -> int:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for iid in iter_python_instance_ids():
        script = _generate_one(iid, args)
        if script is None:
            print(f"  [skip] {iid}: Dockerfiles not in local dockerfiles/", file=sys.stderr)
            continue
        (out_dir / f"{iid}.sh").write_text(script)
        n += 1
    print(f"Wrote {n} setup scripts to {out_dir}", file=sys.stderr)
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--instance-id", help="Convert a single instance.")
    mode.add_argument("--all-python", action="store_true", help="Convert every Python instance from the HF dataset.")
    mode.add_argument("--list-python", action="store_true", help="Print every Python instance_id from the HF dataset and exit.")
    p.add_argument("--output", help="Output path (single-instance mode). Defaults to stdout.")
    p.add_argument("--output-dir", help="Output directory (--all-python mode).")
    p.add_argument("--skip-apt", action="store_true", help="Omit the APT section.")
    p.add_argument("--skip-repo-setup", action="store_true", help="Omit REPO + PREPROCESS sections.")
    p.add_argument("--no-date-pin", action="store_true", help="Strip pypi-timemachine without adding UV_EXCLUDE_NEWER.")
    args = p.parse_args()
    if args.all_python and not args.output_dir:
        p.error("--all-python requires --output-dir")
    return args


def main() -> int:
    args = parse_args()
    if args.list_python:
        return cmd_list_python(args)
    if args.all_python:
        return cmd_all_python(args)
    return cmd_convert_one(args)


if __name__ == "__main__":
    sys.exit(main())
