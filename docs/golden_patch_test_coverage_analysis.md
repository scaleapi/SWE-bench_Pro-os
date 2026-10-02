# Golden Patch and Test Coverage Analysis

Generated on 2026-06-08 from `helper_code/sweap_eval_full_v2.jsonl`.

This analysis covers all 731 SWE-bench Pro tasks in the local JSONL dataset. The goal is to characterize the size of the golden patches, the amount of test code added by the test patches, and the practical strength of the benchmark's direct and regression test coverage.

## Methodology

Patch size is counted from unified diffs by summing added and deleted lines, excluding diff metadata lines such as `+++`, `---`, and `diff --git`.

Test coverage is measured using the fields available in the dataset:

| Field | Meaning |
|---|---|
| `patch` | Golden reference solution patch. |
| `test_patch` | Test patch associated with the task. |
| `FAIL_TO_PASS` | Tests expected to fail before the golden patch and pass after it. These are the strongest direct behavioral coverage signal. |
| `PASS_TO_PASS` | Tests expected to pass before and after the patch. These are regression coverage, not direct bug coverage. |

This is not runtime line or branch coverage. The dataset contains test names and test diffs, but not coverage reports. The coverage metrics below should therefore be read as benchmark coverage proxies.

## Executive Insights

| Insight | Evidence | Implication |
|---|---:|---|
| Golden patches are usually modest, but the distribution has a long tail. | Median `94` changed LOC, P90 `403`, max `2,028`. | Most tasks are not huge by LOC, but a small number are much more invasive. |
| Golden patches typically span multiple files. | Median `4` files, P90 `9`, max `106`. | Many tasks require cross-file reasoning instead of isolated local edits. |
| Test patches are smaller than golden patches for the median task. | Median test patch `57` changed LOC vs median golden patch `94` changed LOC. | Tests usually target behavior rather than mirroring implementation size. |
| Direct bug coverage is narrow for many tasks. | Median `FAIL_TO_PASS` count is `3`; 52.0% of tasks have only `1-3` failing tests. | Many fixes are validated by a small number of direct failing tests. |
| Regression coverage dominates total listed tests. | `42,015` `PASS_TO_PASS` tests vs `10,546` `FAIL_TO_PASS` tests. | The benchmark often checks broad non-regression, but direct bug coverage is much smaller. |
| Larger patches are not proportionally better covered. | `1001+` LOC patches have median `7` `FAIL_TO_PASS` tests and `9` total eval tests. | Large changes can still have thin direct behavioral coverage. |
| Coverage behavior is repo-specific. | `qutebrowser` has `5,130` total `FAIL_TO_PASS`; `flipt` has `0` `PASS_TO_PASS`. | Dataset-wide averages hide large differences between repositories. |

## Overall Metrics

| Metric | Total | Mean | Median | P75 | P90 | Max |
|---|---:|---:|---:|---:|---:|---:|
| Golden changed LOC | `123,962` | `169.6` | `94` | `207` | `403` | `2,028` |
| Golden files touched | `3,705` | `5.1` | `4` | `7` | `9` | `106` |
| Test patch changed LOC | `95,572` | `130.7` | `57` | `134` | `273` | `6,498` |
| Test patch files touched | `1,534` | `2.1` | `1` | `2` | `4` | `59` |
| `FAIL_TO_PASS` tests | `10,546` | `14.4` | `3` | `7` | `16` | `1,869` |
| `PASS_TO_PASS` tests | `42,015` | `57.5` | `0` | `30` | `145` | `3,509` |
| Total listed eval tests | `52,561` | `71.9` | `9` | `48` | `171` | `3,510` |

## Golden Patch Size Buckets

| Golden changed LOC | Tasks | Share | Median `FAIL_TO_PASS` | Median total eval tests | Median test patch LOC |
|---|---:|---:|---:|---:|---:|
| `20-50` | `183` | `25.0%` | `2` | `17` | `36` |
| `51-100` | `199` | `27.2%` | `3` | `11` | `45` |
| `101-250` | `209` | `28.6%` | `3` | `7` | `79` |
| `251-500` | `94` | `12.9%` | `5` | `7` | `121` |
| `501-1000` | `35` | `4.8%` | `4` | `4` | `166` |
| `1001+` | `11` | `1.5%` | `7` | `9` | `170` |

The main pattern is that patch size and direct test count do not scale together. The median `1001+` LOC task has only `7` direct failing tests, which means large solution patches are not automatically guarded by proportionally large direct test suites.

## Direct Coverage Buckets

| `FAIL_TO_PASS` tests | Tasks | Share | Median golden LOC | Median test patch LOC |
|---|---:|---:|---:|---:|
| `1` | `209` | `28.6%` | `79` | `34` |
| `2-3` | `171` | `23.4%` | `90` | `44` |
| `4-10` | `231` | `31.6%` | `94` | `88` |
| `11-50` | `94` | `12.9%` | `137.5` | `115.5` |
| `51-200` | `18` | `2.5%` | `127` | `78` |
| `201+` | `8` | `1.1%` | `102` | `446` |

Most tasks sit in the `1-10` direct failing-test range. The very high direct coverage cases are rare and concentrated in specific repositories or specific test layouts.

## Repo-Level View

| Repo | Tasks | Median golden LOC | Median files | Median `FAIL_TO_PASS` | Median `PASS_TO_PASS` | Median test LOC |
|---|---:|---:|---:|---:|---:|---:|
| `ansible/ansible` | `96` | `85.5` | `3` | `4` | `9` | `74` |
| `internetarchive/openlibrary` | `91` | `97` | `3` | `3` | `5` | `42` |
| `flipt-io/flipt` | `85` | `153` | `6` | `2` | `0` | `71` |
| `qutebrowser/qutebrowser` | `79` | `52` | `3` | `5` | `46` | `36` |
| `gravitational/teleport` | `76` | `113` | `3.5` | `3` | `0` | `92.5` |
| `protonmail/webclients` | `65` | `103` | `6` | `4` | `1` | `48` |
| `future-architect/vuls` | `62` | `160.5` | `5` | `4` | `0` | `80.5` |
| `navidrome/navidrome` | `57` | `109` | `6` | `1` | `0` | `48` |
| `element-hq/element-web` | `56` | `81.5` | `4` | `6` | `87` | `96` |
| `NodeBB/NodeBB` | `44` | `74.5` | `4` | `2` | `180.5` | `33.5` |
| `tutao/tutanota` | `20` | `110.5` | `5` | `78` | `0` | `56.5` |

The repo-level split is the clearest reason not to over-interpret global averages. `NodeBB` and `element-web` carry large regression suites through `PASS_TO_PASS`, while repos such as `flipt`, `navidrome`, `teleport`, and `vuls` have median `PASS_TO_PASS` counts of `0`.

## Coverage Proxies

| Coverage proxy | Median | Interpretation |
|---|---:|---|
| `FAIL_TO_PASS / golden changed LOC` | `0.033` | Roughly 1 direct failing test per 30 changed LOC. |
| `Total eval tests / golden changed LOC` | `0.097` | Roughly 1 listed eval test per 10 changed LOC. |
| `Test patch LOC / golden changed LOC` | `0.576` | Median test diff is about 58% of implementation diff size. |
| `FAIL_TO_PASS / golden files touched` | `1.0` | Median task has about 1 direct failing test per touched file. |

These ratios should be used as coarse signals. They do not prove whether every changed line in the golden patch is executed by tests. They do show that direct behavioral coverage is often much thinner than the implementation patch, especially for multi-file changes.

## Notable Outliers

### Largest Golden Patches

| Instance | Repo | Golden LOC | Files | `FAIL_TO_PASS` | Total eval tests | Test LOC |
|---|---|---:|---:|---:|---:|---:|
| `instance_ansible__ansible-c616e54a6e23fa5616a1d56d243f69576164ef9b-v1055803c3a812189a1133297f7f5468579283f86` | `ansible/ansible` | `2,028` | `4` | `6` | `6` | `217` |
| `instance_internetarchive__openlibrary-7f6b722a10f822171501d027cad60afe53337732-ve8c8d62a2b60610a3c4631f5f23ed866bada9818` | `internetarchive/openlibrary` | `1,663` | `13` | `4` | `9` | `273` |
| `instance_flipt-io__flipt-967855b429f749c28c112b8cb1b15bc79157f973` | `flipt-io/flipt` | `1,482` | `5` | `18` | `18` | `92` |
| `instance_gravitational__teleport-3587cca7840f636489449113969a5066025dd5bf` | `gravitational/teleport` | `1,352` | `15` | `1` | `1` | `47` |
| `instance_flipt-io__flipt-cf06f4ebfab7fa21eed3e5838592e8e44566957f` | `flipt-io/flipt` | `1,325` | `5` | `3` | `3` | `94` |

### Largest Listed Test Sets

| Instance | Repo | Golden LOC | Files | `FAIL_TO_PASS` | `PASS_TO_PASS` | Total eval tests |
|---|---|---:|---:|---:|---:|---:|
| `instance_NodeBB__NodeBB-a5afad27e52fd336163063ba40dcadc80233ae10-vd59a5728dfc977f44533186ace531248c2917516` | `NodeBB/NodeBB` | `188` | `12` | `1` | `3,509` | `3,510` |
| `instance_NodeBB__NodeBB-b398321a5eb913666f903a794219833926881a8f-vd59a5728dfc977f44533186ace531248c2917516` | `NodeBB/NodeBB` | `76` | `11` | `4` | `2,980` | `2,984` |
| `instance_tutao__tutanota-f373ac3808deefce8183dad8d16729839cc330c1-v2939aa9f4356f0dc9f523ee5ce19d09e08ab979b` | `tutao/tutanota` | `204` | `9` | `2` | `2,953` | `2,955` |
| `instance_NodeBB__NodeBB-76c6e30282906ac664f2c9278fc90999b27b1f48-vd59a5728dfc977f44533186ace531248c2917516` | `NodeBB/NodeBB` | `620` | `106` | `1` | `2,924` | `2,925` |
| `instance_qutebrowser__qutebrowser-3e21c8214a998cb1058defd15aabb24617a76402-v5fc38aaf22415ab0b70567368332beee7955b367` | `qutebrowser/qutebrowser` | `59` | `1` | `1,869` | `0` | `1,869` |

These outliers show two different coverage patterns. Some tasks have very large regression suites but only a few direct failing tests. Others, especially in `qutebrowser`, can have very large direct failing-test sets for relatively small patches.

## Bottom Line

SWE-bench Pro golden patches usually require multi-file engineering work, but their direct failing-test coverage is often narrow. The benchmark still has meaningful regression pressure in several repositories through `PASS_TO_PASS`, but that regression coverage is unevenly distributed. Any model evaluation should therefore report both direct solve rate and repo-level behavior, because aggregate test counts can hide whether a task was covered by direct failing tests or mostly by broad regression tests.
