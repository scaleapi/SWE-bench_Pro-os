# Model Error Taxonomy

This analysis summarizes the LLM-as-a-judge error analyses in:

- `error_analysis/claude_sonnet_4.csv`
- `error_analysis/gpt4o.csv`

Each CSV row contains an `instance_id`, a judge-provided `category`, and a free-text `rationale`.

## Taxonomy

Each failed instance is assigned one primary root-cause class. Secondary tags can also apply when the rationale contains evidence for more than one failure mode.

| Failure mode | Definition |
| --- | --- |
| `CONTEXT_EXHAUSTION_UNFOCUSED_EXPLORATION` | The run spent its budget/context on broad listings, repeated file reads, or unfocused exploration before producing a useful patch. |
| `EDIT_TOOL_MISUSE` | The failure was primarily caused by incorrect use of editing tools, such as brittle or non-unique replacements, failed patches, or partial insertions. |
| `SYNTACTIC_OR_BUILD_BREAKAGE` | The produced artifacts were syntactically invalid or broke compile/import/build execution. |
| `WRONG_OR_INCOMPLETE_SOLUTION` | The agent changed code, but the implementation was logically wrong, incomplete, overbroad, or failed to satisfy the requested behavior. |
| `WRONG_LOCATION_OR_STACK` | The agent worked in the wrong file, module, language, generated script, or execution stack instead of the production code under test. |
| `PROBLEM_MISUNDERSTANDING` | The agent misunderstood the requested behavior or pursued an unrelated concern. |
| `NO_SUBSTANTIVE_PROGRESS` | The trajectory produced no meaningful implementation work, often stopping after shallow inspection or an ineffective loop. |
| `OTHER_UNCLASSIFIED` | The available rationale does not cleanly identify one dominant root cause. |

## Classification Method

The classifier is deterministic and rule-based:

1. Use the judge category as a high-confidence direct signal when it maps cleanly to a taxonomy class.
2. Search the rationale text for evidence phrases such as `cost limit`, `str_replace`, `syntax`, `wrong file`, `python script`, `misunderstood`, `no patch`, and `incomplete`.
3. Assign every matched class as a tag.
4. Select the primary class by direct judge-category mapping first. If there is no direct mapping, choose the highest-scoring keyword class using a fixed precedence order.
5. Preserve the original judge category, primary taxonomy class, secondary tags, evidence hits, and full rationale in the classified outputs.

## Breakdown by Model

| Failure mode | Claude Sonnet 4 | GPT-4o |
| --- | ---: | ---: |
| `CONTEXT_EXHAUSTION_UNFOCUSED_EXPLORATION` | 390 (73.2%) | 2 (0.3%) |
| `WRONG_OR_INCOMPLETE_SOLUTION` | 70 (13.1%) | 217 (34.8%) |
| `EDIT_TOOL_MISUSE` | 33 (6.2%) | 171 (27.4%) |
| `SYNTACTIC_OR_BUILD_BREAKAGE` | 24 (4.5%) | 164 (26.3%) |
| `WRONG_LOCATION_OR_STACK` | 9 (1.7%) | 48 (7.7%) |
| `PROBLEM_MISUNDERSTANDING` | 7 (1.3%) | 20 (3.2%) |
| `NO_SUBSTANTIVE_PROGRESS` | 0 (0.0%) | 2 (0.3%) |
| `OTHER_UNCLASSIFIED` | 0 (0.0%) | 0 (0.0%) |

Claude Sonnet 4's errors are dominated by context exhaustion and unfocused exploration. GPT-4o's errors are dominated by implementation failures: wrong or incomplete solutions, edit-tool misuse, and syntax/build breakage.
