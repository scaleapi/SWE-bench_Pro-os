# dataset_preprocessing

Tools for converting SWE-bench Pro Dockerfiles into bash setup scripts and building the task dataset.

> **Scope**: only Python tasks are currently supported. All scripts filter to Python instances unless noted otherwise.
>
> **Dataset source**: scripts pull directly from the HuggingFace dataset [`ScaleAI/SWE-bench_Pro`](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro) via `datasets.load_dataset`. The `helper_code/sweap_eval_full_v2.jsonl` file in this repo is **not** used here.

---

## End-to-end pipeline: producing `artifacts/python_dataset.jsonl`

```
Step 1  gen_bash_script_setup.py   convert Dockerfiles → bash setup scripts
Step 2  collect_all_system_deps.py aggregate apt packages → install_system_deps.sh
Step 3  prepare_dataset.py         attach setup scripts to HuggingFace dataset → python_dataset.jsonl
```

### Step 1 — generate bash setup scripts

`gen_bash_script_setup.py` reads each task's Dockerfiles and emits a self-contained bash script that installs system deps, clones the repo, and creates a Python venv at `/opt/venv`.

```bash
# Generate scripts for all Python instances into scripts/
python dataset_preprocessing/gen_bash_script_setup.py --all-python --output-dir scripts/

# Or generate a single instance (useful for debugging)
python dataset_preprocessing/gen_bash_script_setup.py --instance-id <iid> --output setup.sh
```

Each generated script is structured as:

```
ENV  →  APT  →  REPO  →  PREPROCESS  →  UV VENV  →  PYTHON SETUP
```

The venv is placed at `/opt/venv` (outside `/app`) so a `git clean -fdx` in the PREPROCESS step cannot delete it.

### Step 2 — aggregate apt packages

`collect_all_system_deps.py` scans all Python instances, collects their apt packages per repo, and writes `install_system_deps.sh` at the repo root.

```bash
python dataset_preprocessing/collect_all_system_deps.py
```

Re-run this after regenerating scripts to keep `install_system_deps.sh` in sync.

### Step 3 — build the JSONL dataset

`prepare_dataset.py` loads the HuggingFace dataset, attaches a `setup_script` field to each Python task (ENV + UV VENV + PYTHON SETUP sections only — no apt or repo clone, since those run once at the host level), and writes the result to a JSONL file.

```bash
python dataset_preprocessing/prepare_dataset.py --output artifacts/python_dataset.jsonl
```

The output `python_dataset.jsonl` is the artifact consumed by everything downstream.

---

## Testing a dataset entry end-to-end in Docker

`test_instance.py` lets you verify that a specific entry in `python_dataset.jsonl` is correct: that the environment builds, the patch applies, and the eval script correctly distinguishes the failing state from the passing state.

### What it does, step by step

1. **Loads the entry** from `python_dataset.jsonl` (by `instance_id` string or 0-based index).
2. **Ensures the base image** (`swebench-system-deps`, built from `artifacts/Dockerfile.system-deps`) exists; builds it if not.
3. **Writes a temporary Docker build context** containing:
   - `setup.sh` — the instance's `setup_script` from the dataset (venv + Python deps)
   - `before_repo_set_cmd.sh` — any repo mutations that must happen before setup
   - `eval.sh` — the eval script for this instance
   - `patch.diff` — the gold patch
   - `entrypoint.sh` — the script that orchestrates the before/after run
4. **Builds a Docker image** on top of the base image. The build clones the repo, checks out `base_commit`, runs `before_repo_set_cmd.sh`, and runs `setup.sh` to install the Python environment. This is the "frozen" state of the repo before any patch is applied.
5. **Runs the container**, which:
   - Activates the venv
   - Runs the eval script → saves results to `/workspace/before/`
   - Applies `patch.diff` with `git apply`
   - Runs the eval script again → saves results to `/workspace/after/`
   - Drops into an interactive bash shell (venv still active)

A correctly set up instance should show failures in `before` and passes in `after`.

### Usage

```bash
# By instance_id
python dataset_preprocessing/test_instance.py ansible__ansible-40ade1f84b8b...

# By 0-based index into the dataset
python dataset_preprocessing/test_instance.py 5

# Custom dataset file
python dataset_preprocessing/test_instance.py 5 --dataset path/to/other_dataset.jsonl

# Force a clean build (no Docker layer cache)
python dataset_preprocessing/test_instance.py 5 --no-cache

# Remove the image after the session (images are kept by default for re-use)
python dataset_preprocessing/test_instance.py 5 --no-keep-image
```

Inside the interactive shell:

```bash
cat /workspace/before/output.json   # test results before patch (failures expected)
cat /workspace/after/output.json    # test results after patch  (passes expected)
cat /workspace/before/eval.log      # full eval output before patch
cat /workspace/after/eval.log       # full eval output after patch
```

---

## Other scripts

### `test_setup_script_in_docker.py` — smoke test the converter

Spins up a Docker container, runs the generated setup script, and verifies the working tree is at the expected `base_commit`. Tests the Dockerfile-to-bash converter, not the benchmark itself.

```bash
python dataset_preprocessing/test_setup_script_in_docker.py
python dataset_preprocessing/test_setup_script_in_docker.py --instance-id <iid> --base-image python:3.11-slim
```

### `gen_bash_script_setup.py` — additional options

```bash
# Print to stdout instead of a file
python dataset_preprocessing/gen_bash_script_setup.py --instance-id <iid>

# Skip apt and repo setup (caller already has system deps + cloned repo)
python dataset_preprocessing/gen_bash_script_setup.py --instance-id <iid> --skip-apt --skip-repo-setup

# List all Python instance IDs
python dataset_preprocessing/gen_bash_script_setup.py --list-python
```

---

## Library: `dockerfile_to_bash.py`

Shared conversion logic imported by all scripts above.

```python
from dataset_preprocessing.dockerfile_to_bash import build_sections, load_local_dockerfiles

base, inst = load_local_dockerfiles(iid)
sections = build_sections(iid, base, inst)

sections.to_bash()                                     # full script
sections.to_bash(skip_apt=True, skip_repo_setup=True)  # env + venv + python only
sections.apt_packages                                  # set of debian package names
sections.python_version                                # e.g. "3.11"
```
