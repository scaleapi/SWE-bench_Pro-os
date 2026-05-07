# dataset_preprocessing

Tools for converting SWE-bench Pro Dockerfiles into bash setup scripts and building the task dataset.

## Scripts

### `gen_bash_script_setup.py` — generate bash setup scripts

Converts a task's Dockerfiles into a self-contained bash script that installs system deps, clones the repo, and sets up a Python venv at `/opt/venv`.

```bash
# Single instance → stdout
python dataset_preprocessing/gen_bash_script_setup.py --instance-id <iid>

# Single instance → file
python dataset_preprocessing/gen_bash_script_setup.py --instance-id <iid> --output setup.sh

# All Python instances
python dataset_preprocessing/gen_bash_script_setup.py --all-python --output-dir scripts/

# Skip apt and repo setup (caller already has system deps + cloned repo)
python dataset_preprocessing/gen_bash_script_setup.py --instance-id <iid> --skip-apt --skip-repo-setup

# List all Python instance IDs
python dataset_preprocessing/gen_bash_script_setup.py --list-python
```

Generated scripts are structured as: `ENV` → `APT` → `REPO` → `PREPROCESS` → `UV VENV` → `PYTHON SETUP`.

The venv is placed at `/opt/venv` (outside `/app`) so `git clean -fdx` in the PREPROCESS step cannot delete it.

### `collect_all_system_deps.py` — aggregate apt packages

Scans all Python instances, collects apt packages per repo, and writes `install_system_deps.sh` at the repo root.

```bash
python dataset_preprocessing/collect_all_system_deps.py
```

Re-run this after regenerating scripts to keep `install_system_deps.sh` in sync.

### `prepare_dataset.py` — build JSONL dataset

Loads the HuggingFace dataset, attaches a `setup_script` field (ENV + UV VENV + PYTHON SETUP sections only — no apt or repo clone) to each Python task, and writes a JSONL file.

```bash
python dataset_preprocessing/prepare_dataset.py --output artifacts/python_dataset.jsonl
```

### `test_setup_script_in_docker.py` — smoke test

Spins up a Docker container, runs the generated setup script, and verifies the working tree is at the expected `base_commit`. This tests the converter, not the benchmark.

```bash
python dataset_preprocessing/test_setup_script_in_docker.py
python dataset_preprocessing/test_setup_script_in_docker.py --instance-id <iid> --base-image python:3.11-slim
```

## Library: `dockerfile_to_bash.py`

Shared conversion logic imported by all scripts above. Key public API:

```python
from dataset_preprocessing.dockerfile_to_bash import build_sections, load_local_dockerfiles

base, inst = load_local_dockerfiles(iid)
sections = build_sections(iid, base, inst)

sections.to_bash()                                    # full script
sections.to_bash(skip_apt=True, skip_repo_setup=True) # env + venv + python only
sections.apt_packages                                 # set of debian package names
sections.python_version                               # e.g. "3.11"
```
