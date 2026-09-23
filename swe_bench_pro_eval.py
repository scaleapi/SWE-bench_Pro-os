"""
The script is used to evaluate the performance of the SWEAP Pro agent with Modal.

This evaluation script:
1. Takes a CSV file containing test cases and a JSON file containing patches
2. Runs each patch in a Modal sandbox environment using Docker Hub images
3. Executes the tests using local run scripts and collects results
4. Calculates overall accuracy based on test pass/fail status

Usage:
python sweap_pro_eval_modal.py \
    --raw_sample_path=data.csv \
    --patch_path={OUTPUT}/gold_patches.json \
    --output_dir={OUTPUT}/ \
    --scripts_dir=run_scripts \
    --num_workers=100 \
    --dockerhub_username=your-username

It expects:
- Local run scripts in run_scripts/{instance_id}/run_script.sh
- Local parser scripts in run_scripts/{instance_id}/parser.py
- CSV file with columns: instance_id, before_repo_set_cmd, selected_test_files_to_run, 
  base_commit, base_dockerfile, instance_dockerfile, FAIL_TO_PASS, PASS_TO_PASS

And the generated patch file (gold_patches.json) should have the following format:
[
    {
        "instance_id": "unique_id",
        "patch": "git patch content",
        "prefix": "optional_prefix"
    },
    ...
]
"""

import argparse
import concurrent.futures
import json
import os
import platform as py_platform
import re

try:
    import modal  # Lazy/optional: only required when not using --use_local_docker
except Exception:
    modal = None
try:
    import docker  # Optional: used when --use_local_docker is set
except Exception:
    docker = None
import pandas as pd
from tqdm import tqdm

from helper_code.image_uri import get_dockerhub_image_uri

# Docker names some architectures differently from platform.machine().
_ARCH_ALIASES = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
}


class InfrastructureError(RuntimeError):
    """The environment failed, so the patch was never scored.

    Distinct from a patch that ran and failed its tests: counting one as the other
    reports a broken environment as a wrong answer.
    """


def engine_version(client):
    """The server half of `docker version`, or {} if the engine cannot be asked.

    Not necessarily this machine: DOCKER_HOST or a docker context can point at another
    host entirely.
    """
    if client is None:
        return {}
    try:
        return client.version()
    except Exception:
        return {}


def engine_runs_in_vm(client, version):
    """Best effort: whether the engine runs containers in a VM instead of on this kernel.

    Only reached on a Linux client, where it catches this script running inside a
    container on a Mac. Docker Desktop names itself in the server's Platform.Name, and in
    info()["OperatingSystem"]; an engine that does neither falls through to the honest
    error rather than emulating silently.
    """
    if "docker desktop" in str((version.get("Platform") or {}).get("Name", "")).lower():
        return True
    if client is None:
        return False
    try:
        return "docker desktop" in str(client.info().get("OperatingSystem", "")).lower()
    except Exception:
        return False


def default_docker_platform(client=None):
    """The platform to use when --docker_platform was not given.

    `docker version` reports a client and a server separately, and on a Mac they differ:
    the client is darwin/arm64 and the server linux/arm64, because the engine runs in a
    VM. This process is the client, so platform.system() is that client line -- Darwin
    there, however Linux the container it starts turns out to be. That is the case the
    existing default was written for: no arm64 sweap-image exists to run in that VM, so
    emulation is the only way to run at all and stays the default.

    A Linux client with a Linux engine shares its kernel, so run the architecture that
    engine reports. Emulating a foreign one instead is slow enough to hit the
    per-instance timeout, and those timeouts are recorded as ordinary test failures.

    An engine that does not report its architecture gets None, not this machine's ISA:
    DOCKER_HOST or a docker context can point at a host with a different one, and leaving
    the platform unset lets that engine choose for itself.
    """
    version = engine_version(client)
    if py_platform.system() != "Linux" or engine_runs_in_vm(client, version):
        return "linux/amd64"
    arch = _ARCH_ALIASES.get(str(version.get("Arch", "")).lower())
    return f"linux/{arch}" if arch else None


def platform_arch(docker_platform):
    """The architecture component of a `linux/amd64`-style platform string."""
    if not docker_platform:
        return None
    parts = docker_platform.split("/")
    return _ARCH_ALIASES.get(parts[1].lower()) if len(parts) > 1 else None


def progress_description(eval_results, infra_errors):
    """Running accuracy over the instances that actually ran, plus the excluded count."""
    if eval_results:
        desc = f"Accuracy: {sum(eval_results.values()) / len(eval_results):.2%}"
    else:
        desc = "Accuracy: n/a"
    return f"{desc} ({len(infra_errors)} infra err)" if infra_errors else desc


def container_diagnostics(container, tail=50):
    """The container's own stdio.

    The only other diagnostics are /workspace/*.log, which do not exist if the
    entryscript never started -- exactly the case a wrong-architecture image produces.
    """
    try:
        logs = container.logs(tail=tail).decode("utf-8", errors="replace")
    except Exception as e:
        return f"  (could not read container logs: {e!r})"
    return "".join(f"  [container] {line}\n" for line in logs.splitlines()) or "  (no container output)"


# Credit: prabhuteja12
def load_base_docker(iid):
    with open(f"dockerfiles/base_dockerfile/{iid}/Dockerfile") as fp:
        return fp.read()

def instance_docker(iid):
    with open(f"dockerfiles/instance_dockerfile/{iid}/Dockerfile") as fp:
        return fp.read()

def load_local_script(scripts_dir, instance_id, script_name):
    """Load a script file from local scripts directory."""
    script_path = os.path.join(scripts_dir, instance_id, script_name)
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")
    
    with open(script_path, 'r') as f:
        return f.read()


def strip_binary_hunks(patch: str) -> str:
    """Remove binary diff sections from a git patch."""
    if not patch:
        return patch

    sections = re.split(r'(?=^diff --git )', patch, flags=re.MULTILINE)

    kept: list[str] = []
    for section in sections:
        if not section.strip():
            continue
        if re.search(r'^Binary files .* differ$', section, re.MULTILINE):
            continue
        if re.search(r'^GIT binary patch$', section, re.MULTILINE):
            continue
        kept.append(section)

    return "".join(kept)


def create_entryscript(sample):
    before_repo_set_cmd = sample["before_repo_set_cmd"].strip().split("\n")[-1]
    selected_test_files_to_run = ",".join(eval(sample["selected_test_files_to_run"]))
    base_commit = sample["base_commit"]
    base_dockerfile = load_base_docker(sample["instance_id"])
    instance_dockerfile = instance_docker(sample["instance_id"])
    
    # Extract ENV commands from dockerfiles
    env_cmds = []
    for dockerfile_content in [base_dockerfile, instance_dockerfile]:
        for line in dockerfile_content.split("\n"):
            line = line.strip()
            if line.startswith("ENV"):
                # Convert ENV commands to export statements
                env_cmd = line.replace("ENV", "export", 1)
                env_cmds.append(env_cmd)
    
    env_cmds = "\n".join(env_cmds)

    entry_script = f"""
{env_cmds}
# apply patch
cd /app
git reset --hard {base_commit}
git checkout {base_commit}
git apply -v /workspace/patch.diff
{before_repo_set_cmd}
# run test and save stdout and stderr to separate files
bash /workspace/run_script.sh {selected_test_files_to_run} > /workspace/stdout.log 2> /workspace/stderr.log
# run parsing script
python /workspace/parser.py /workspace/stdout.log /workspace/stderr.log /workspace/output.json
"""
    return entry_script


def create_dockerhub_tag(uid, repo_name=""):
    """
    Convert instance_id and repo name to Docker Hub compatible tag format.
    This must match the format used in the upload script.

    Args:
        uid (str): The instance_id (e.g., "django__django-12345")
        repo_name (str): The repository name from ECR (e.g., "sweap-images/nodebb.nodebb")

    Returns:
        str: Docker Hub compatible tag (e.g., "nodebb-nodebb-12345")
    """
    if repo_name:
        # For "NodeBB/NodeBB" -> repo_base="nodebb", repo_name="nodebb" 
        # Format: {repo_base}.{repo_name}-{OriginalCase}__{OriginalCase}-{hash}-{version}
        # Example: nodebb.nodebb-NodeBB__NodeBB-7b8bffd763e2155cf88f3ebc258fa68ebe18188d-vf2cf3cbd463b7ad942381f1c6d077626485a1e9e
        repo_base, repo_name_only = repo_name.lower().split("/")
        # Keep original case for the instance_id part (after removing "instance_" prefix)
        hsh = uid.replace("instance_", "")
        return f"{repo_base}.{repo_name_only}-{hsh}"
    else:
        image_name = "default"

    # Extract the tag part from the instance ID
    # For UIDs that start with a pattern like "django__django-", extract everything after position 9
    if "__" in uid and len(uid) > 9:
        tag_part = uid[9:]  # Skip the first 9 characters (e.g., "django__")
    else:
        tag_part = uid

    return f"{image_name}-{tag_part}"




def prepare_run(uid, output_dir, prefix, redo):
    uid_dir = os.path.join(output_dir, uid)
    os.makedirs(uid_dir, exist_ok=True)
    output_path = os.path.join(uid_dir, f"{prefix}_output.json")
    if not redo and os.path.exists(output_path):
        print(f"Skipping {uid} - output already exists")
        with open(output_path, "r") as f:
            return json.load(f), output_path, os.path.join(uid_dir, "workspace")
    workspace_dir = os.path.join(uid_dir, "workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    return None, output_path, workspace_dir


def write_patch_snapshot(output_dir, uid, prefix, patch):
    with open(os.path.join(output_dir, uid, f"{prefix}_patch.diff"), "w") as f:
        f.write(patch)


def assemble_workspace_files(uid, scripts_dir, patch, sample):
    run_script = load_local_script(scripts_dir, uid, "run_script.sh")
    parser_script = load_local_script(scripts_dir, uid, "parser.py")
    entryscript_content = create_entryscript(sample)

    cleaned_patch = strip_binary_hunks(patch)
    if cleaned_patch != patch:
        print(f"Stripped binary diff hunks from patch for {uid}")

    files = {
        "patch.diff": cleaned_patch,
        "run_script.sh": run_script,
        "parser.py": parser_script,
        "entryscript.sh": entryscript_content,
    }
    return files, entryscript_content


def write_files_modal(sandbox, files):
    for rel_path, content in files.items():
        with sandbox.open(f"/workspace/{rel_path}", "w") as f:
            f.write(content)


def write_files_local(workspace_dir, files):
    for rel_path, content in files.items():
        dst = os.path.join(workspace_dir, rel_path)
        with open(dst, "w") as f:
            f.write(content)


def save_entryscript_copy(output_dir, uid, prefix, entryscript_content):
    with open(os.path.join(output_dir, uid, f"{prefix}_entryscript.sh"), "w") as f:
        f.write(entryscript_content if entryscript_content is not None else "")


def collect_outputs_modal(sandbox, output_dir, uid, prefix):
    # Save logs first (best-effort)
    try:
        with sandbox.open("/workspace/stdout.log", "r") as f_in:
            with open(os.path.join(output_dir, uid, f"{prefix}_stdout.log"), "w") as f:
                stdout_content = f_in.read()
                f.write(stdout_content if stdout_content is not None else "")
    except FileNotFoundError:
        pass
    try:
        with sandbox.open("/workspace/stderr.log", "r") as f_in:
            with open(os.path.join(output_dir, uid, f"{prefix}_stderr.log"), "w") as f:
                stderr_content = f_in.read()
                f.write(stderr_content if stderr_content is not None else "")
    except FileNotFoundError:
        pass

    # Then try to read output.json
    try:
        with sandbox.open("/workspace/output.json", "r") as f_in:
            output = json.load(f_in)
            with open(os.path.join(output_dir, uid, f"{prefix}_output.json"), "w") as f:
                json.dump(output, f)
            return output
    except FileNotFoundError:
        print(
            f"Warning: output.json not found for {uid}. Check {prefix}_stdout.log and {prefix}_stderr.log for details"
        )
        return None


def collect_outputs_local(workspace_dir, output_dir, uid, prefix):
    def _copy_safe(src_name, dest_name):
        src_path = os.path.join(workspace_dir, src_name)
        dest_path = os.path.join(output_dir, uid, dest_name)
        try:
            with open(src_path, "r") as f_in:
                content = f_in.read()
        except FileNotFoundError:
            content = ""
        with open(dest_path, "w") as f_out:
            f_out.write(content if content is not None else "")

    _copy_safe("stdout.log", f"{prefix}_stdout.log")
    _copy_safe("stderr.log", f"{prefix}_stderr.log")

    # Then try to read output.json
    try:
        with open(os.path.join(workspace_dir, "output.json"), "r") as f_in:
            output = json.load(f_in)
            with open(os.path.join(output_dir, uid, f"{prefix}_output.json"), "w") as f:
                json.dump(output, f)
            return output
    except FileNotFoundError:
        print(
            f"Warning: output.json not found for {uid}. Check {prefix}_stdout.log and {prefix}_stderr.log for details"
        )
        return None


def eval_with_modal(patch, sample, output_dir, dockerhub_username, scripts_dir, prefix="", redo=False, block_network=False, docker_platform=None):
    if modal is None:
        raise RuntimeError("modal is not installed. Install it or run with --use_local_docker")
    uid = sample["instance_id"]
    existing_output, output_path, workspace_dir = prepare_run(uid, output_dir, prefix, redo)
    if existing_output is not None:
        return existing_output

    sandbox = None
    
    print(f"Running evaluation for {uid}")
    try:
        write_patch_snapshot(output_dir, uid, prefix, patch)

        try:
            files, entryscript_content = assemble_workspace_files(uid, scripts_dir, patch, sample)
        except FileNotFoundError as e:
            print(f"Error loading scripts for {uid}: {e}")
            return None

        app = modal.App.lookup(name="swe-bench-pro-eval", create_if_missing=True)
        
        # Use Docker Hub image instead of ECR
        dockerhub_image_uri = get_dockerhub_image_uri(uid, dockerhub_username, sample.get("repo", ""))
        print(f"Using Docker Hub image: {dockerhub_image_uri}")
        
        image = modal.Image.from_registry(
            dockerhub_image_uri
        )

        sandbox = modal.Sandbox.create(
            image=image,
            app=app,
            timeout=60 * 60,
            cpu=(1, 4),
            memory=(5 * 1024, 30 * 1024),
            block_network=block_network,
        )
        
        process = sandbox.exec("mkdir", "-p", "/workspace")
        process.wait()
        
        write_files_modal(sandbox, files)
            
        process = sandbox.exec("bash", "/workspace/entryscript.sh")
        process.wait()
        
        # Check if the process was successful
        if process.returncode != 0:
            print(f"Entryscript failed for {uid} with return code: {process.returncode}")
            # Get stderr from the process directly (note: this may not work with all Modal versions)
            try:
                stderr_content = getattr(process, 'stderr', None)
                if stderr_content and hasattr(stderr_content, 'read'):
                    error_details = stderr_content.read()
                    if error_details:
                        print(f"Error details for {uid}:")
                        print(error_details[:1000])  # Print first 1000 chars
            except Exception as e:
                print(f"Failed to read stderr for {uid}: {e}")
            
        output = collect_outputs_modal(sandbox, output_dir, uid, prefix)
        if output is None:
            return None
        save_entryscript_copy(output_dir, uid, prefix, entryscript_content)
            
        return output
    except Exception as e:
        print(f"Error in eval_with_modal for {uid}: {repr(e)}")
        print(f"Error type: {type(e)}")
        return None
    finally:
        if sandbox:
            try:
                sandbox.terminate()
            except Exception:
                pass


def eval_with_docker(patch, sample, output_dir, dockerhub_username, scripts_dir, prefix="", redo=False, block_network=False, docker_platform=None):
    if docker is None:
        raise RuntimeError("docker SDK is not installed. Install via 'pip install docker' or run without --use_local_docker")
    uid = sample["instance_id"]
    existing_output, output_path, workspace_dir = prepare_run(uid, output_dir, prefix, redo)
    if existing_output is not None:
        return existing_output

    print(f"Running local-docker evaluation for {uid}")

    try:
        try:
            files, entryscript_content = assemble_workspace_files(uid, scripts_dir, patch, sample)
        except FileNotFoundError as e:
            raise InfrastructureError(f"Error loading scripts for {uid}: {e}")
        write_files_local(workspace_dir, files)
        write_patch_snapshot(output_dir, uid, prefix, patch)

        # Run container via Docker SDK
        dockerhub_image_uri = get_dockerhub_image_uri(uid, dockerhub_username, sample.get("repo", ""))
        print(f"Using Docker Hub image: {dockerhub_image_uri}")

        client = docker.from_env()
        try:
            if docker_platform:
                client.images.pull(dockerhub_image_uri, platform=docker_platform)
            else:
                client.images.pull(dockerhub_image_uri)
        except Exception as pull_err:
            # If pull fails, fall back to a local image if present; otherwise, fail this run
            try:
                client.images.get(dockerhub_image_uri)
                print(f"Using locally available image: {dockerhub_image_uri}")
            except Exception:
                raise InfrastructureError(
                    f"Failed to pull or find image locally for {uid}: {pull_err}"
                )

        # Checked after a successful pull too, not just after the fallback: these tags are
        # single-platform manifests with no platform list for Docker to reject, so a pull
        # asking for arm64 succeeds and returns the amd64 image. Unchecked, the mismatch
        # surfaces inside the entryscript, where it looks like a failing patch.
        #
        # Only when a platform was asked for. Without one the engine served whatever it
        # runs natively, so there is nothing to disagree with -- and comparing against
        # this machine's ISA would reject a native image on a remote engine.
        wanted_arch = platform_arch(docker_platform)
        image_arch = _ARCH_ALIASES.get(
            str(client.images.get(dockerhub_image_uri).attrs.get("Architecture", "")).lower()
        )
        if wanted_arch and image_arch and image_arch != wanted_arch:
            raise InfrastructureError(
                f"Image for {uid} is {image_arch}, not {wanted_arch} "
                f"({dockerhub_image_uri}). The published sweap-images are amd64-only; "
                f"pass --docker_platform linux/amd64 to emulate it instead."
            )

        abs_workspace_dir = os.path.abspath(workspace_dir)
        volumes = {abs_workspace_dir: {"bind": "/workspace", "mode": "rw"}}
        run_kwargs = {
            "volumes": volumes,
            "detach": True,
            # Removed explicitly below instead, so that a container which failed before it
            # could write /workspace/*.log is still around to read logs from.
            "remove": False,
            "entrypoint": "/bin/bash",  # Override image entrypoint
            "command": ["-c", "bash /workspace/entryscript.sh"],
        }
        if block_network:
            run_kwargs["network_mode"] = "none"
        # Optional platform override (useful on Apple Silicon)
        if docker_platform:
            run_kwargs["platform"] = docker_platform

        try:
            container = client.containers.run(
                dockerhub_image_uri,
                **run_kwargs,
            )
        except docker.errors.DockerException as run_err:
            # A container that was never created ran no tests, so this cannot be a wrong
            # answer. Docker reports a platform with no matching image here as a bare 404
            # on /containers/create, which the outer handler would otherwise turn into
            # `return None` and main() into a scored failure.
            raise InfrastructureError(
                f"Could not start container for {uid} from {dockerhub_image_uri}: {run_err!r}"
            )

        try:
            result = container.wait()
            status_code = result.get("StatusCode", 1) if isinstance(result, dict) else 1
            if status_code != 0:
                print(f"Entryscript failed for {uid} with return code: {status_code}")
                print(container_diagnostics(container))
        finally:
            try:
                container.remove(force=True)
            except Exception as rm_err:
                print(f"Warning: could not remove container for {uid}: {rm_err!r}")

        # Collect outputs and logs, and save entryscript for reference
        output = collect_outputs_local(workspace_dir, output_dir, uid, prefix)
        if output is None:
            return None
        save_entryscript_copy(output_dir, uid, prefix, entryscript_content)

        return output
    except InfrastructureError:
        raise
    except Exception as e:
        print(f"Error in eval_with_docker for {uid}: {repr(e)}")
        print(f"Error type: {type(e)}")
        return None


def parse_args():
    parser = argparse.ArgumentParser(description="Run SWEAP Pro evaluations using Modal or local Docker with Docker Hub images and local scripts")
    parser.add_argument("--raw_sample_path", required=True, help="Path to the raw sample CSV file")
    parser.add_argument(
        "--patch_path", required=True, help="Path to the JSON file containing patches"
    )
    parser.add_argument("--output_dir", required=True, help="Directory to store evaluation outputs")
    parser.add_argument(
        "--dockerhub_username", required=True, help="Docker Hub username where sweap-images repository is located"
    )
    parser.add_argument(
        "--scripts_dir", required=True, help="Directory containing local run scripts (e.g., scripts/run_scripts)"
    )
    parser.add_argument(
        "--use_local_docker", action="store_true", help="Run locally with Docker instead of Modal"
    )
    parser.add_argument(
        "--docker_platform",
        default=None,
        help=(
            "Docker platform for --use_local_docker, e.g. linux/amd64. Defaults to this "
            "machine's own architecture on Linux, and to linux/amd64 where Docker runs "
            "containers in a VM (macOS). Naming a foreign architecture opts in to emulation."
        ),
    )
    parser.add_argument(
        "--redo", action="store_true", help="Redo evaluations even if output exists"
    )
    parser.add_argument(
        "--num_workers",
        type=int,
        default=50,
        help="Number of workers to run evaluations in parallel",
    )
    parser.add_argument(
        "--block_network", action="store_true", help="Block network access inside container"
    )
    args = parser.parse_args()
    if args.docker_platform and not args.use_local_docker:
        parser.error(
            "--docker_platform applies only to --use_local_docker; the Modal path builds "
            "its own image and ignores it."
        )
    return args


def main():
    args = parse_args()

    # Support both JSONL and CSV input files
    if args.raw_sample_path.endswith(".jsonl"):
        raw_sample_df = pd.read_json(args.raw_sample_path, lines=True)
    else:
        raw_sample_df = pd.read_csv(args.raw_sample_path)
    
    # Replace nulls with empty strings
    raw_sample_df = raw_sample_df.fillna("")
    
    # use instance_id as index
    raw_sample_df = raw_sample_df.set_index("instance_id", drop=False)

    # each patch sample is a dict with keys: instance_id, patch, prefix
    with open(args.patch_path, "r") as f:
        patches_to_run = json.load(f)
    eval_results = {}
    # Instances that never ran, kept apart from instances that ran and failed.
    infra_errors = {}

    # Filter patches to only include those with matching instance_ids in the raw sample data
    valid_patches = []
    missing_instances = []
    for patch_sample in patches_to_run:
        instance_id = patch_sample["instance_id"]
        if instance_id in raw_sample_df.index:
            valid_patches.append(patch_sample)
        else:
            missing_instances.append(instance_id)
    
    if missing_instances:
        print(f"Warning: Found {len(missing_instances)} patch instances not in raw sample data:")
        for missing_id in missing_instances[:5]:  # Show first 5
            print(f"  - {missing_id}")
        if len(missing_instances) > 5:
            print(f"  ... and {len(missing_instances) - 5} more")
        print(f"Proceeding with {len(valid_patches)} valid patches out of {len(patches_to_run)} total patches")

    # Select runtime
    # A Linux engine runs its own architecture; a VM-backed one (macOS) keeps preferring
    # linux/amd64, since there is nothing else it could run (see default_docker_platform).
    docker_platform = args.docker_platform
    if args.use_local_docker and docker_platform is None:
        try:
            probe_client = docker.from_env() if docker is not None else None
        except Exception:
            probe_client = None
        docker_platform = default_docker_platform(probe_client)
        if docker_platform is None:
            print(
                "Warning: the Docker engine did not report an architecture this script "
                "recognises; letting it choose the platform. Pass --docker_platform to "
                "pin one."
            )
        elif platform_arch(docker_platform) != "amd64":
            print(
                f"Running natively on {docker_platform}. The published sweap-images are "
                f"amd64-only today, so instances with no {platform_arch(docker_platform)} "
                f"image will report an infrastructure error instead of being scored. "
                f"Pass --docker_platform linux/amd64 to emulate amd64 instead."
            )

    eval_fn = eval_with_docker if args.use_local_docker else eval_with_modal

    # Use ThreadPoolExecutor to run evaluations in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.num_workers) as executor:
        # Create a dictionary mapping futures to their patch samples for progress tracking
        future_to_patch = {
            executor.submit(
                eval_fn,
                patch_sample.get("model_patch", patch_sample.get("patch", "")),
                raw_sample_df.loc[patch_sample["instance_id"]],
                args.output_dir,
                args.dockerhub_username,
                args.scripts_dir,
                prefix=patch_sample.get("prefix", ""),
                redo=args.redo,
                block_network=args.block_network,
                docker_platform=docker_platform,
            ): patch_sample
            for patch_sample in valid_patches
        }

        # Track progress with tqdm and show running accuracy
        pbar = tqdm(concurrent.futures.as_completed(future_to_patch), total=len(valid_patches))
        for future in pbar:
            patch_sample = future_to_patch[future]
            try:
                # Get the result (if any error occurred, it will be raised here)
                output = future.result()
                if output is None:
                    print(f'Evaluation for {patch_sample["instance_id"]} returned None')
                    eval_results[patch_sample["instance_id"]] = False
                else:
                    instance_id = patch_sample["instance_id"]
                    if instance_id not in raw_sample_df.index:
                        print(f'Warning: Instance {instance_id} not found in raw sample data, skipping')
                        eval_results[instance_id] = False
                    else:
                        raw_sample = raw_sample_df.loc[instance_id]
                        passed_tests = {x["name"] for x in output["tests"] if x["status"] == "PASSED"}
                        f2p = set(eval(raw_sample["fail_to_pass"]))
                        p2p = set(eval(raw_sample["pass_to_pass"]))
                        result = (f2p | p2p) <= passed_tests
                        eval_results[instance_id] = result

            except InfrastructureError as exc:
                # Never scored, so not an unresolved instance either.
                print(f'Evaluation for {patch_sample["instance_id"]} could not run: {exc}')
                infra_errors[patch_sample["instance_id"]] = str(exc)
            except Exception as exc:
                print(f'Evaluation for {patch_sample["instance_id"]} generated an exception: {exc}')
                eval_results[patch_sample["instance_id"]] = False
            pbar.set_description(progress_description(eval_results, infra_errors))

    with open(os.path.join(args.output_dir, "eval_results.json"), "w") as f:
        json.dump(eval_results, f)
    # Reported separately and left out of the accuracy denominator: these instances never
    # ran, so scoring them as failures would understate the result by exactly the number of
    # broken environments -- which is how an architecture mismatch turns into a
    # plausible-looking number. Written even when empty, like eval_results.json above: a
    # later --redo in the same output_dir would otherwise leave the previous run's list
    # behind to describe this one.
    with open(os.path.join(args.output_dir, "infra_errors.json"), "w") as f:
        json.dump(infra_errors, f, indent=2)
    if infra_errors:
        print(
            f"{len(infra_errors)} instance(s) could not be evaluated and are excluded from "
            f"the accuracy below; see infra_errors.json"
        )
    if eval_results:
        print(
            "Overall accuracy: ",
            sum(eval_results.values()) / len(eval_results),
            f"({len(eval_results)} of {len(valid_patches)} instances scored)",
        )
    else:
        print(f"No instances were scored out of {len(valid_patches)}.")


if __name__ == "__main__":
    main()
