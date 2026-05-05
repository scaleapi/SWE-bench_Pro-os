#!/usr/bin/env python3
"""End-to-end smoke test: convert a task and run the setup script in a Docker container.

Spins up a fresh container of the chosen base image, mounts the generated
setup script, runs it, and verifies that ``/app`` ended up checked out at
the task's ``base_commit``.

This is a smoke test for the converter, not the benchmark — it does not
re-run the failing/passing tests, only proves the setup completes and the
working tree is at the expected commit.

Usage:
    python helper_code/test_setup_script_in_docker.py
    python helper_code/test_setup_script_in_docker.py \\
        --instance-id <iid> --base-image python:3.11-slim
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "helper_code"))

from convert_to_setup_script import (  # noqa: E402
    generate_script,
    is_python_dockerfile,
    load_local,
)

DEFAULT_INSTANCE = (
    "instance_ansible__ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8-"
    "v30a923fb5c164d6cd18280c02422f75e611e8fb2"
)
DEFAULT_IMAGE = "python:3.11-slim"


def extract_base_commit(setup_script: str) -> str:
    m = re.search(r"git reset --hard ([0-9a-f]{40})", setup_script)
    if not m:
        raise RuntimeError("Could not find a `git reset --hard <sha>` in the generated script")
    return m.group(1)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--instance-id", default=DEFAULT_INSTANCE)
    p.add_argument("--base-image", default=DEFAULT_IMAGE,
                   help="Container image to run the setup script in.")
    p.add_argument("--skip-apt", action="store_true",
                   help="Pass through to the converter (use if the base image already has system tools).")
    p.add_argument("--no-pypi-timemachine", action="store_true",
                   help="Pass through to the converter.")
    p.add_argument("--keep-workspace", action="store_true",
                   help="Don't delete the temporary workspace on exit (useful for debugging).")
    args = p.parse_args()

    if shutil.which("docker") is None:
        print("ERROR: docker is not on PATH", file=sys.stderr)
        return 2

    base, instance = load_local(args.instance_id)
    if not is_python_dockerfile(base):
        print(f"ERROR: {args.instance_id} is not a Python instance", file=sys.stderr)
        return 2

    setup = generate_script(
        args.instance_id, base, instance,
        skip_apt=args.skip_apt,
        no_pypi_timemachine=args.no_pypi_timemachine,
    )
    expected_commit = extract_base_commit(setup)
    print(f"Instance:        {args.instance_id}")
    print(f"Base image:      {args.base_image}")
    print(f"Expected commit: {expected_commit}")

    workspace = Path(tempfile.mkdtemp(prefix="swebpro-test-"))
    try:
        (workspace / "setup.sh").write_text(setup)
        driver = (
            "#!/bin/bash\n"
            "set -e\n"
            "bash /workspace/setup.sh\n"
            f'EXPECTED="{expected_commit}"\n'
            'ACTUAL=$(git -C /app rev-parse HEAD)\n'
            'if [ "$EXPECTED" != "$ACTUAL" ]; then\n'
            '  echo "FAIL: /app HEAD is $ACTUAL, expected $EXPECTED" >&2\n'
            '  exit 1\n'
            'fi\n'
            'echo "OK: /app HEAD = $ACTUAL"\n'
        )
        (workspace / "driver.sh").write_text(driver)

        cmd = [
            "docker", "run", "--rm",
            "-v", f"{workspace}:/workspace",
            args.base_image,
            "bash", "/workspace/driver.sh",
        ]
        print(f"Running: {' '.join(cmd)}", flush=True)
        rc = subprocess.call(cmd)
        if rc == 0:
            print(f"PASS: {args.instance_id} setup ran cleanly on {args.base_image}")
        else:
            print(f"FAIL: container exited with code {rc}", file=sys.stderr)
            if not args.keep_workspace:
                print("  (rerun with --keep-workspace to inspect the workspace)", file=sys.stderr)
        return rc
    finally:
        if args.keep_workspace:
            print(f"Workspace kept: {workspace}", file=sys.stderr)
        else:
            shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
