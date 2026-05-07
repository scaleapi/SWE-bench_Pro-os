# `gen_bash_script_setup.py`

Generates a self-contained bash setup script for a SWE-bench Pro Python task.

Key features:

- **All apt blocks preserved.** Some Dockerfiles have two separate `RUN apt-get install`
  blocks; `gen_bash_script_setup.py` concatenates them all.
- **Venv at `/opt/venv`.** The venv is placed outside `/app`, so `git clean -fdx` (run
  during PREPROCESS) cannot accidentally delete it.
- **`--skip-repo-setup` flag.** Lets you skip the REPO + PREPROCESS sections when your
  harness has already cloned the repo and reset it to `base_commit`.
- **Parsed apt packages.** `SetupSections.apt_packages` exposes the set of debian package
  names extracted from all apt blocks — useful for auditing system dependencies without
  parsing bash.
- **Batch mode driven by the HF dataset.** `--all-python` and `--list-python` filter on
  `repo_language == "python"` from the HuggingFace dataset instead of guessing from the
  `FROM` line.

The same four correctness fixes from the prior debugging session apply here:
pip→uv translation, setuptools date-pin bypass for editable installs, old `ENV KEY VALUE`
syntax normalization, and `--default-timeout` stripping.

---

## Quick CLI usage

```bash
# Convert a single instance (prints to stdout)
python dataset_preprocessing/gen_bash_script_setup.py --instance-id <iid>

# Write to a file
python dataset_preprocessing/gen_bash_script_setup.py --instance-id <iid> --output setup.sh

# Skip apt (base image already has system deps) and repo setup (caller pre-cloned)
python dataset_preprocessing/gen_bash_script_setup.py --instance-id <iid> --skip-apt --skip-repo-setup

# Bulk-generate all 235 Python instances
python dataset_preprocessing/gen_bash_script_setup.py --all-python --output-dir scripts/

# List all Python instance ids (from the HF dataset)
python dataset_preprocessing/gen_bash_script_setup.py --list-python
```

All flags:

| Flag | Default | Effect |
|------|---------|--------|
| `--instance-id ID` | — | Convert a single instance (mutually exclusive with the two batch modes) |
| `--all-python` | — | Convert every Python instance from the HF dataset |
| `--list-python` | — | Print every Python instance_id and exit |
| `--output PATH` | stdout | Output path (single-instance mode) |
| `--output-dir PATH` | required for `--all-python` | Output directory |
| `--skip-apt` | off | Omit the `# === APT ===` section |
| `--skip-repo-setup` | off | Omit `# === REPO ===` and `# === PREPROCESS ===` sections |
| `--no-date-pin` | off | Strip pypi-timemachine boilerplate without adding `UV_EXCLUDE_NEWER` |

> **Note:** `--all-python` and `--list-python` require the `datasets` package
> (`pip install datasets`). Single-instance mode has no extra dependency.

---

## Output structure

Generated scripts use these section markers, in this order:

```
# === ENV ===           export lines from both Dockerfiles (always)
# === APT ===           all apt-get install blocks concatenated (skippable)
# === REPO ===          git clone, checkout, submodule init (skippable)
# === PREPROCESS ===    git reset --hard <base_commit> + git clean (skippable)
# === UV VENV ===       install uv, create venv at /opt/venv (always)
# === PYTHON SETUP ===  pip→uv installs from EOFBUILD heredoc (always)
```

The PREPROCESS section resets the working tree to the task's `base_commit` (the first
SHA in the instance id) before the venv is created. The venv lives at `/opt/venv` rather
than `/app/.venv`, so this reset — which runs `git clean -fdx` — cannot wipe it.

When `--skip-repo-setup` is set, the generated script assumes `/app` already exists and
`HEAD == base_commit`. The script enters at `# === UV VENV ===`.

---

## Example 1 — Convert a single instance

```bash
python dataset_preprocessing/gen_bash_script_setup.py \
    --instance-id instance_ansible__ansible-bec27fb4c0a40c5f8bbcf26a475704227d65ee73-v30a923fb5c164d6cd18280c02422f75e611e8fb2 \
    --output ./setup.sh
chmod +x ./setup.sh
docker run --rm -v $(pwd)/setup.sh:/setup.sh ubuntu:24.04 bash /setup.sh
```

---

## Example 2 — Bulk-generate for all Python instances

```bash
python dataset_preprocessing/gen_bash_script_setup.py --all-python --output-dir scripts/
# → writes 235 scripts (one per Python instance that has local Dockerfiles)
```

For environments where system deps are pre-installed:

```bash
python dataset_preprocessing/gen_bash_script_setup.py --all-python --output-dir scripts/ --skip-apt
```

---

## Example 3 — Use the Python API

```python
import sys
from pathlib import Path

from dataset_preprocessing.gen_bash_script_setup import build_sections, load_local_dockerfiles

iid = "instance_ansible__ansible-bec27fb4c0a40c5f8bbcf26a475704227d65ee73-v30a923fb5c164d6cd18280c02422f75e611e8fb2"
base, inst = load_local_dockerfiles(iid)
sections = build_sections(iid, base, inst)

# Render the full script
Path("setup.sh").write_text(sections.to_bash())

# Or render only the parts you need
partial = sections.to_bash(skip_apt=True, skip_repo_setup=True)

# Inspect parsed data
print("Python version :", sections.python_version)
print("APT packages   :", sorted(sections.apt_packages))
print("Base steps     :", len(sections.base_runs))
```

### `SetupSections` fields

| Field | Type | Contents |
|-------|------|----------|
| `instance_id` | `str` | The task id |
| `python_version` | `str` | Python version from the base image, e.g. `"3.11"` or `"3.12.2"` |
| `env_exports` | `list[str]` | `export KEY=VALUE` lines from both Dockerfiles |
| `apt_installs` | `list[str]` | Raw apt shell command(s) — one entry per `RUN apt-get install` block |
| `apt_packages` | `set[str]` | Parsed debian package names (from all apt blocks combined) |
| `base_runs` | `list[str]` | Non-apt steps from the base Dockerfile: `mkdir /app`, `git clone`, `git checkout`, extras. `pip` rewritten to `uv pip`; lines that would call uv before it's installed are dropped. |
| `preprocess_body` | `str` | Body of the EOFPREP heredoc: resets working tree to `base_commit` |
| `python_setup_body` | `str` | Body of the EOFBUILD heredoc: pip→uv installs, pypi-timemachine replaced by `UV_EXCLUDE_NEWER`, editable-install fix applied |

---

## Relationship to `collect_all_system_deps.py`

[`collect_all_system_deps.py`](collect_all_system_deps.py) scans `scripts/*.sh` to regenerate
`install_system_deps.sh`. It imports `parse_apt_packages` and `extract_apt_blocks_from_script`
directly from `gen_bash_script_setup.py`, so both scripts share a single apt parser.

To regenerate `install_system_deps.sh` after updating the scripts:

```bash
python dataset_preprocessing/gen_bash_script_setup.py --all-python --output-dir scripts/
python dataset_preprocessing/collect_all_system_deps.py
```
