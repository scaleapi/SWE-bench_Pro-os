## SWE-Bench Pro

Code and data for the following works:
* <a href="https://static.scale.com/uploads/654197dc94d34f66c0f5184e/SWEAP_Eval_Scale%20(9).pdf">SWE-bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks?</a>

* HuggingFace: <a href="https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro">https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro</a>

* Public Leaderboard: <a href="https://scale.com/leaderboard/swe_bench_pro_public">https://scale.com/leaderboard/swe_bench_pro_public</a>

* Commercial (Private) Leaderboard: <a href="https://scale.com/leaderboard/swe_bench_pro_commercial">https://scale.com/leaderboard/swe_bench_pro_commercial</a>

## 👋 Overview
SWE-Bench Pro is a challenging benchmark evaluating LLMs/Agents on long-horizon software engineering tasks.
Given a *codebase* and an *issue*, a language model is tasked with generating a *patch* that resolves the described problem.

The dataset is inspired from SWE-Bench: https://github.com/SWE-bench/SWE-bench

To access SWE-bench Pro, copy and run the following code:
```python
from datasets import load_dataset
swebench = load_dataset('ScaleAI/SWE-bench_Pro', split='test')
```

## 🚀 Set Up
SWE-bench Pro uses Docker for reproducible evaluations.
In addition, the evaluation script requires Modal to scale the evaluation set.

Follow the instructions in the [Docker setup guide](https://docs.docker.com/engine/install/) to install Docker on your machine.
If you're setting up on Linux, we recommend seeing the [post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/) as well.

Run the following commands to store modal credentials:
```
pip install modal
modalv setup # and follow the prompts to generate your token and secret
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

## 💽 Usage
First generate patch predictions using your harness of choice.
Evaluate patch predictions on SWE-bench Pro with the following command:

```bash
python sweap_pro_eval_modal.py \
    --raw_sample_path=external_hf_v2.csv \
    --patch_path={OUTPUT}/gold_patches.json \
    --output_dir={OUTPUT}/ \
    --scripts_dir=run_scripts \
    --num_workers=100 \
    --dockerhub_username=your-username
```

Replace gold_patches with your patch json, and point raw_sample_path to the SWE-Bench Pro CSV.
