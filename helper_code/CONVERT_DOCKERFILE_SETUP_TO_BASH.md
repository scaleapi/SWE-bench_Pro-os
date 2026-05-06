# `convert_dockerfile_setup_to_bash.py`

A simpler alternative to [`convert_to_setup_script.py`](CONVERT_TO_SETUP_SCRIPT.md).
Same outer loop (instance_id → base + instance Dockerfile contents),
same CLI flags, same kind of output — but ~half the code, with a few
targeted regexes instead of general Dockerfile-instruction iteration.

**Uses `uv` for all Python install steps in the generated script.** Every
`pip install` / `python -m pip` from the original Dockerfile build script
is rewritten to `uv pip install`. The `pypi-timemachine` proxy boilerplate
is replaced by `export UV_EXCLUDE_NEWER=<date>`, which pins UV's resolver
to the same cutoff date without requiring a background server. You're
expected to create and activate the venv yourself before running the
script — the generated header tells you the exact command to use, e.g.

```bash
uv venv --python 3.11 && source .venv/bin/activate
bash setup.sh
```

The simplification works because the benchmark's Dockerfiles follow a
rigid structure:

- **Base Dockerfile**: one `FROM`, one multi-line `RUN apt-get …`, one
  or more `RUN git …` lines (clone, checkout, optional submodule), and
  occasionally a few extras (e.g. `ln -sf …`, `pip install --upgrade …`).
- **Instance Dockerfile**: some `ENV` lines, plus two inline heredocs
  `RUN cat <<'EOFPREP' > /preprocess.sh … EOFPREP` and
  `RUN cat <<'EOFBUILD' > /build.sh … EOFBUILD`.

Scope: Python tasks only (base `FROM` matches `python:*`).

---

## Quick CLI usage

```bash
python helper_code/convert_dockerfile_setup_to_bash.py --list-python
python helper_code/convert_dockerfile_setup_to_bash.py \
    --instance-id <iid> --output setup.sh
python helper_code/convert_dockerfile_setup_to_bash.py \
    --all-python --output-dir scripts/
```

Flags: `--skip-apt` (omit the apt-get block), `--no-date-pin`
(strip the pypi-timemachine boilerplate *without* adding `UV_EXCLUDE_NEWER`,
resolving from today's PyPI — only use this if you've verified the project's
own pinning is strict enough).

---

## Example 1 — Fetch a task from the dataset and convert it

The benchmark dataset ships in this repo as a local JSONL:
[`helper_code/sweap_eval_full_v2.jsonl`](sweap_eval_full_v2.jsonl). Each
line has `instance_id`, `base_dockerfile`, and `instance_dockerfile`
columns (full Dockerfile contents inline) plus task metadata
(`base_commit`, `problem_statement`, `FAIL_TO_PASS`, …).

Fetch one task and convert it in a single script:

```python
import json
from pathlib import Path
import sys

# Make `helper_code` importable when running from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent / "helper_code"))
from convert_dockerfile_setup_to_bash import build_sections

JSONL = Path("helper_code/sweap_eval_full_v2.jsonl")
TARGET_IID = "instance_ansible__ansible-bec27fb4c0a40c5f8bbcf26a475704227d65ee73-v30a923fb5c164d6cd18280c02422f75e611e8fb2"

# 1. Fetch the task row.
def fetch_task(jsonl_path: Path, instance_id: str) -> dict:
    with jsonl_path.open() as f:
        for line in f:
            obj = json.loads(line)
            if obj["instance_id"] == instance_id:
                return obj
    raise KeyError(instance_id)

task = fetch_task(JSONL, TARGET_IID)
print(f"Task: {task['repo']} @ {task['base_commit']}")

# 2. Convert. Pass the Dockerfile contents in directly, so this script
#    does not depend on the local `dockerfiles/` tree.
sections = build_sections(
    TARGET_IID,
    base_content=task["base_dockerfile"],
    instance_content=task["instance_dockerfile"],
    # no_date_pin=True  # omit UV_EXCLUDE_NEWER if you want today's PyPI
)

# 3. Render and save.
Path("setup.sh").write_text(sections.to_bash())
```

If you'd rather load from the local `dockerfiles/` tree instead of the
JSONL, omit `base_content`/`instance_content` and `build_sections` will
read them by `instance_id`:

```python
sections = build_sections(TARGET_IID)  # reads dockerfiles/{base,instance}_dockerfile/<iid>/Dockerfile
```

---

## Example 2 — Use the Python functions in another module

The dataclass exposes one bash-rendering method per phase, so you can
compose your own driver. Typical pattern: your container already has
the system tools, so skip the apt block and just run the repo +
preprocess + python phases.

```python
from convert_dockerfile_setup_to_bash import build_sections

sections = build_sections(
    "instance_ansible__ansible-bec27fb4...",
    # no_date_pin=True  # omit UV_EXCLUDE_NEWER if you want today's PyPI
)

# Inspect what was parsed
print("env exports :", len(sections.env_exports))
print("apt block   :", "yes" if sections.apt_install else "no")
print("base steps  :", len(sections.base_runs))   # repo clone, checkout, any extras
print("preprocess  :", len(sections.preprocess_body), "chars")
print("python deps :", len(sections.python_setup_body), "chars")

# Compose only the phases you need
my_setup = "\n\n".join([
    sections.env_bash(),
    sections.base_runs_bash(),     # mkdir, git clone, checkpoint checkout
    sections.preprocess_bash(),    # reset to task base_commit
    sections.python_setup_bash(),  # pip installs (incl. pypi-timemachine)
])

# Or: render the whole script but skip apt because your container has it.
full_script = sections.to_bash(skip_apt=True)
```

The fields on `SetupSections`:

| Field | Type | Contents |
|---|---|---|
| `instance_id` | `str` | The task id |
| `python_version` | `str` | Python version from the base image, e.g. `"3.11"` or `"3.12.2"`. Use with `uv venv --python <ver>`. |
| `env_exports` | `list[str]` | `export X=Y` lines from both Dockerfiles |
| `apt_install` | `str` | The single multi-line `apt-get install …` body, or `""` |
| `base_runs` | `list[str]` | Everything else from the base layer (mkdir, git, occasional extras), in original order, **with `pip` rewritten to `uv pip`** |
| `preprocess_body` | `str` | Body of `/preprocess.sh` (resets to task `base_commit`), shebang stripped |
| `python_setup_body` | `str` | Body of `/build.sh` (pip installs), shebang stripped, **`pip` rewritten to `uv pip`**, pypi-timemachine boilerplate replaced by `export UV_EXCLUDE_NEWER=<date>` |

Methods: `env_bash()`, `system_setup_bash()`, `base_runs_bash()`,
`preprocess_bash()`, `python_setup_bash()`, `to_bash(skip_apt=False)`.

Lower-level helpers if you need them: `load_local(iid)`,
`is_python_dockerfile(content)`, `get_python_version(content)`,
`list_local_instances()`, `extract_timemachine_date(body)`,
`drop_pypi_timemachine(body)`, `to_uv(bash_body)`.

### Driving `uv venv` from Python

```python
import subprocess
from convert_dockerfile_setup_to_bash import build_sections

sections = build_sections(iid)

# Create the venv with the correct interpreter, then run the setup
# script inside the activated venv.
subprocess.run(["uv", "venv", "--python", sections.python_version], check=True)
subprocess.run(
    ["bash", "-c", "source .venv/bin/activate && bash setup.sh"],
    check=True,
)
```

---

## Example 3 — Store the output in a `.sh` file

**From the CLI** — pass `--output`:

```bash
python helper_code/convert_dockerfile_setup_to_bash.py \
    --instance-id instance_ansible__ansible-bec27fb4... \
    --output ./setup_bec27fb4.sh
```

To make it executable:

```bash
chmod +x ./setup_bec27fb4.sh
```

**From Python** — write the rendered string:

```python
from pathlib import Path
from convert_dockerfile_setup_to_bash import build_sections

sections = build_sections("instance_ansible__ansible-bec27fb4...")

out_path = Path("./setup_bec27fb4.sh")
out_path.write_text(sections.to_bash())
out_path.chmod(0o755)  # make executable (optional)
print(f"Wrote {out_path}")
```

**Bulk dump for every Python instance**:

```bash
python helper_code/convert_dockerfile_setup_to_bash.py \
    --all-python --output-dir ./generated_setup_scripts/
```

---

## Output structure

Generated scripts use these section markers:

```
# === ENV ===
# === SYSTEM SETUP (apt) ===
# === REPO + BASE EXTRAS ===
# === PREPROCESS (reset to task base_commit) ===
# === PYTHON SETUP (pip install) ===
```

The order matters and mirrors the benchmark's two-step checkout: deps
are installed at the **checkpoint commit** (the `v…` suffix in the
instance id), then the working tree is reset to the task's `base_commit`.
Skipping the preprocess phase will leave you at the checkpoint commit,
not at the task commit.

---

## Notes

- **Date pinning via `UV_EXCLUDE_NEWER`.** By default the generated script
  sets `export UV_EXCLUDE_NEWER=<date>` (extracted from the original
  `pypi-timemachine` invocation), which tells UV to ignore any distribution
  uploaded after that date. This replaces the old proxy-server approach with
  a native UV feature and requires no extra package. Pass `--no-date-pin`
  (or `no_date_pin=True` in the API) only when you've verified the project's
  own pinning is strict enough to not need a date snapshot.
- **Python only.** Non-Python tasks (Go, Node) use different build
  patterns and aren't supported.
- **Difference vs. the original converter.** The original
  ([`convert_to_setup_script.py`](CONVERT_TO_SETUP_SCRIPT.md)) classifies
  base RUNs into apt vs repo vs other and emits `pip install` verbatim.
  This one splits apt vs everything-else (`base_runs`), rewrites every
  `pip install` to `uv pip install`, and exposes `python_version` /
  `get_python_version()` so you can drive `uv venv --python <ver>` from
  the same conversion call.
