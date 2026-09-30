# SWE-bench Pro harness

This document describes the grading harness invariants for SWE-bench Pro OSS evals.
Run `python scripts/swebench_preflight.py` before `swe_bench_pro_eval.py` to catch
layout and schema issues early.

## Pipeline overview

1. **Generate patches** — agent harness (SWE-agent, mini-swe-agent, etc.) writes `.pred` files
2. **Gather patches** — `helper_code/gather_patches.py` → JSON array
3. **Preflight** — `scripts/swebench_preflight.py` validates JSON + `run_scripts/`
4. **Evaluate** — `swe_bench_pro_eval.py` applies patches in Docker/Modal and runs tests

## Patch JSON format

```json
[
  {
    "instance_id": "instance_org__repo-<hash>",
    "patch": "diff --git a/...",
    "prefix": "gold"
  }
]
```

Required keys: `instance_id`, `patch`, `prefix`. Duplicate `instance_id` values are rejected by preflight.

## Per-instance run scripts

For each `instance_id`, the repo ships:

- `run_scripts/<instance_id>/run_script.sh` — applies patch and runs tests
- `run_scripts/<instance_id>/parser.py` — parses stdout into pass/fail

Preflight fails if either file is missing for a patch entry.

## Known harness footguns

| Issue | Symptom | Mitigation |
|-------|---------|------------|
| [#101](https://github.com/scaleapi/SWE-bench_Pro-os/issues/101) golden patch / sendmail | `[[error:sendmail-not-found]]` in NodeBB email tests | See [GOLDEN_PATCH.md](GOLDEN_PATCH.md) |
| [#93](https://github.com/scaleapi/SWE-bench_Pro-os/issues/93) git history leakage | Agent can `git show` future fix commits | Strip future history in Docker images before eval |
| [#6](https://github.com/scaleapi/SWE-bench_Pro-os/issues/6) bash entrypoint | Manual `bash` breaks eval | Use image entrypoint as documented |

## Binary patch hunks

`swe_bench_pro_eval.py` strips binary diff sections before apply. Preflight warns when
binary hunks are present so maintainers know patches may be incomplete.

## References

- [SWE-bench Pro paper](https://static.scale.com/uploads/654197dc94d34f66c0f5184e/SWEAP_Eval_Scale%20(9).pdf)
- [HuggingFace dataset](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro)
