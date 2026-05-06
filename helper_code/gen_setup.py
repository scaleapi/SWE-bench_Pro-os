#!/usr/bin/env python3
"""Generate a bash setup script for a SWE-bench Pro Python task.

Leaner alternative to ``convert_dockerfile_setup_to_bash.py``. Produces:

  1. ENV exports (both Dockerfiles, ``ENV K V`` normalized to ``K=V``)
  2. APT      — concatenation of ALL ``RUN apt-get …`` blocks (skippable)
  3. REPO     — base Dockerfile non-apt RUN/WORKDIR steps (skippable)
  4. PREPROCESS — EOFPREP heredoc body (skippable with REPO)
  5. UV VENV  — uv install + venv at ``/opt/venv`` (outside /app, immune to ``git clean``)
  6. PYTHON   — EOFBUILD heredoc body, transformed (pip→uv, date pin, editable fix)

Usage:
    gen_setup.py --instance-id <iid>
    gen_setup.py --instance-id <iid> --output setup.sh
    gen_setup.py --instance-id <iid> --skip-apt --skip-repo-setup
    gen_setup.py --all-python --output-dir scripts/
    gen_setup.py --list-python
"""
import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = REPO_ROOT / "dockerfiles" / "base_dockerfile"
INST_DIR = REPO_ROOT / "dockerfiles" / "instance_dockerfile"
VENV_PATH = "/opt/venv"

FROM_RE = re.compile(r"^FROM\s+(\S+)", re.M)
PYIMG_RE = re.compile(r"(^|/)python:")
PYVER_RE = re.compile(r"python:(\d+(?:\.\d+){0,2})")
ENV_RE = re.compile(r"^ENV\s+(.+)$", re.M)
HEREDOC_RE_TPL = r"<<'?{tag}'?[^\n]*\n(.*?)\n\s*{tag}\s*$"
TIMEMACHINE_RE = re.compile(r"pypi-timemachine\s+(\d{4}-\d{2}-\d{2})")
TIMEOUT_RE = re.compile(r"\s+--default-timeout=\d+")
EDITABLE_RE = re.compile(r"^uv pip install -e \.$", re.M)

_PIP_VERBS = "install|uninstall|freeze|list|show|cache|index|download|wheel"
_PYTHON_PIP_RE = re.compile(r"^(\s*)python3?\s+-m\s+pip\s+(.*)$")
_PIP_VERB_RE = re.compile(rf"^(\s*)pip\s+({_PIP_VERBS})\b(.*)$")
_PIP_INDEX_URL_RE = re.compile(r"^(\s*)pip\s+config\s+set\s+global\.index-url\s+(\S+)\s*$")

_APT_BACKTICK_COMMENT_RE = re.compile(r"`#[^`]*`")
_DEB_PKG_RE = re.compile(r"[a-z][a-z0-9.+\-]{0,39}")
_APT_NON_PKG_TOKENS = {
    "apt-get", "apt", "update", "install", "-y", "-qq", "&&", "||", "\\",
    "rm", "-rf", "/var/lib/apt/lists/*",
}

_TIMEMACHINE_DROP_EXACT = {"pip install pypi-timemachine", "sleep 3"}
_TIMEMACHINE_DROP_PREFIX = (
    "pypi-timemachine ",
    "pip config set global.index-url http://127.0.0.1:9876",
)


def is_python_dockerfile(base_content: str) -> bool:
    m = FROM_RE.search(base_content)
    return bool(m and PYIMG_RE.search(m.group(1)))


def get_python_version(base_content: str) -> str:
    m = FROM_RE.search(base_content)
    if not m:
        return ""
    pm = PYVER_RE.search(m.group(1))
    return pm.group(1) if pm else ""


def list_local_instances() -> list[str]:
    return sorted(p.name for p in BASE_DIR.iterdir() if p.is_dir())


def load_local_dockerfiles(iid: str) -> tuple[str, str]:
    return (
        (BASE_DIR / iid / "Dockerfile").read_text(),
        (INST_DIR / iid / "Dockerfile").read_text(),
    )


def normalize_env(kv: str) -> str:
    """``ENV KEY VALUE`` (no =) → ``KEY=VALUE``. Otherwise pass through."""
    if "=" in kv:
        return kv
    parts = kv.split(None, 1)
    return f"{parts[0]}={parts[1]}" if len(parts) == 2 else kv


def to_uv(line: str) -> str:
    """Translate pip-based commands to uv equivalents (single line)."""
    m = _PIP_INDEX_URL_RE.match(line)
    if m:
        indent, url = m.group(1), m.group(2)
        return f"{indent}export UV_INDEX_URL={url}\n{indent}export PIP_INDEX_URL={url}"
    m = _PYTHON_PIP_RE.match(line)
    if m:
        return f"{m.group(1)}uv pip {TIMEOUT_RE.sub('', m.group(2))}"
    m = _PIP_VERB_RE.match(line)
    if m:
        return f"{m.group(1)}uv pip {m.group(2)}{TIMEOUT_RE.sub('', m.group(3))}"
    return line


def to_uv_block(text: str) -> str:
    return "\n".join(to_uv(line) for line in text.split("\n"))


def iter_run_steps(content: str) -> list[str]:
    """Yield each Dockerfile RUN/WORKDIR translated to bash. Skips heredoc RUNs."""
    out: list[str] = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("RUN ") and "<<" not in line:
            buf = [line[4:]]
            while line.rstrip().endswith("\\") and i + 1 < len(lines):
                i += 1
                line = lines[i]
                buf.append(line)
            out.append("\n".join(buf))
        elif line.startswith("WORKDIR "):
            out.append(f"cd {line[len('WORKDIR '):].strip()}")
        i += 1
    return out


def is_apt_step(step: str) -> bool:
    head = step.lstrip().split(None, 1)
    return bool(head) and head[0] in ("apt-get", "apt")


def split_apt_vs_other(steps: list[str]) -> tuple[list[str], list[str]]:
    apt_blocks: list[str] = []
    other: list[str] = []
    for s in steps:
        (apt_blocks if is_apt_step(s) else other).append(s)
    return apt_blocks, other


def extract_apt_blocks_from_script(text: str) -> list[str]:
    """Find every backslash-continued ``apt-get install -y`` block in a bash script.

    Used by collect_all_system_deps.py, which scans generated ``scripts/*.sh``.
    A block starts at any line containing ``apt-get install -y`` and continues
    while the previous line ended with ``\\``.
    """
    blocks: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if "apt-get install -y" not in lines[i]:
            i += 1
            continue
        buf: list[str] = []
        while i < len(lines):
            raw = lines[i].rstrip()
            buf.append(raw)
            i += 1
            if not raw.endswith("\\"):
                break
        blocks.append("\n".join(buf))
    return blocks


def parse_apt_packages(blocks: list[str]) -> set[str]:
    """Extract debian package names from a list of ``apt-get install …`` shell commands.

    Shared with helper_code/collect_all_system_deps.py — single source of truth.
    Tokenization rules: strip backtick-comments, only keep tokens after
    ``install -y``/``install`` until ``&&``/``||``, drop known non-package tokens
    and anything not matching the deb package name shape.
    """
    pkgs: set[str] = set()
    for block in blocks:
        text = _APT_BACKTICK_COMMENT_RE.sub("", block)
        # Only consider the part after the FIRST `install` keyword in this block.
        if "install" not in text:
            continue
        text = text.split("install", 1)[1]
        # Stop at the first chained command after the package list.
        for stopper in (" && ", " || "):
            if stopper in text:
                text = text.split(stopper, 1)[0]
        for token in text.replace("\\\n", " ").split():
            token = token.strip().rstrip("\\")
            if not token or token in _APT_NON_PKG_TOKENS:
                continue
            if token.startswith("-"):
                continue
            if _DEB_PKG_RE.fullmatch(token):
                pkgs.add(token)
    return pkgs


def extract_heredoc(content: str, tag: str) -> str:
    m = re.search(HEREDOC_RE_TPL.format(tag=tag), content, re.S | re.M)
    if not m:
        return ""
    body = m.group(1).split("\n")
    if body and body[0].lstrip().startswith("#!"):
        body = body[1:]
    return "\n".join(body).strip("\n")


def drop_pypi_timemachine(body: str) -> str:
    keep: list[str] = []
    for line in body.split("\n"):
        s = line.strip()
        if s in _TIMEMACHINE_DROP_EXACT or any(s.startswith(p) for p in _TIMEMACHINE_DROP_PREFIX):
            continue
        keep.append(line)
    return "\n".join(keep)


def transform_build(body: str, *, no_date_pin: bool) -> str:
    m = TIMEMACHINE_RE.search(body)
    date = m.group(1) if m else ""
    body = drop_pypi_timemachine(body)
    body = to_uv_block(body)
    if date and not no_date_pin:
        body = f"export UV_EXCLUDE_NEWER={date}\n{body}"
    # Bug 1: editable installs need modern setuptools, bypass UV_EXCLUDE_NEWER.
    body = EDITABLE_RE.sub(
        "uv pip install --upgrade pip wheel\n"
        "env -u UV_EXCLUDE_NEWER uv pip install --upgrade setuptools\n"
        "env -u UV_EXCLUDE_NEWER uv pip install -e .",
        body,
    )
    return body


@dataclass
class SetupSections:
    instance_id: str
    python_version: str = ""
    env_exports: list[str] = field(default_factory=list)
    apt_installs: list[str] = field(default_factory=list)  # raw shell commands
    apt_packages: set[str] = field(default_factory=set)    # parsed pkg names
    base_runs: list[str] = field(default_factory=list)
    preprocess_body: str = ""
    python_setup_body: str = ""

    def uv_env_bash(self) -> str:
        if not self.python_version:
            return ""
        return "\n".join([
            "if ! command -v uv &>/dev/null; then",
            "    curl -LsSf https://astral.sh/uv/install.sh | sh",
            '    source "$HOME/.local/bin/env" bash',
            "fi",
            'export PATH="$HOME/.local/bin:$PATH"',
            f"uv venv --python {self.python_version} {VENV_PATH}",
            f"source {VENV_PATH}/bin/activate",
        ])

    def to_bash(self, *, skip_apt: bool = False, skip_repo_setup: bool = False) -> str:
        out: list[str] = ["#!/bin/bash", f"# Setup for SWE-bench Pro instance: {self.instance_id}"]
        if self.python_version:
            out.append(f"# Python version: {self.python_version}")
        out += ["# Generated by helper_code/gen_setup.py", "set -e", ""]
        if self.env_exports:
            out += ["# === ENV ===", *self.env_exports, ""]
        if not skip_apt and self.apt_installs:
            out += ["# === APT ===", " && \\\n  ".join(self.apt_installs), ""]
        if not skip_repo_setup:
            if self.base_runs:
                out += ["# === REPO ===", *self.base_runs, ""]
            if self.preprocess_body:
                out += ["# === PREPROCESS ===", self.preprocess_body, ""]
        uv = self.uv_env_bash()
        if uv:
            out += ["# === UV VENV ===", uv, ""]
        if self.python_setup_body:
            out += ["# === PYTHON SETUP ===", self.python_setup_body, ""]
        return "\n".join(out)


def build_sections(
    iid: str,
    base: str,
    inst: str,
    *,
    no_date_pin: bool = False,
) -> SetupSections:
    apt_blocks, other_steps = split_apt_vs_other(iter_run_steps(base))
    # Bug 2: drop any uv-pip line from base_runs (uv not yet installed at this stage).
    translated = [to_uv_block(s) for s in other_steps]
    base_runs = [
        s for s in translated
        if not any(line.lstrip().startswith("uv pip ") for line in s.splitlines())
    ]
    env_exports = [
        "export " + normalize_env(m.group(1))
        for m in ENV_RE.finditer(base + "\n" + inst)
    ]
    return SetupSections(
        instance_id=iid,
        python_version=get_python_version(base),
        env_exports=env_exports,
        apt_installs=apt_blocks,
        apt_packages=parse_apt_packages(apt_blocks),
        base_runs=base_runs,
        preprocess_body=extract_heredoc(inst, "EOFPREP"),
        python_setup_body=transform_build(extract_heredoc(inst, "EOFBUILD"), no_date_pin=no_date_pin),
    )


def iter_python_instance_ids():
    """Yield instance_ids from the HF dataset where ``repo_language == 'python'``.

    Lazy-imports ``datasets`` so single-instance mode works without it.
    """
    from datasets import load_dataset
    for row in load_dataset("ScaleAI/SWE-bench_Pro", split="test"):
        if row["repo_language"] == "python":
            yield row["instance_id"]


def cmd_list_python(_args) -> int:
    for iid in iter_python_instance_ids():
        print(iid)
    return 0


def _generate_one(iid: str, args) -> str | None:
    try:
        base, inst = load_local_dockerfiles(iid)
    except FileNotFoundError:
        return None
    if not is_python_dockerfile(base):
        return None
    sections = build_sections(iid, base, inst, no_date_pin=args.no_date_pin)
    return sections.to_bash(skip_apt=args.skip_apt, skip_repo_setup=args.skip_repo_setup)


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
