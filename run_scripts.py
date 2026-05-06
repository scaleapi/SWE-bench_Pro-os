#!/usr/bin/env python3
"""Build the base Docker image once, then run every setup script in scripts/
inside a fresh container. Successes are printed; failures are recorded in a CSV.

Usage:
    python run_scripts.py [--scripts-dir scripts] [--output failures.csv]
                         [--image-tag swebpro-base] [--timeout 600]
                         [--dry-run] [--jobs N]
"""
import argparse
import csv
import shutil
import subprocess
import sys
import textwrap
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_SCRIPTS_DIR = REPO_ROOT / "scripts"
DEFAULT_DOCKERFILE = REPO_ROOT / "Dockerfile"
DEFAULT_OUTPUT = REPO_ROOT / "failures.csv"
DEFAULT_IMAGE_TAG = "swebpro-base:latest"
DEFAULT_TIMEOUT = 600  # seconds per container


# ── helpers ──────────────────────────────────────────────────────────────────

def build_image(dockerfile: Path, tag: str) -> None:
    print(f"[build] docker build -t {tag} -f {dockerfile} {dockerfile.parent}", flush=True)
    result = subprocess.run(
        ["docker", "build", "-t", tag, "-f", str(dockerfile), str(dockerfile.parent)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(
            f"[build] FAILED (exit {result.returncode})\n"
            f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    print(f"[build] OK — image tagged {tag}", flush=True)


def run_script(script: Path, image: str, timeout: int) -> tuple[bool, str]:
    """Return (success, error_summary)."""
    cmd = [
        "docker", "run", "--rm",
        "--network", "host",          # scripts clone from GitHub
        "-v", f"{script}:/setup.sh:ro",
        image,
        "bash", "/setup.sh",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout}s"

    if result.returncode == 0:
        return True, ""

    # Combine last ~800 chars of stdout+stderr for the CSV cell
    combined = (result.stdout + result.stderr).strip()
    snippet = combined[-800:] if len(combined) > 800 else combined
    # Collapse newlines so the CSV cell stays on one logical line
    snippet = snippet.replace("\r\n", " | ").replace("\n", " | ")
    return False, f"exit={result.returncode} | {snippet}"


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--scripts-dir", type=Path, default=DEFAULT_SCRIPTS_DIR,
                   help="Directory containing the .sh setup scripts")
    p.add_argument("--dockerfile", type=Path, default=DEFAULT_DOCKERFILE)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                   help="CSV file to write failures into")
    p.add_argument("--image-tag", default=DEFAULT_IMAGE_TAG)
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                   help="Per-container timeout in seconds (default 600)")
    p.add_argument("--dry-run", action="store_true",
                   help="List scripts that would run, skip docker entirely")
    p.add_argument("--jobs", type=int, default=1,
                   help="Parallel containers (default 1; increase with care)")
    p.add_argument("--limit", type=int, default=None,
                   help="Only run the first N scripts (useful for smoke-testing)")
    args = p.parse_args()

    if not shutil.which("docker"):
        print("ERROR: docker not found on PATH", file=sys.stderr)
        return 2

    scripts = sorted(args.scripts_dir.glob("*.sh"))
    if args.limit:
        scripts = scripts[: args.limit]
    if not scripts:
        print(f"No .sh scripts found in {args.scripts_dir}", file=sys.stderr)
        return 1

    print(f"Found {len(scripts)} scripts in {args.scripts_dir}")

    if args.dry_run:
        for s in scripts:
            print(f"  [dry-run] {s.name}")
        return 0

    # ── build image ──────────────────────────────────────────────────────────
    build_image(args.dockerfile, args.image_tag)

    # ── open CSV upfront so every result is flushed immediately ──────────────
    args.output.parent.mkdir(parents=True, exist_ok=True)
    csv_lock = threading.Lock()
    failures = 0
    passed = 0
    total = len(scripts)

    with open(args.output, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["script", "status", "reason"])
        fh.flush()

        def _run(script: Path, idx: int) -> tuple[Path, bool, str]:
            prefix = f"[{idx}/{total}] {script.name}"
            print(f"{prefix} — starting", flush=True)
            ok, reason = run_script(script, args.image_tag, args.timeout)
            status = "PASS" if ok else "FAIL"
            if ok:
                print(f"{prefix} — PASS", flush=True)
            else:
                short = textwrap.shorten(reason, width=120)
                print(f"{prefix} — FAIL: {short}", flush=True)
            with csv_lock:
                writer.writerow([script.name, status, reason])
                fh.flush()
            return script, ok, reason

        if args.jobs == 1:
            for idx, script in enumerate(scripts, 1):
                _, ok, _ = _run(script, idx)
                if ok:
                    passed += 1
                else:
                    failures += 1
        else:
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                futs = {pool.submit(_run, s, i): s for i, s in enumerate(scripts, 1)}
                for fut in as_completed(futs):
                    _, ok, _ = fut.result()
                    if ok:
                        passed += 1
                    else:
                        failures += 1

    print(f"\nResults written to {args.output}")
    print(f"Done — {passed}/{total} passed, {failures}/{total} failed.")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
