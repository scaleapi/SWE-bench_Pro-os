# SWE-bench Pro Public Task Analysis

Date: 2026-06-08

This note summarizes the public SWE-bench Pro task set in this repository and
documents how the repository, language, and task-type breakdowns were produced.

## Source of Truth

The public benchmark task count should be taken from:

- `helper_code/sweap_eval_full_v2.jsonl`

That JSONL contains 731 rows, matching the public leaderboard report. Counting
`run_scripts/` directly is too broad in this checkout: `run_scripts/` contains
1,000 local instance directories.

Comparison between the JSONL and local run scripts:

| Measure | Count |
|---|---:|
| Public dataset rows in `helper_code/sweap_eval_full_v2.jsonl` | 731 |
| Local `run_scripts/instance_*` directories | 1,000 |
| Public dataset IDs with matching run scripts | 731 |
| Extra local run scripts not referenced by the public JSONL | 269 |
| Public dataset IDs missing run scripts | 0 |

The 269 extra local run scripts are not part of the current public task set
because their `instance_id`s do not appear in `helper_code/sweap_eval_full_v2.jsonl`.

Extra local scripts by repository:

| Repository | Extra Scripts |
|---|---:|
| element-hq/element-web | 80 |
| navidrome/navidrome | 57 |
| tutao/tutanota | 54 |
| gravitational/teleport | 17 |
| internetarchive/openlibrary | 13 |
| ansible/ansible | 12 |
| protonmail/webclients | 11 |
| qutebrowser/qutebrowser | 10 |
| NodeBB/NodeBB | 7 |
| flipt-io/flipt | 6 |
| future-architect/vuls | 2 |

## Public Task Breakdown

Total public tasks: 731

### By Repository

| Repository | Language | Tasks | Percent |
|---|---:|---:|---:|
| ansible/ansible | Python | 96 | 13.1% |
| internetarchive/openlibrary | Python | 91 | 12.4% |
| flipt-io/flipt | Go | 85 | 11.6% |
| qutebrowser/qutebrowser | Python | 79 | 10.8% |
| gravitational/teleport | Go | 76 | 10.4% |
| protonmail/webclients | TypeScript | 65 | 8.9% |
| future-architect/vuls | Go | 62 | 8.5% |
| navidrome/navidrome | Go | 57 | 7.8% |
| element-hq/element-web | TypeScript | 56 | 7.7% |
| NodeBB/NodeBB | JavaScript | 44 | 6.0% |
| tutao/tutanota | TypeScript | 20 | 2.7% |

### By Language Type

Language was mapped from each repository's primary implementation language, not
inferred per changed file.

| Language | Tasks | Percent |
|---|---:|---:|
| Go | 280 | 38.3% |
| Python | 266 | 36.4% |
| TypeScript | 141 | 19.3% |
| JavaScript | 44 | 6.0% |

### By Task Type

The dataset does not include an official `task_type` column. These categories
were derived with a deterministic keyword classifier over `problem_statement`.

| Task Type | Tasks | Percent |
|---|---:|---:|
| Security/Auth | 194 | 26.5% |
| UI/UX | 174 | 23.8% |
| Bug Fix | 95 | 13.0% |
| Feature/Enhancement | 81 | 11.1% |
| Performance/Optimization | 77 | 10.5% |
| Refactor/Maintenance | 63 | 8.6% |
| Tests/CI/Tooling | 45 | 6.2% |
| Unclassified/General Fix | 2 | 0.3% |

## Deterministic Task-Type Classification

Classification used only each row's `problem_statement`, not `patch` or
`test_patch`. An earlier classifier pass included patches and over-counted
Tests/CI/Tooling because every benchmark task includes test patches.

For each row:

1. Extract a title from common Markdown patterns:
   - `# Title: ...`
   - `# ...`
   - `**Title: ...**`
   - `Title: ...`
2. Lowercase the extracted title plus the first 2,500 characters of the problem
   statement.
3. Apply ordered regex rules. First match wins.
4. Fall back to `Unclassified/General Fix`.

Classifier order:

1. Security/Auth
2. Performance/Optimization
3. UI/UX
4. Tests/CI/Tooling
5. Refactor/Maintenance
6. Feature/Enhancement
7. Bug Fix
8. Unclassified/General Fix

Representative keyword groups:

| Task Type | Representative Keywords |
|---|---|
| Security/Auth | security, vulnerable, cve, authentication, authorization, permission, login, logout, password, token, oauth, saml, oidc, 2fa, mfa, encrypt, decrypt, crypto, certificate, tls, ssl, xss, csrf, secret, credential |
| Performance/Optimization | performance, optimize, slow, speed, latency, timeout, hang, deadlock, memory leak, cache, efficient, expensive, scale, rate limit, throughput |
| UI/UX | ui, ux, user interface, frontend, button, modal, dialog, screen, page, view, display, render, layout, css, style, theme, tooltip, form, toast, accessibility, keyboard, focus, mobile, responsive, visual |
| Tests/CI/Tooling | testing, pytest, jest, unit test, integration test, ci, workflow, lint, eslint, ruff, mypy, build system, docker, script, cli, tooling, harness |
| Refactor/Maintenance | refactor, cleanup, rename, reorganize, move file, deprecated, migration, compatibility, upgrade, dependency, maintainability, technical debt |
| Feature/Enhancement | feature request, enhancement, add support, implement, new endpoint, new api, allow users, ability to, introduce, provide, enable, create |
| Bug Fix | bug, fix, incorrect, wrong, failure, error, exception, crash, broken, regression, cannot, unable, expected behavior, actual behavior |

## Reproduction Snippets

Count public rows:

```bash
wc -l helper_code/sweap_eval_full_v2.jsonl
```

Compare public IDs to local run scripts:

```python
import json
from pathlib import Path

ids = {
    json.loads(line)["instance_id"]
    for line in open("helper_code/sweap_eval_full_v2.jsonl")
    if line.strip()
}
scripts = {p.name for p in Path("run_scripts").iterdir() if p.is_dir()}

print("dataset ids", len(ids))
print("run_scripts dirs", len(scripts))
print("overlap", len(ids & scripts))
print("extra scripts not in dataset", len(scripts - ids))
print("dataset ids missing scripts", len(ids - scripts))
```

## Caveats

- Repository counts are exact from `helper_code/sweap_eval_full_v2.jsonl`.
- Language counts are mapped by repository, not by individual changed files.
- Task-type counts are heuristic, deterministic, and reproducible, but they are
  not official benchmark annotations.
- Some tasks span multiple categories. Because first match wins, a task with
  both authentication and UI language is classified as Security/Auth.
