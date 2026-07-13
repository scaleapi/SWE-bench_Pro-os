# Golden patch verification

Issue [#101](https://github.com/scaleapi/SWE-bench_Pro-os/issues/101): running evaluation with
dataset golden patches can fail on some instances (e.g. NodeBB) with:

```text
[emailer.send] Error: [[error:sendmail-not-found]]
```

The tests in the log may still pass — the error is logged during email setup, not necessarily
as a test failure. Always inspect `test_output.txt` / parser output, not only stderr noise.

## Recommended workflow

### 1. Extract gold patches

```bash
python helper_code/extract_gold_patches.py --output gold_patches.json
```

### 2. Preflight

```bash
python scripts/swebench_preflight.py \
  --patches gold_patches.json \
  --scripts-dir run_scripts
```

NodeBB instances will emit a **WARN** about sendmail — expected for #101-class images.

### 3. Evaluate one instance (local Docker)

```bash
python swe_bench_pro_eval.py \
  --raw_sample_path=<csv_with_one_row> \
  --patch_path=gold_patches.json \
  --output_dir=out/golden-verify/ \
  --scripts_dir=run_scripts \
  --use_local_docker \
  --num_workers=1
```

### 4. Single-instance smoke (example)

Instance from #101:

`instance_NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5-vnan`

Filter `gold_patches.json` and dataset CSV to this `instance_id` before running step 3.

## Interpreting results

| Signal | Meaning |
|--------|---------|
| Parser reports fail-to-pass tests passed | Golden patch valid for grading |
| sendmail error in logs only | Environment noise (#101) — check parser |
| `git apply` failure | Patch/instance mismatch — fix harness before trusting scores |
| Missing `run_scripts/` files | Run preflight — do not publish scores |

## Related issues

- [#93](https://github.com/scaleapi/SWE-bench_Pro-os/issues/93) — git history reward hacking
- [#108](https://github.com/scaleapi/SWE-bench_Pro-os/issues/108) — determinacy audit
