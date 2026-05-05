#!/usr/bin/env python3
"""Convert a SWE-bench Pro task into a single bash setup script.

The benchmark normally provisions a per-task environment via two Dockerfiles
(base + instance). This utility extracts the equivalent shell commands so
the setup can run inside an already-existing container instead.

Scope: Python tasks only (base FROM matches python:*). 235 instances.

Usage:
    convert_to_setup_script.py --list-python
    convert_to_setup_script.py --instance-id <iid> --output setup.sh
    convert_to_setup_script.py --all-python --output-dir scripts/
    convert_to_setup_script.py --instance-id <iid> --skip-apt --no-pypi-timemachine
"""
import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = REPO_ROOT / "dockerfiles" / "base_dockerfile"
INSTANCE_DIR = REPO_ROOT / "dockerfiles" / "instance_dockerfile"

FROM_RE = re.compile(r"^\s*FROM\s+(\S+)", re.MULTILINE)
PYTHON_IMAGE_RE = re.compile(r"(^|/)python:")
HEREDOC_OPEN_RE = re.compile(r"<<'?(\w+)'?")
APT_RE = re.compile(r"\bapt(-get)?\s+(install|update)\b|\bapk\s+add\b|\byum\s+install\b|\bdnf\s+install\b")
REPO_RE = re.compile(r"\bgit\s+(clone|checkout|submodule|reset|rev-list)\b")
MKCD_RE = re.compile(r"^(mkdir|cd)\b", re.MULTILINE)


def is_python_dockerfile(base_content: str) -> bool:
    m = FROM_RE.search(base_content)
    if not m:
        return False
    return bool(PYTHON_IMAGE_RE.search(m.group(1)))


def list_local_instances() -> list[str]:
    return sorted(p.name for p in BASE_DIR.iterdir() if p.is_dir())


def load_local(iid: str) -> tuple[str, str]:
    return (
        (BASE_DIR / iid / "Dockerfile").read_text(),
        (INSTANCE_DIR / iid / "Dockerfile").read_text(),
    )


def iter_instructions(content: str):
    """Yield raw multi-line Dockerfile instructions.

    Handles BuildKit heredocs (``<<'TAG'`` ... ``TAG``) and backslash
    continuations. Skips comments and blank lines.
    """
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        instr = [line]
        heredoc = HEREDOC_OPEN_RE.search(line)
        if heredoc:
            terminator = heredoc.group(1)
            i += 1
            while i < len(lines):
                instr.append(lines[i])
                if lines[i].strip() == terminator:
                    break
                i += 1
        else:
            while line.rstrip().endswith("\\") and i + 1 < len(lines):
                i += 1
                line = lines[i]
                instr.append(line)
        yield "\n".join(instr)
        i += 1


def _split_keyword(instr: str) -> tuple[str, str]:
    parts = instr.split(None, 1)
    if not parts:
        return "", ""
    keyword = parts[0].upper()
    rest = parts[1] if len(parts) > 1 else ""
    return keyword, rest


def parse_base(content: str, *, skip_apt: bool = False) -> tuple[list[str], list[str]]:
    """Return (env_exports, run_commands) extracted from the base Dockerfile.

    The ``skip_apt`` flag drops any RUN body containing ``apt-get install``.
    Prefer :func:`build_sections` for finer-grained access.
    """
    envs: list[str] = []
    runs: list[str] = []
    for instr in iter_instructions(content):
        first_line = instr.split("\n", 1)[0]
        keyword, rest_first = _split_keyword(first_line)
        if keyword in ("FROM", "ENTRYPOINT", "CMD", "LABEL", "EXPOSE", "USER", "ARG"):
            continue
        if keyword == "WORKDIR":
            path = rest_first.strip()
            runs.append(f"mkdir -p {path} && cd {path}")
            continue
        if keyword == "ENV":
            _, rest = _split_keyword(instr)
            envs.append(f"export {rest}")
            continue
        if keyword == "RUN":
            _, body = _split_keyword(instr)
            if skip_apt and "apt-get install" in body:
                continue
            runs.append(body)
            continue
    return envs, runs


def _classify_base_run(body: str) -> str:
    """Bucket a base-layer RUN body into 'apt', 'repo', or 'other'."""
    if APT_RE.search(body):
        return "apt"
    if REPO_RE.search(body):
        return "repo"
    if MKCD_RE.search(body) and "pip" not in body:
        return "repo"
    return "other"


def _strip_shebang(body: str) -> str:
    lines = body.split("\n")
    if lines and lines[0].lstrip().startswith("#!"):
        lines = lines[1:]
    return "\n".join(lines).strip("\n")


def parse_instance(content: str) -> tuple[list[str], str, str]:
    """Return (env_exports, preprocess_body, build_body) from instance Dockerfile."""
    envs: list[str] = []
    preprocess = ""
    build = ""
    for instr in iter_instructions(content):
        first_line = instr.split("\n", 1)[0]
        keyword, rest_first = _split_keyword(first_line)
        if keyword in ("FROM", "ENTRYPOINT", "CMD", "LABEL", "EXPOSE", "USER", "ARG", "WORKDIR"):
            continue
        if keyword == "ENV":
            _, rest = _split_keyword(instr)
            envs.append(f"export {rest}")
            continue
        if keyword != "RUN":
            continue
        if "<<'EOFPREP'" in first_line:
            preprocess = _extract_heredoc_body(instr, "EOFPREP")
            continue
        if "<<'EOFBUILD'" in first_line:
            build = _extract_heredoc_body(instr, "EOFBUILD")
            continue
        body = rest_first.strip()
        if re.fullmatch(r"chmod\s+\+x\s+/(preprocess|build)\.sh", body):
            continue
        if re.fullmatch(r"/(preprocess|build)\.sh", body):
            continue
    return envs, _strip_shebang(preprocess), _strip_shebang(build)


def _extract_heredoc_body(instr: str, terminator: str) -> str:
    lines = instr.split("\n")
    body: list[str] = []
    for line in lines[1:]:
        if line.strip() == terminator:
            break
        body.append(line)
    return "\n".join(body)


def strip_pypi_timemachine(build_body: str) -> str:
    """Remove the pypi-timemachine setup lines from a build script body.

    Leaves the actual ``pip install -r ...`` lines untouched, so version
    correctness still depends on whatever the project's requirements files
    pin. Without timemachine, pip resolves from today's PyPI, which may
    yield newer versions than the benchmark was authored against.
    """
    keep: list[str] = []
    for line in build_body.split("\n"):
        s = line.strip()
        if s == "pip install pypi-timemachine":
            continue
        if s.startswith("pypi-timemachine "):
            continue
        if s.startswith("pip config set global.index-url http://127.0.0.1:9876"):
            continue
        if s == "sleep 3":
            continue
        keep.append(line)
    return "\n".join(keep)


@dataclass
class SetupSections:
    """Parsed pieces of a task's setup, separated by phase.

    Each list/string is already a bash snippet ready to ``exec``. Use the
    ``*_bash()`` helpers to render a single phase, or :meth:`to_bash` to
    render the whole script. Dropping a phase is a matter of leaving it
    out when you compose your own script.
    """

    instance_id: str
    env_exports: list[str] = field(default_factory=list)
    apt_install: list[str] = field(default_factory=list)
    repo_setup: list[str] = field(default_factory=list)
    other_base_runs: list[str] = field(default_factory=list)
    preprocess_body: str = ""
    python_setup_body: str = ""

    def env_bash(self) -> str:
        return "\n".join(self.env_exports)

    def system_setup_bash(self) -> str:
        return "\n\n".join(self.apt_install)

    def repo_setup_bash(self) -> str:
        return "\n".join(self.repo_setup)

    def other_base_bash(self) -> str:
        return "\n".join(self.other_base_runs)

    def preprocess_bash(self) -> str:
        return self.preprocess_body

    def python_setup_bash(self) -> str:
        return self.python_setup_body

    def to_bash(self, *, skip_apt: bool = False) -> str:
        out: list[str] = [
            "#!/bin/bash",
            f"# Setup for SWE-bench Pro instance: {self.instance_id}",
            "# Generated by helper_code/convert_to_setup_script.py",
            "set -e",
            "",
        ]
        if self.env_exports:
            out.append("# === ENV ===")
            out.extend(self.env_exports)
            out.append("")
        if not skip_apt and self.apt_install:
            out.append("# === SYSTEM SETUP (apt) ===")
            out.extend(self.apt_install)
            out.append("")
        if self.repo_setup:
            out.append("# === REPO (clone + checkpoint checkout) ===")
            out.extend(self.repo_setup)
            out.append("")
        if self.other_base_runs:
            out.append("# === BASE EXTRAS ===")
            out.extend(self.other_base_runs)
            out.append("")
        if self.preprocess_body:
            out.append("# === PREPROCESS (reset to task base_commit) ===")
            out.append(self.preprocess_body)
            out.append("")
        if self.python_setup_body:
            out.append("# === PYTHON SETUP (pip install) ===")
            out.append(self.python_setup_body)
            out.append("")
        return "\n".join(out)


def build_sections(
    iid: str,
    *,
    base_content: str | None = None,
    instance_content: str | None = None,
    no_pypi_timemachine: bool = False,
) -> SetupSections:
    """Build a :class:`SetupSections` for ``iid``.

    By default loads the base + instance Dockerfiles from the local
    ``dockerfiles/`` tree. Pass ``base_content`` / ``instance_content``
    explicitly to source them from somewhere else (e.g. an in-memory
    string from a database row).
    """
    if base_content is None or instance_content is None:
        loaded_base, loaded_instance = load_local(iid)
        base_content = base_content if base_content is not None else loaded_base
        instance_content = instance_content if instance_content is not None else loaded_instance

    base_envs, base_runs = parse_base(base_content, skip_apt=False)
    instance_envs, preprocess_body, build_body = parse_instance(instance_content)
    if no_pypi_timemachine:
        build_body = strip_pypi_timemachine(build_body)

    apt: list[str] = []
    repo: list[str] = []
    other: list[str] = []
    for body in base_runs:
        bucket = _classify_base_run(body)
        {"apt": apt, "repo": repo, "other": other}[bucket].append(body)

    return SetupSections(
        instance_id=iid,
        env_exports=base_envs + instance_envs,
        apt_install=apt,
        repo_setup=repo,
        other_base_runs=other,
        preprocess_body=preprocess_body,
        python_setup_body=build_body,
    )


def generate_script(
    iid: str,
    base_content: str,
    instance_content: str,
    *,
    skip_apt: bool,
    no_pypi_timemachine: bool,
) -> str:
    """Backwards-compatible wrapper around :func:`build_sections`."""
    sections = build_sections(
        iid,
        base_content=base_content,
        instance_content=instance_content,
        no_pypi_timemachine=no_pypi_timemachine,
    )
    return sections.to_bash(skip_apt=skip_apt)


def cmd_list_python(args) -> int:
    for iid in list_local_instances():
        try:
            base, _ = load_local(iid)
        except FileNotFoundError:
            continue
        if is_python_dockerfile(base):
            print(iid)
    return 0


def cmd_convert_one(args) -> int:
    iid = args.instance_id
    base, instance = load_local(iid)
    if not is_python_dockerfile(base):
        print(
            f"Warning: {iid} is not a Python instance (FROM is not python:*). "
            "Generating anyway, but the build script may not apply.",
            file=sys.stderr,
        )
    script = generate_script(
        iid,
        base,
        instance,
        skip_apt=args.skip_apt,
        no_pypi_timemachine=args.no_pypi_timemachine,
    )
    if args.output:
        Path(args.output).write_text(script)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(script)
    return 0


def cmd_all_python(args) -> int:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0
    for iid in list_local_instances():
        try:
            base, instance = load_local(iid)
        except FileNotFoundError:
            skipped += 1
            continue
        if not is_python_dockerfile(base):
            continue
        script = generate_script(
            iid,
            base,
            instance,
            skip_apt=args.skip_apt,
            no_pypi_timemachine=args.no_pypi_timemachine,
        )
        (out_dir / f"{iid}.sh").write_text(script)
        count += 1
    print(f"Wrote {count} setup scripts to {out_dir}", file=sys.stderr)
    if skipped:
        print(f"Skipped {skipped} instances missing dockerfiles", file=sys.stderr)
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--instance-id", help="Convert a single instance.")
    mode.add_argument("--all-python", action="store_true", help="Convert every Python instance.")
    mode.add_argument("--list-python", action="store_true", help="Print all Python instance ids and exit.")
    p.add_argument("--output", help="Output path (single-instance mode). Defaults to stdout.")
    p.add_argument("--output-dir", help="Output directory (--all-python mode).")
    p.add_argument("--skip-apt", action="store_true", help="Omit the apt-get block (host container already has system tools).")
    p.add_argument(
        "--no-pypi-timemachine",
        action="store_true",
        help="Strip pypi-timemachine lines from the build script. Risks resolving newer dep versions than the benchmark expects.",
    )
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
