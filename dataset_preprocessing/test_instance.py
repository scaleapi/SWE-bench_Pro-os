#!/usr/bin/env python3
"""
Build a Docker test environment for a single SWE-bench Pro dataset instance.

The container runs the eval script before and after applying the patch, then
drops into an interactive shell. Results land in /workspace/before/ and
/workspace/after/ (output.json, stdout.log, stderr.log, eval.log).

Usage:
    python test_instance.py <instance_id|index> [options]

Options:
    --dataset PATH   Path to the JSONL dataset (default: ../artifacts/python_dataset.jsonl)
    --no-cache       Pass --no-cache to docker build
    --no-keep-image  Remove the built image after the session (images are kept by default)
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DEFAULT_DATASET = SCRIPT_DIR / "../artifacts/python_dataset.jsonl"
DEFAULT_BASE_DOCKERFILE = SCRIPT_DIR / "../artifacts/Dockerfile.system-deps"
BASE_IMAGE = "swebench-system-deps"

ENTRYPOINT = """\
#!/usr/bin/env bash
set -euo pipefail

source /opt/venv/bin/activate 2>/dev/null || true

run_eval() {
    local label="$1"
    local outdir="/workspace/$label"
    mkdir -p "$outdir"
    (
        sed "s|/workspace/|${outdir}/|g" /workspace/eval.sh > "$outdir/eval_run.sh"
        chmod +x "$outdir/eval_run.sh"
        bash "$outdir/eval_run.sh" > "$outdir/eval.log" 2>&1 || true
    )
    echo "Done. Results in /workspace/$label/"
}

echo "========================================================"
echo " Running eval BEFORE patch ..."
echo "========================================================"
run_eval before

echo ""
echo "========================================================"
echo " Applying patch ..."
echo "========================================================"
git apply /workspace/patch.diff
echo "Patch applied."

echo ""
echo "========================================================"
echo " Running eval AFTER patch ..."
echo "========================================================"
run_eval after

echo ""
echo "========================================================"
echo " Summary"
echo "========================================================"
echo "  Before results : /workspace/before/"
echo "  After results  : /workspace/after/"
echo "  (output.json, stdout.log, stderr.log, eval.log in each)"
echo ""
echo " Dropping into shell. The venv is active."
exec bash
"""

DOCKERFILE_TEMPLATE = """\
FROM {base_image}

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

RUN git clone https://github.com/{repo} /app
WORKDIR /app
RUN git checkout {base_commit}

COPY before_repo_set_cmd.sh /workspace/before_repo_set_cmd.sh
RUN bash /workspace/before_repo_set_cmd.sh

COPY setup.sh /workspace/setup.sh
RUN bash /workspace/setup.sh

COPY eval.sh /workspace/eval.sh
COPY patch.diff /workspace/patch.diff
COPY entrypoint.sh /workspace/entrypoint.sh
RUN chmod +x /workspace/eval.sh /workspace/entrypoint.sh

WORKDIR /app
CMD ["/workspace/entrypoint.sh"]
"""


def load_entry(dataset: Path, query: str) -> dict:
    lines = dataset.read_text().splitlines()
    if query.isdigit():
        idx = int(query)
        if idx >= len(lines):
            sys.exit(f"Index {idx} out of range (dataset has {len(lines)} entries)")
        return json.loads(lines[idx])
    for line in lines:
        entry = json.loads(line)
        if entry["instance_id"] == query:
            return entry
    sys.exit(f"instance_id not found: {query}")


def image_tag(instance_id: str) -> str:
    digest = hashlib.sha256(instance_id.encode()).hexdigest()[:16]
    return f"swebench-test-{digest}"


def image_exists(tag: str) -> bool:
    result = subprocess.run(
        ["docker", "image", "inspect", tag],
        capture_output=True,
    )
    return result.returncode == 0


def docker_build(tag: str, context: Path, no_cache: bool) -> None:
    cmd = ["docker", "build", "-t", tag]
    if no_cache:
        cmd.append("--no-cache")
    cmd.append(str(context))
    subprocess.run(cmd, check=True)


def docker_run(tag: str) -> None:
    tty_flags = ["-it"] if sys.stdin.isatty() and sys.stdout.isatty() else ["-i"]
    subprocess.run(
        ["docker", "run", "--rm"]
        + tty_flags
        + ["-e", f"TERM={os.environ.get('TERM', 'xterm-256color')}", tag],
        check=False,  # non-zero exit when user types 'exit 1' is fine
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("instance", help="instance_id string or 0-based index")
    parser.add_argument(
        "--dataset", type=Path, default=DEFAULT_DATASET, help="path to JSONL dataset"
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="pass --no-cache to docker build"
    )
    parser.add_argument(
        "--no-keep-image",
        dest="keep_image",
        action="store_false",
        help="remove the built image after the session",
    )
    parser.set_defaults(keep_image=True)
    args = parser.parse_args()

    entry = load_entry(args.dataset.resolve(), args.instance)
    repo = entry["repo"]
    base_commit = entry["base_commit"]
    instance_id = entry["instance_id"]
    tag = image_tag(instance_id)

    print(f"==> Instance : {instance_id}")
    print(f"==> Repo     : {repo}")
    print(f"==> Commit   : {base_commit}")
    print(f"==> Image    : {tag}")

    if not image_exists(BASE_IMAGE):
        print(f"==> Building base image {BASE_IMAGE} ...")
        subprocess.run(
            [
                "docker",
                "build",
                "-t",
                BASE_IMAGE,
                "-f",
                str(DEFAULT_BASE_DOCKERFILE),
                str(DEFAULT_BASE_DOCKERFILE.parent),
            ],
            check=True,
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = Path(tmpdir)

        (ctx / "setup.sh").write_text(entry["setup_script"])
        (ctx / "eval.sh").write_text("\n".join(entry["eval_scripts"]))
        (ctx / "before_repo_set_cmd.sh").write_text(entry["before_repo_set_cmd"])
        (ctx / "patch.diff").write_text(entry["patch"])
        (ctx / "entrypoint.sh").write_text(ENTRYPOINT)

        for name in ("setup.sh", "eval.sh", "before_repo_set_cmd.sh", "entrypoint.sh"):
            (ctx / name).chmod(0o755)

        (ctx / "Dockerfile").write_text(
            DOCKERFILE_TEMPLATE.format(
                base_image=BASE_IMAGE,
                repo=repo,
                base_commit=base_commit,
            )
        )

        print(f"==> Building test image {tag} ...")
        docker_build(tag, ctx, no_cache=args.no_cache)

    print("\n==> Running evaluation (before/after patch) and dropping into shell ...\n")
    try:
        docker_run(tag)
    finally:
        if not args.keep_image:
            subprocess.run(["docker", "rmi", tag], capture_output=True)


if __name__ == "__main__":
    main()
