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
import subprocess
import tempfile
import time

import pandas as pd
from tqdm import tqdm

# modal is imported lazily only when needed (not used with --use_local_docker)
modal = None

# Constants for retry logic
MAX_BUILD_RETRIES = 3
BUILD_RETRY_DELAY = 5  # seconds


def load_local_script(scripts_dir, instance_id, script_name):
    """Load a script file from local scripts directory."""
    script_path = os.path.join(scripts_dir, instance_id, script_name)
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")
    
    with open(script_path, 'r') as f:
        return f.read()


def create_entryscript(sample):
    before_repo_set_cmd = sample["before_repo_set_cmd"].strip().split("\n")[-1]
    selected_test_files_to_run = ",".join(eval(sample["selected_test_files_to_run"]))
    base_commit = sample["base_commit"]
    base_dockerfile = sample["base_dockerfile"]
    instance_dockerfile = sample["instance_dockerfile"]
    
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


# ── Instance-to-Docker-Hub-tag mapping ──────────────────────────────────────────
# Loaded once from a JSON file that maps every known instance_id to its exact
# Docker Hub tag.  This eliminates all edge-case tag-construction logic.
_INSTANCE_TAG_MAP = None  # lazily loaded


def _load_instance_tag_map():
    """Load the instance-to-tag mapping from the JSON file (once)."""
    global _INSTANCE_TAG_MAP
    if _INSTANCE_TAG_MAP is not None:
        return _INSTANCE_TAG_MAP

    # The mapping file lives next to the SPB_Eval_Pipeline directory
    mapping_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "SPB_Eval_Pipeline",
        "instance_to_tag_mapping.json",
    )
    if not os.path.exists(mapping_path):
        raise FileNotFoundError(
            f"Instance-to-tag mapping file not found: {mapping_path}\n"
            "Run the tag-mapping generation script first."
        )
    with open(mapping_path, "r") as f:
        _INSTANCE_TAG_MAP = json.load(f)
    print(f"Loaded {len(_INSTANCE_TAG_MAP)} instance-to-tag mappings from {mapping_path}")
    return _INSTANCE_TAG_MAP


def create_dockerhub_tag(uid, repo_name=""):
    """
    Look up the Docker Hub tag for a given instance_id from the pre-built mapping.

    Args:
        uid (str): The instance_id (e.g., "instance_NodeBB__NodeBB-abc123-vdef456")
        repo_name (str): Unused, kept for backward compatibility.

    Returns:
        str: Docker Hub tag for this instance.

    Raises:
        KeyError: If the instance_id is not found in the mapping.
    """
    tag_map = _load_instance_tag_map()
    if uid in tag_map:
        return tag_map[uid]
    raise KeyError(
        f"Instance '{uid}' not found in instance_to_tag_mapping.json. "
        "Regenerate the mapping or add this instance manually."
    )


def get_dockerhub_image_uri(uid, dockerhub_username, repo_name=""):
    """
    Generate Docker Hub image URI matching the upload script format.
    
    Args:
        uid (str): Instance ID
        dockerhub_username (str): Docker Hub username
        repo_name (str): Repository name from the sample data
        
    Returns:
        str: Full Docker Hub image URI
    """
    tag = create_dockerhub_tag(uid, repo_name)
    return f"{dockerhub_username}/sweap-images:{tag}"


def is_image_build_error(error: Exception) -> bool:
    """Check if an exception is related to Docker image build failure."""
    error_str = str(error).lower()
    error_repr = repr(error).lower()
    
    build_error_indicators = [
        "image build",
        "skopeo copy",
        "failed with the exception",
        "remoteerror",
        "image pull",
        "registry",
    ]
    
    for indicator in build_error_indicators:
        if indicator in error_str or indicator in error_repr:
            return True
    
    # Check for modal.exception.RemoteError specifically
    if "RemoteError" in type(error).__name__:
        return True
    
    return False


def create_build_failure_output(uid: str, error: Exception, attempt: int, max_attempts: int) -> dict:
    """Create a standardized output dict for image build failures."""
    return {
        "status": "image_build_fail",
        "instance_id": uid,
        "error": str(error),
        "error_type": type(error).__name__,
        "attempts": attempt,
        "max_attempts": max_attempts,
        "tests": []
    }


def eval_with_modal(patch, sample, output_dir, dockerhub_username, scripts_dir, prefix="", redo=False, block_network=False):
    global modal
    if modal is None:
        import modal as _modal
        modal = _modal

    uid = sample["instance_id"]
    os.makedirs(os.path.join(output_dir, uid), exist_ok=True)
    output_path = os.path.join(output_dir, uid, f"{prefix}_output.json")
    
    if not redo and os.path.exists(output_path):
        print(f"Skipping {uid} - output already exists")
        with open(output_path, "r") as f:
            return json.load(f)
    
    print(f"Running evaluation for {uid}")
    
    # Save patch file
    with open(os.path.join(output_dir, uid, f"{prefix}_patch.diff"), "w") as f:
        f.write(patch)
    
    # Load local scripts
    try:
        run_script = load_local_script(scripts_dir, uid, "run_script.sh")
        parser_script = load_local_script(scripts_dir, uid, "parser.py")
    except FileNotFoundError as e:
        print(f"Error loading scripts for {uid}: {e}")
        return None
    
    # Use Docker Hub image instead of ECR
    dockerhub_image_uri = get_dockerhub_image_uri(uid, dockerhub_username, sample.get("repo", ""))
    print(f"Using Docker Hub image: {dockerhub_image_uri}")
    
    # Retry loop for sandbox creation (handles image build failures)
    sandbox = None
    last_error = None
    
    for attempt in range(1, MAX_BUILD_RETRIES + 1):
        try:
            app = modal.App.lookup(name="swe-bench-pro-eval", create_if_missing=True)
            
            image = modal.Image.from_registry(
                dockerhub_image_uri,
                setup_dockerfile_commands=[
                    "RUN (apt update && apt install -y python3-pip) || (apk update && apk add py3-pip) || true",
                    "RUN python -m pip config set global.break-system-packages true || true",
                    "RUN pip install requests || true",
                ],
            ).entrypoint([])

            sandbox = modal.Sandbox.create(
                image=image,
                app=app,
                timeout=10 * 60,  # 10 minutes timeout
                cpu=(1, 4),
                memory=(5 * 1024, 30 * 1024),
                block_network=block_network,
            )
            
            # If we get here, sandbox was created successfully
            break
            
        except Exception as e:
            last_error = e
            error_msg = f"Attempt {attempt}/{MAX_BUILD_RETRIES} - Sandbox creation failed for {uid}: {repr(e)}"
            print(error_msg)
            
            if is_image_build_error(e):
                if attempt < MAX_BUILD_RETRIES:
                    print(f"  Image build error detected. Retrying in {BUILD_RETRY_DELAY} seconds...")
                    time.sleep(BUILD_RETRY_DELAY)
                else:
                    # Max retries reached for build error - save failure output and move on
                    print(f"  Max retries ({MAX_BUILD_RETRIES}) reached for image build failure. Moving to next instance.")
                    build_fail_output = create_build_failure_output(uid, e, attempt, MAX_BUILD_RETRIES)
                    with open(output_path, "w") as f:
                        json.dump(build_fail_output, f, indent=2)
                    return build_fail_output
            else:
                # Non-build error, don't retry
                print(f"  Non-build error encountered. Not retrying.")
                return None
    
    # If sandbox is still None after retries, something went wrong
    if sandbox is None:
        print(f"Failed to create sandbox for {uid} after {MAX_BUILD_RETRIES} attempts")
        if last_error:
            build_fail_output = create_build_failure_output(uid, last_error, MAX_BUILD_RETRIES, MAX_BUILD_RETRIES)
            with open(output_path, "w") as f:
                json.dump(build_fail_output, f, indent=2)
            return build_fail_output
        return None
    
    # Sandbox created successfully, proceed with evaluation
    try:
        process = sandbox.exec("mkdir", "-p", "/workspace")
        process.wait()
        
        # Write patch file
        with sandbox.open("/workspace/patch.diff", "w") as f:
            f.write(patch)
            
        # Write local scripts to sandbox
        with sandbox.open("/workspace/run_script.sh", "w") as f:
            f.write(run_script)
        with sandbox.open("/workspace/parser.py", "w") as f:
            f.write(parser_script)
        with sandbox.open("/workspace/entryscript.sh", "w") as f:
            f.write(create_entryscript(sample))
            
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
            
        # Check if output.json exists first
        try:
            with sandbox.open("/workspace/output.json", "r") as f_in:
                output = json.load(f_in)
                with open(output_path, "w") as f:
                    json.dump(output, f)
        except FileNotFoundError:
            print(
                f"Warning: output.json not found for {uid}. Check {prefix}_stdout.log and {prefix}_stderr.log for details"
            )
            return None
            
        # Save logs
        with sandbox.open("/workspace/stdout.log", "r") as f_in:
            with open(os.path.join(output_dir, uid, f"{prefix}_stdout.log"), "w") as f:
                stdout_content = f_in.read()
                f.write(stdout_content if stdout_content is not None else "")
        with sandbox.open("/workspace/stderr.log", "r") as f_in:
            with open(os.path.join(output_dir, uid, f"{prefix}_stderr.log"), "w") as f:
                stderr_content = f_in.read()
                f.write(stderr_content if stderr_content is not None else "")
        with open(os.path.join(output_dir, uid, f"{prefix}_entryscript.sh"), "w") as f:
            entryscript_content = create_entryscript(sample)
            f.write(entryscript_content if entryscript_content is not None else "")
            
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


def eval_with_local_docker(patch, sample, output_dir, dockerhub_username, scripts_dir, prefix="", redo=False):
    """Evaluate a patch using local Docker instead of Modal sandboxes."""
    uid = sample["instance_id"]
    os.makedirs(os.path.join(output_dir, uid), exist_ok=True)
    output_path = os.path.join(output_dir, uid, f"{prefix}_output.json")

    if not redo and os.path.exists(output_path):
        print(f"Skipping {uid} - output already exists")
        with open(output_path, "r") as f:
            return json.load(f)

    print(f"Running LOCAL DOCKER evaluation for {uid}")

    # Save patch file
    with open(os.path.join(output_dir, uid, f"{prefix}_patch.diff"), "w") as f:
        f.write(patch)

    # Load local scripts
    try:
        run_script = load_local_script(scripts_dir, uid, "run_script.sh")
        parser_script = load_local_script(scripts_dir, uid, "parser.py")
    except FileNotFoundError as e:
        print(f"Error loading scripts for {uid}: {e}")
        return None

    # Use Docker Hub image
    dockerhub_image_uri = get_dockerhub_image_uri(uid, dockerhub_username, sample.get("repo", ""))
    print(f"Using Docker Hub image: {dockerhub_image_uri}")

    container_name = f"swe-bench-eval-{uid}".replace("/", "-")[:128]
    entryscript_content = create_entryscript(sample)

    # Write workspace files to a temp directory to docker-cp into the container
    tmpdir = None
    try:
        tmpdir = tempfile.mkdtemp(prefix="swe_eval_")
        patch_path_local = os.path.join(tmpdir, "patch.diff")
        run_script_path = os.path.join(tmpdir, "run_script.sh")
        parser_path = os.path.join(tmpdir, "parser.py")
        entry_path = os.path.join(tmpdir, "entryscript.sh")

        with open(patch_path_local, "w") as f:
            f.write(patch)
        with open(run_script_path, "w") as f:
            f.write(run_script)
        with open(parser_path, "w") as f:
            f.write(parser_script)
        with open(entry_path, "w") as f:
            f.write(entryscript_content)

        # Save entryscript locally for debugging
        with open(os.path.join(output_dir, uid, f"{prefix}_entryscript.sh"), "w") as f:
            f.write(entryscript_content)

        # Pull the image
        print(f"  Pulling image {dockerhub_image_uri}...")
        pull_result = subprocess.run(
            ["docker", "pull", dockerhub_image_uri],
            capture_output=True, text=True, timeout=600
        )
        if pull_result.returncode != 0:
            print(f"  Failed to pull image for {uid}: {pull_result.stderr}")
            build_fail_output = {
                "status": "image_build_fail",
                "instance_id": uid,
                "error": f"docker pull failed: {pull_result.stderr}",
                "error_type": "DockerPullError",
                "attempts": 1,
                "max_attempts": 1,
                "tests": []
            }
            with open(output_path, "w") as f:
                json.dump(build_fail_output, f, indent=2)
            return build_fail_output

        # Create and start container
        print(f"  Creating container for {uid}...")
        create_result = subprocess.run(
            ["docker", "create", "--name", container_name,
             "--entrypoint", "", dockerhub_image_uri,
             "sleep", "infinity"],
            capture_output=True, text=True, timeout=120
        )
        if create_result.returncode != 0:
            print(f"  Failed to create container for {uid}: {create_result.stderr}")
            return None

        subprocess.run(
            ["docker", "start", container_name],
            capture_output=True, text=True, timeout=60
        )

        # Create /workspace inside container
        subprocess.run(
            ["docker", "exec", container_name, "mkdir", "-p", "/workspace"],
            capture_output=True, text=True, timeout=30
        )

        # Copy workspace files into container
        for local_file, container_dest in [
            (patch_path_local, "/workspace/patch.diff"),
            (run_script_path, "/workspace/run_script.sh"),
            (parser_path, "/workspace/parser.py"),
            (entry_path, "/workspace/entryscript.sh"),
        ]:
            cp_result = subprocess.run(
                ["docker", "cp", local_file, f"{container_name}:{container_dest}"],
                capture_output=True, text=True, timeout=30
            )
            if cp_result.returncode != 0:
                print(f"  Failed to copy {local_file} into container: {cp_result.stderr}")
                return None

        # Execute the entry script (10 min timeout)
        print(f"  Running entry script for {uid}...")
        exec_result = subprocess.run(
            ["docker", "exec", container_name, "bash", "/workspace/entryscript.sh"],
            capture_output=True, text=True, timeout=600
        )
        if exec_result.returncode != 0:
            print(f"  Entry script failed for {uid} with return code: {exec_result.returncode}")
            if exec_result.stderr:
                print(f"  Stderr (first 1000 chars): {exec_result.stderr[:1000]}")

        # Copy output files from container
        output_json_local = os.path.join(tmpdir, "output.json")
        stdout_log_local = os.path.join(tmpdir, "stdout.log")
        stderr_log_local = os.path.join(tmpdir, "stderr.log")

        # Copy output.json
        cp_out = subprocess.run(
            ["docker", "cp", f"{container_name}:/workspace/output.json", output_json_local],
            capture_output=True, text=True, timeout=30
        )
        if cp_out.returncode != 0:
            print(f"  Warning: output.json not found for {uid}. Check logs for details.")
            # Still try to grab logs
            subprocess.run(
                ["docker", "cp", f"{container_name}:/workspace/stdout.log", stdout_log_local],
                capture_output=True, text=True, timeout=30
            )
            subprocess.run(
                ["docker", "cp", f"{container_name}:/workspace/stderr.log", stderr_log_local],
                capture_output=True, text=True, timeout=30
            )
            # Save whatever logs we got
            for log_file, dest_name in [(stdout_log_local, f"{prefix}_stdout.log"), (stderr_log_local, f"{prefix}_stderr.log")]:
                if os.path.exists(log_file):
                    with open(log_file, "r") as fin:
                        with open(os.path.join(output_dir, uid, dest_name), "w") as fout:
                            fout.write(fin.read())
            return None

        # Read and save output
        with open(output_json_local, "r") as f:
            output = json.load(f)
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        # Copy and save logs
        subprocess.run(
            ["docker", "cp", f"{container_name}:/workspace/stdout.log", stdout_log_local],
            capture_output=True, text=True, timeout=30
        )
        subprocess.run(
            ["docker", "cp", f"{container_name}:/workspace/stderr.log", stderr_log_local],
            capture_output=True, text=True, timeout=30
        )
        for log_file, dest_name in [(stdout_log_local, f"{prefix}_stdout.log"), (stderr_log_local, f"{prefix}_stderr.log")]:
            if os.path.exists(log_file):
                with open(log_file, "r") as fin:
                    with open(os.path.join(output_dir, uid, dest_name), "w") as fout:
                        fout.write(fin.read())

        return output

    except subprocess.TimeoutExpired:
        print(f"  Timeout expired for {uid}")
        return None
    except Exception as e:
        print(f"Error in eval_with_local_docker for {uid}: {repr(e)}")
        print(f"Error type: {type(e)}")
        return None
    finally:
        # Clean up container
        try:
            subprocess.run(["docker", "rm", "-f", container_name],
                           capture_output=True, text=True, timeout=30)
        except Exception:
            pass
        # Clean up temp dir
        if tmpdir and os.path.exists(tmpdir):
            try:
                import shutil
                shutil.rmtree(tmpdir)
            except Exception:
                pass


def parse_args():
    parser = argparse.ArgumentParser(description="Run SWEAP Pro evaluations with Modal using Docker Hub images and local scripts")
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
        "--redo", action="store_true", help="Redo evaluations even if output exists"
    )
    parser.add_argument(
        "--num_workers",
        type=int,
        default=50,
        help="Number of workers to run evaluations in parallel",
    )
    parser.add_argument(
        "--block_network", action="store_true", help="Block network access for Modal"
    )
    parser.add_argument(
        "--use_local_docker", action="store_true",
        help="Use local Docker instead of Modal for evaluation (pulls images from Docker Hub, runs containers locally)"
    )
    return parser.parse_args()


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

    # Select eval function based on --use_local_docker flag
    use_local = getattr(args, "use_local_docker", False)
    if use_local:
        print(">>> Using LOCAL DOCKER evaluation mode <<<")
        eval_fn = lambda patch, sample, output_dir, dockerhub_username, scripts_dir, prefix="", redo=False, block_network=False: \
            eval_with_local_docker(patch, sample, output_dir, dockerhub_username, scripts_dir, prefix=prefix, redo=redo)
    else:
        eval_fn = eval_with_modal

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
                    eval_results[patch_sample["instance_id"]] = {
                        "status": "Fail",
                        "resolved": False,
                        "PASS_TO_PASS": "",
                        "FAIL_TO_PASS": "",
                        "error": "Evaluation returned None"
                    }
                elif output.get("status") == "image_build_fail":
                    # Handle image build failure - preserve the status for Google Sheets
                    instance_id = patch_sample["instance_id"]
                    print(f'Image build failed for {instance_id} after {output.get("attempts", "?")} attempts')
                    eval_results[instance_id] = {
                        "status": "image_build_fail",
                        "resolved": False,
                        "PASS_TO_PASS": "",
                        "FAIL_TO_PASS": "",
                        "error": output.get("error", "Image build failed"),
                        "error_type": output.get("error_type", "Unknown"),
                        "attempts": output.get("attempts", 0)
                    }
                else:
                    instance_id = patch_sample["instance_id"]
                    if instance_id not in raw_sample_df.index:
                        print(f'Warning: Instance {instance_id} not found in raw sample data, skipping')
                        eval_results[instance_id] = {
                            "status": "Fail",
                            "resolved": False,
                            "PASS_TO_PASS": "",
                            "FAIL_TO_PASS": "",
                            "error": "Instance not found in raw sample data"
                        }
                    else:
                        raw_sample = raw_sample_df.loc[instance_id]
                        passed_tests = {x["name"] for x in output.get("tests", []) if x["status"] == "PASSED"}
                        f2p = set(eval(raw_sample["fail_to_pass"]))
                        p2p = set(eval(raw_sample["pass_to_pass"]))
                        
                        # Calculate which tests passed/failed for each category
                        f2p_passed = f2p & passed_tests
                        f2p_failed = f2p - passed_tests
                        p2p_passed = p2p & passed_tests
                        p2p_failed = p2p - passed_tests
                        
                        result = (f2p | p2p) <= passed_tests
                        
                        # Build detailed breakdown strings
                        f2p_status = f"{len(f2p_passed)}/{len(f2p)} passed"
                        if f2p_failed:
                            f2p_status += f" (failed: {', '.join(sorted(f2p_failed))})"
                        
                        p2p_status = f"{len(p2p_passed)}/{len(p2p)} passed"
                        if p2p_failed:
                            p2p_status += f" (failed: {', '.join(sorted(p2p_failed))})"
                        
                        eval_results[instance_id] = {
                            "status": "Pass" if result else "Fail",
                            "resolved": result,
                            "PASS_TO_PASS": p2p_status,
                            "FAIL_TO_PASS": f2p_status
                        }

                resolved_count = sum(1 for r in eval_results.values() if isinstance(r, dict) and r.get("resolved", False))
                current_accuracy = resolved_count / len(eval_results)
                pbar.set_description(f"Accuracy: {current_accuracy:.2%}")
            except Exception as exc:
                print(f'Evaluation for {patch_sample["instance_id"]} generated an exception: {exc}')
                eval_results[patch_sample["instance_id"]] = {
                    "status": "Fail",
                    "resolved": False,
                    "PASS_TO_PASS": "",
                    "FAIL_TO_PASS": "",
                    "error": str(exc)
                }
                # Update progress bar description with current accuracy
                resolved_count = sum(1 for r in eval_results.values() if isinstance(r, dict) and r.get("resolved", False))
                current_accuracy = resolved_count / len(eval_results)
                pbar.set_description(f"Accuracy: {current_accuracy:.2%}")
    with open(os.path.join(args.output_dir, "eval_results.json"), "w") as f:
        json.dump(eval_results, f, indent=2)
    resolved_count = sum(1 for r in eval_results.values() if isinstance(r, dict) and r.get("resolved", False))
    print("Overall accuracy: ", resolved_count / len(eval_results))


if __name__ == "__main__":
    main()