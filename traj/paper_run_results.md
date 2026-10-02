# SWE-bench Pro Paper Run Results

This note summarizes the local `*-paper` result manifests under `traj/`.
Each `eval_results.json` file maps a SWE-bench Pro `instance_id` to a boolean
pass/fail result for that model run.

The counts below use the number of recorded results in each manifest as the
denominator. They are not normalized to the full local benchmark set.

| Model run | Recorded instances | Solved | Failed | Solve rate |
|---|---:|---:|---:|---:|
| `claude-sonnet-4-paper` | 663 | 166 | 497 | 25.0% |
| `claude-opus-4-1-paper` | 891 | 206 | 685 | 23.1% |
| `gptoss-paper` | 728 | 118 | 610 | 16.2% |
| `gemini-2-5-pro-preview-paper` | 955 | 105 | 850 | 11.0% |
| `gpt-4o-paper` | 619 | 36 | 583 | 5.8% |

## Denominator Notes

The local `run_scripts/` directory contains 1000 benchmark instance directories.
The paper result manifests are strict subsets of those local instances: they do
not contain extra instance ids outside `run_scripts/`, but each manifest omits a
different number of instances.

| Model run | Missing from local 1000-instance set |
|---|---:|
| `claude-opus-4-1-paper` | 109 |
| `claude-sonnet-4-paper` | 337 |
| `gemini-2-5-pro-preview-paper` | 45 |
| `gpt-4o-paper` | 381 |
| `gptoss-paper` | 272 |

The `traj/README.md` distinguishes the paper runs from later dated leaderboard
runs. Paper runs were included in the paper with a $2 cost limit, while dated
leaderboard runs used a shared configuration with a 250-turn limit and no cost
limit. Because the local paper manifests are per-run artifacts rather than a
single normalized 1000-row benchmark table, the correct interpretation is:
each denominator is the number of instances with recorded results for that
specific paper run.
