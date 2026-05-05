"""
Patch every SWE-Bench PRo instance Dockerfile to strip future git history.

Each instance Dockerfile has a heredoc ending in something like:

```
cd /app
git reset --hard <BASE_SHA>
git clean -fdx
git checkout <BASE_SHA>

cd /
EOFPREP
```

This script inserts a cleanup block right after the `git checkout <SHA>` line.
The cleanup mirrors SWE-bench Verified's hardening.

Usage:
    python3 strip_future_history.py                          # dry-run, prints summary
    python3 strip_future_history.py --apply                  # write changes
    python3 strip_future_history.py --apply --with-assertion # also embed a build-time leak assertion in each file
    python3 strip_future_history.py --diff                   # dry-run + show diffs

The script is idempotent, re-running on already-patched files is a no-op.

Note on --with-assertion: off by default. The assertion adds 5 lines per file that fail
the docker build if any future commit is still reachable after the cleanup.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_DIR = REPO_ROOT / "dockerfiles" / "instance_dockerfile"

MARKER = "# Strip future git history so the agent can't reach the reference fix."

# Core cleanup, inserted directly after `git checkout <SHA>`. Indentation and
# leading newline tuned so the resulting heredoc is readable.
# This mirrors SWE-bench Verified's hardening (swebench/harness/test_spec/python.py).
CLEANUP_CORE = """
# Strip future git history so the agent can't reach the reference fix.
echo "===== HEAD before cleanup ====="
git log -1 --format='HEAD = %H%n  date    = %aI%n  subject = %s' HEAD
echo "==============================="
git remote remove origin 2>/dev/null || true
git for-each-ref --format='delete %(refname)' refs/remotes refs/tags \\
  | git update-ref --stdin
HEAD_BRANCH=$(git symbolic-ref --short -q HEAD || true)
git for-each-ref refs/heads/ --format='%(refname:short)' | while read -r b; do
  [ "$b" = "$HEAD_BRANCH" ] || git branch -D "$b"
done
rm -f .git/FETCH_HEAD .git/ORIG_HEAD
git reflog expire --expire=now --all
git gc --prune=now --aggressive
"""

# Optional build-time assertion, appended only when --with-assertion is passed.
ASSERTION_BLOCK = """
# Assertion: no commit reachable from any ref dates after HEAD. Fails the image build if the cleanup missed anything.
TARGET_TIMESTAMP=$(git show -s --format=%ci HEAD)
AFTER_TIMESTAMP=$(date -d "$TARGET_TIMESTAMP + 1 second" '+%Y-%m-%d %H:%M:%S')
COMMIT_COUNT=$(git log --oneline --all --since="$AFTER_TIMESTAMP" | wc -l)
[ "$COMMIT_COUNT" -eq 0 ] || { echo "LEAK: $COMMIT_COUNT future commits reachable" >&2; exit 1; }
"""

CHECKOUT_RE = re.compile(r"^git checkout [0-9a-f]{40}\s*$", re.MULTILINE)


def patch_text(text: str, with_assertion: bool = False) -> tuple[str | None, str]:
    """
    Return (new_text, status). new_text is None if no rewrite is needed.
    status ∈ {patched, already-patched, no-checkout, multi-checkout}.
    """
    if MARKER in text:
        return None, "already-patched"

    matches = list(CHECKOUT_RE.finditer(text))
    if not matches:
        return None, "no-checkout"
    if len(matches) > 1:
        return None, "multi-checkout"

    block = CLEANUP_CORE + (ASSERTION_BLOCK if with_assertion else "")
    m = matches[0]
    insert_at = m.end()
    new_text = text[:insert_at] + block + text[insert_at:]
    return new_text, "patched"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply", action="store_true", help="write changes (default: dry-run)"
    )
    ap.add_argument("--diff", action="store_true", help="print unified diffs")
    ap.add_argument(
        "--with-assertion",
        action="store_true",
        help="also embed a build-time leak assertion (off by default; see module docstring)",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=INSTANCE_DIR,
        help=f"directory containing instance_*/Dockerfile (default: {INSTANCE_DIR})",
    )
    args = ap.parse_args()

    if not args.root.is_dir():
        print(f"error: {args.root} is not a directory", file=sys.stderr)
        return 2

    counts = {"patched": 0, "already-patched": 0, "no-checkout": 0, "multi-checkout": 0}
    examples: dict[str, list[str]] = {k: [] for k in counts}

    for dockerfile in sorted(args.root.glob("*/Dockerfile")):
        text = dockerfile.read_text()
        new_text, status = patch_text(text, with_assertion=args.with_assertion)
        counts[status] += 1
        if len(examples[status]) < 3:
            examples[status].append(dockerfile.parent.name)

        if new_text is None:
            continue

        if args.diff:
            diff = difflib.unified_diff(
                text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=str(dockerfile.relative_to(args.root)) + " (before)",
                tofile=str(dockerfile.relative_to(args.root)) + " (after)",
                n=3,
            )
            sys.stdout.writelines(diff)

        if args.apply:
            dockerfile.write_text(new_text)

    print()
    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"=== {mode} summary across {sum(counts.values())} Dockerfiles ===")
    for status, n in counts.items():
        print(f"  {status:18s} {n:4d}", end="")
        if examples[status]:
            print(f"  e.g. {examples[status][0]}")
        else:
            print()
    if not args.apply and counts["patched"] > 0:
        print("\nRe-run with --apply to write the changes.")
    return 0 if counts["no-checkout"] == 0 and counts["multi-checkout"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
