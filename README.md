## SWE-Bench Pro

Code and data for the following works:
* <a href="https://static.scale.com/uploads/654197dc94d34f66c0f5184e/SWEAP_Eval_Scale%20(9).pdf">SWE-bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks?</a>

* HuggingFace: <a href="https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro">https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro</a>

* Public Leaderboard: <a href="https://scale.com/leaderboard/swe_bench_pro_public">https://scale.com/leaderboard/swe_bench_pro_public</a>

* Commercial (Private) Leaderboard: <a href="https://scale.com/leaderboard/swe_bench_pro_commercial">https://scale.com/leaderboard/swe_bench_pro_commercial</a>

## News

(10/28) We added mini-swe-agent! Results are comparable to SWE-Agent for Sonnet 4.5. Feel free to give it a shot. (credit @miguelrc-scale)

(10/28) We have the SWE-Agent scaffold to reproduce results and a step-by-step guide below. We have confirmed that this reproduces the Sonnet 4.5 results. (credit @18vijayb)

(10/3) We have updated results without cap limit here: https://scaleapi.github.io/SWE-bench_Pro-os/

## Overview
SWE-Bench Pro is a challenging benchmark evaluating LLMs/Agents on long-horizon software engineering tasks.
Given a *codebase* and an *issue*, a language model is tasked with generating a *patch* that resolves the described problem.

The dataset is inspired from SWE-Bench: https://github.com/SWE-bench/SWE-bench

To access SWE-bench Pro, copy and run the following code:
```python
from datasets import load_dataset
swebench = load_dataset('ScaleAI/SWE-bench_Pro', split='test')
```

## Setup
SWE-bench Pro uses Docker for reproducible evaluations.
In addition, the evaluation script requires Modal to scale the evaluation set.

Follow the instructions in the [Docker setup guide](https://docs.docker.com/engine/install/) to install Docker on your machine.
If you're setting up on Linux, we recommend seeing the [post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/) as well.

Run the following commands to store modal credentials:
```
pip install modal
modal setup # and follow the prompts to generate your token and secret
```

After running these steps, you should be able to see a token ID and secret in  `~/.modal.toml`:
EG:
```
token_id = <token id>
token_secret = <token secret>
active = true
```

We store prebuilt Docker images for each instance. They can be found in this directory:

https://hub.docker.com/r/jefzda/sweap-images

The format of the images is as follows.

`jefzda/sweap-images:{repo_base}.{repo_name}-{repo_base}__{repo_name}-{hash}`

For example:

`jefzda/sweap-images:gravitational.teleport-gravitational__teleport-82185f232ae8974258397e121b3bc2ed0c3729ed-v626ec2a48416b10a88641359a169d99e935ff03`

Note that bash runs by default in our images. e.g. when running these images, you should not manually envoke bash. See https://github.com/scaleapi/SWE-bench_Pro-os/issues/6

## Usage

### 1. Generate Patches
Generate patch predictions using your harness of choice. 

For generating patches using SWE-agent, see the [SWE-agent git submodule](./SWE-agent/) (note: you will have to use this as a git submodule. See [official git documentation](https://git-scm.com/book/en/v2/Git-Tools-Submodules) for details). The submodule contains detailed instructions to
- Set up SWE-agent for patch generation
- Run SWE-agent on SWE-Bench Pro instances
- Configure model parameters and turn limits

The output will be `.pred` files containing model-generated patches for each instance.

### 2. Gather Patches
After generating patches, use the `gather_patches.py` helper script to collect all patches into a single JSON file for evaluation:

```bash
python helper_code/gather_patches.py \
    --directory <path_to_pred_files> \
    --prefix <model_name> \
    --output <output_file>.json
```

**Parameters:**
- `--directory`: Directory containing instance folders with `.pred` files (e.g., from SWE-agent output or downloaded trajectories)
- `--prefix`: Prefix identifier for your model/run (e.g., "gpt4", "claude-sonnet", "sample1")
- `--output`: Output JSON file path

**Example:**
```bash
python helper_code/gather_patches.py \
    --directory swe_bench_pro_results/sample1 \
    --prefix sample1 \
    --output sample1_patches.json
```

This will create a JSON file in the format expected by the evaluation script:
```json
[
  {
    "instance_id": "instance_...",
    "patch": "diff --git ...",
    "prefix": "sample1"
  }
]
```

### 3. Evaluate Patches
Evaluate patch predictions on SWE-Bench Pro with the following command. (`swe_bench_pro_full.csv` is the CSV in the HuggingFace dataset)

```bash
python swe_bench_pro_eval.py \
    --raw_sample_path=swe_bench_pro_full.csv \
    --patch_path=<your_patches>.json \
    --output_dir=<output_directory> \
    --scripts_dir=run_scripts \
    --num_workers=100 \
    --dockerhub_username=jefzda
```

Replace gold_patches with your patch json, and point raw_sample_path to the SWE-Bench Pro CSV.
Gold Patches can be compiled from the HuggingFace dataset.

## Reproducing Leaderboard Results

To reproduce leaderboard results end-to-end, follow the following steps:

1. Complete setup in the `SWE-agent` submodule. We recommend to use the Docker image to run the scaffold, via `just`.
2. Run the scaffold. We have included an example for Claude Sonnet 4.5 (claude.yaml) but feel free to use any model. It also supports `vllm` for local models. Note that we recommend using the DockerHub images rather than building the Docker images from scratch. You can also execute it locally without Modal.
3. Compile predictions with helper_code/gather_patches.py.
4. Run the evaluation script `swe_bench_pro_eval.py` to run the evaluation script.



