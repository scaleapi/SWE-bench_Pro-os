# SWE-Bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks?

**Scale AI Research Team**

**Paper**: [https://arxiv.org/abs/2509.16941](https://arxiv.org/abs/2509.16941)
**Dataset**: [https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro)
**Leaderboard**: [https://scale.com/leaderboard/swe_bench_pro_public](https://scale.com/leaderboard/swe_bench_pro_public)

---

## Abstract

SWE-Bench Pro is a challenging benchmark designed to evaluate AI agents on realistic, long-horizon software engineering tasks. The benchmark addresses critical limitations in existing evaluation frameworks by focusing on **data contamination resistance**, **enterprise-grade task complexity**, and **reliable testing infrastructure**. It contains **1,865 problems** across **41 actively maintained repositories**, including both GPL-licensed open-source projects and proprietary commercial codebases from real startups.

Unlike previous benchmarks where models achieve >70% resolution rates, current frontier models achieve only **23.3% - 43.6%** on SWE-Bench Pro, revealing significant gaps between AI capabilities and professional software engineering requirements.

---

## 1. Introduction

### Motivation

Modern software engineering requires complex reasoning across large codebases, understanding nuanced requirements, and implementing changes that span multiple files and subsystems. While recent AI agents show promise on simplified benchmarks, their performance on realistic enterprise tasks remains unclear.

SWE-Bench Pro addresses four critical challenges in existing benchmarks:

1. **Data Contamination**: Models likely encountered evaluation code during training, making it difficult to distinguish problem-solving from memorization
2. **Limited Task Diversity**: Many benchmarks focus on simple utility libraries rather than real business applications
3. **Oversimplified Problems**: Ambiguous or underspecified issues are filtered out, unlike real developer workflows
4. **Unreliable Testing**: Inconsistent test environments make it hard to verify if solutions truly work

### Key Contributions

1. **Contamination-Resistant Dataset**: Novel collection strategy using GPL-licensed repositories and commercial codebases
2. **Complex, Long-Horizon Tasks**: Average of 107.4 line changes across 4.1 files per problem
3. **Human-Augmented Specifications**: Three-stage verification process ensuring clarity and resolvability
4. **Comprehensive Evaluation**: Detailed failure mode analysis revealing model-specific weaknesses

---

## 2. Dataset Construction

### 2.1 Sourcing Strategy

**Public Set (731 instances, 11 repositories)**
- Exclusively GPL-licensed open-source projects
- Legal deterrent against inclusion in proprietary training data
- Diverse applications: business tools, developer platforms, infrastructure software

**Commercial Set (276 instances, 18 repositories)**
- Proprietary codebases from real startups
- Sourced through Scale AI partnerships and acquisitions
- Enterprise-grade complexity with intricate business logic
- Results publicly released; codebases remain private

**Held-Out Set (858 instances, 12 repositories)**
- Reserved for future validation against overfitting
- GPL-licensed repositories not initially disclosed

### 2.2 Repository Selection Criteria

Selected repositories must demonstrate:
- **Active Maintenance**: Regular commits and active development
- **Comprehensive Test Coverage**: Robust test suites for validation
- **Real-World Usage**: Production applications with actual users
- **Complexity**: Non-trivial business logic and architectural patterns

**Language Distribution**: Python, Go, JavaScript, TypeScript, and others

**Domain Coverage**:
- Business applications with complex UI/UX logic
- B2B services with sophisticated backend systems
- Developer tools with advanced APIs and integrations

### 2.3 Four-Stage Workflow

#### Stage 1: Sourcing
Curate repositories meeting selection criteria from both public (GPL) and private (commercial) sources.

#### Stage 2: Environment Creation
Professional engineers build **reproducible Docker environments** for each repository:
- Install all dependencies and build tools
- Configure databases and external services
- Ensure tests run reliably out-of-the-box
- Verify consistent execution across multiple runs

**Quality Control**: Human verification of environment correctness

#### Stage 3: Harvesting
Analyze commit history to identify suitable problems:
- Require **fail-to-pass test transitions**: commits must include new tests that fail before the change and pass after
- Filter commits with exactly one associated issue/PR
- Exclude commits without clear problem descriptions
- Minimum change threshold: 10 lines modified

**Automated Filters**:
- Remove flaky tests (inconsistent results across runs)
- Eliminate overly broad test modifications
- Filter out dependency-only updates

#### Stage 4: Human Augmentation
Expert engineers enhance problem specifications with three components:

1. **Problem Statement**: Clear description derived from original GitHub issues/PRs
   - Maintains authentic developer language
   - Adds clarification where necessary
   - Removes ambiguity while preserving realistic complexity

2. **Requirements**: Behavioral specifications grounded in test expectations
   - Explicit expected behaviors
   - Edge case handling requirements
   - Integration with existing functionality

3. **Interface Definitions**: Explicit class/function signatures
   - Prevents false negatives from naming mismatches
   - Clarifies expected API structure
   - Reduces specification ambiguity

**Three Human-in-the-Loop Checkpoints**:
- ✓ Environment construction verification
- ✓ Issue description clarity review
- ✓ Test relevance validation

---

## 3. Quality Control Measures

### 3.1 Contamination Resistance

**GPL License Strategy**:
- Strong copyleft licenses create legal barriers to inclusion in commercial training datasets
- Public set repositories exclusively use GPL, AGPL, or similar licenses
- Held-out set follows same licensing strategy
- Legal teams at major AI companies typically exclude GPL code from training corpora

**Commercial Set Protection**:
- Proprietary codebases never publicly released
- Accessed only through secure partnerships
- Cannot be web-scraped or incorporated into training data
- Represents truly unseen enterprise complexity

### 3.2 Task Complexity Validation

**Minimum Complexity Thresholds**:
- At least 10 lines of code changes required
- Median: 107.4 lines across 4.1 files
- Over 100 tasks exceed 100-line modifications
- Multi-file changes common (not isolated edits)

**Complexity Distribution**:
- **Trivial problems filtered out**: Unlike SWE-Bench Verified (161/500 one-line fixes)
- **Long-horizon reasoning required**: Changes span multiple subsystems
- **Integration complexity**: Must maintain existing functionality

### 3.3 Test Suite Validation

**Reliability Checks**:
- Run tests multiple times to identify flaky tests
- Verify gold patches pass 100% of tests
- Ensure fail-to-pass tests actually fail before the fix
- Validate pass-to-pass tests remain passing

**Human Review**:
- Engineers verify test relevance to problem statement
- Remove overly broad or unrelated tests
- Ensure tests accurately capture expected behavior
- Check for false positive/negative potential

### 3.4 Environment Verification

**Reproducibility Testing**:
- Docker containers built and tested on multiple systems
- Dependency resolution verified across clean environments
- Database initialization and seeding validated
- External service mocks properly configured

**Consistency Validation**:
- Same test results across multiple runs
- No race conditions or timing dependencies
- Deterministic execution guaranteed
- Platform independence verified (Linux, macOS, Windows where applicable)

---

## 4. Benchmark Structure

### 4.1 Instance Format

Each SWE-Bench Pro instance includes:

```python
{
  "instance_id": "unique_identifier",
  "repo": "repository_name",
  "base_commit": "commit_hash",
  "problem_statement": "Human-readable issue description",
  "requirements": "Explicit behavioral specifications",
  "interface": "Expected class/function signatures",
  "fail_to_pass": ["test_case_1", "test_case_2"],  # Must pass after fix
  "pass_to_pass": ["test_case_3", "test_case_4"],  # Must remain passing
  "environment_setup_commit": "commit_hash",
  "test_patch": "diff_with_new_tests",
  "hints_text": "Optional guidance from original issue"
}
```

### 4.2 Dataset Statistics

| Metric | Value |
|--------|-------|
| **Total Problems** | 1,865 |
| **Public Set** | 731 instances |
| **Commercial Set** | 276 instances |
| **Held-Out Set** | 858 instances |
| **Total Repositories** | 41 |
| **Languages** | Python, Go, JS/TS, others |
| **Avg. Lines Changed** | 107.4 |
| **Avg. Files Modified** | 4.1 |
| **Min. Lines Changed** | 10 |
| **Problems >100 Lines** | 100+ |

---

## 5. Evaluation Methodology

### 5.1 Resolution Criteria

A problem is considered **resolved** if and only if:

1. **All fail-to-pass tests pass**: The patch implements the required functionality
2. **All pass-to-pass tests pass**: No regressions introduced in existing functionality

Both conditions must be satisfied for a successful resolution.

### 5.2 Metrics

**Primary Metric: Resolve Rate (Pass@1)**
- Percentage of problems successfully resolved on first attempt
- Single evaluation per instance (no retry attempts)
- Binary outcome: resolved or failed

**Failure Mode Analysis**:
- Wrong solution (incorrect semantic understanding)
- Syntax errors (malformed code)
- Context overflow (exceeding token limits)
- Excessive file reading (inefficient exploration)
- Tool use errors (incorrect API usage)
- Format errors (invalid patch format)

### 5.3 Evaluation Infrastructure

**Docker-Based Execution**:
- Isolated environments per instance
- Consistent dependency versions
- Reproducible test execution
- Timeout limits (30 minutes per instance)

**Scaling with Modal**:
- Parallel evaluation across 100+ workers
- Efficient resource utilization
- Cost-effective at scale

---

## 6. Experimental Results

### 6.1 Model Performance (Public Set)

| Model | Resolve Rate | Year |
|-------|--------------|------|
| **Claude Sonnet 4.5** | 43.6% | 2025 |
| **GPT-5** | 23.3% | 2025 |
| **Claude Opus 4.1** | 22.7% | 2024 |
| **Claude Sonnet 4** | 17.6% | 2024 |
| **Gemini 2.5 Pro** | 13.5% | 2025 |
| **GPT-4o** | 4.9% | 2024 |

**Key Observations**:
- Massive difficulty increase vs. SWE-Bench Verified (>70% on previous benchmarks)
- Clear separation between frontier and mid-tier models
- Open-source models struggle significantly (<5%)

### 6.2 Commercial Set Results

| Model | Resolve Rate |
|-------|--------------|
| **Claude Opus 4.1** | 17.8% |
| **GPT-5** | 14.9% |
| **Claude Sonnet 4** | 12.3% |

**Insight**: Commercial codebases prove even more challenging than public repositories, likely due to:
- More complex business logic
- Less standardized architecture
- Proprietary frameworks and patterns
- Sparser documentation

### 6.3 Performance by Language

| Language | Best Model Performance |
|----------|------------------------|
| **Python** | 30-45% (varies by repo) |
| **Go** | 25-40% |
| **JavaScript** | 15-35% |
| **TypeScript** | 10-30% |

Language-specific challenges:
- **Python**: Type ambiguity, dynamic features
- **Go**: Concurrency patterns, interface satisfaction
- **JavaScript**: Asynchronous complexity, DOM manipulation
- **TypeScript**: Complex type inference, generic constraints

### 6.4 Performance by Repository

Significant variation across repositories (some <10%, others >50%), indicating:
- **Codebase structure** affects difficulty
- **Documentation quality** impacts understanding
- **Test coverage** influences validation
- **Domain complexity** varies widely

---

## 7. Failure Mode Analysis

### 7.1 LLM-as-a-Judge Methodology

Failed instances analyzed using frontier models to categorize error types:
- Prompt: "Given the problem statement, patch, and test results, categorize the failure reason"
- Categories: Wrong solution, syntax error, context overflow, tool use error, format error

### 7.2 Frontier Model Failures (GPT-5, Claude Opus 4.1)

| Failure Type | Percentage |
|--------------|------------|
| **Wrong Solution** | 35.9% |
| **Syntax Errors** | 24.2% |
| **Context Issues** | 18.5% |
| **Tool Use Errors** | 12.7% |
| **Format Errors** | 8.7% |

**Key Insight**: Frontier models primarily struggle with **semantic understanding** rather than technical execution. They can write syntactically correct code but often misunderstand the problem requirements.

### 7.3 Mid-Tier Model Failures (Claude Sonnet 4)

| Failure Type | Percentage |
|--------------|------------|
| **Context Overflow** | 35.6% |
| **Wrong Solution** | 26.3% |
| **Excessive File Reading** | 17.0% |
| **Syntax Errors** | 13.4% |
| **Format Errors** | 7.7% |

**Key Insight**: Mid-tier models struggle with **context management**, frequently exceeding token limits through inefficient exploration.

### 7.4 Open-Source Model Failures (Qwen3 32B)

| Failure Type | Percentage |
|--------------|------------|
| **Syntax/Format Errors** | 47.7% |
| **Tool Use Errors** | 42.0% |
| **Wrong Solution** | 8.3% |
| **Context Issues** | 2.0% |

**Key Insight**: Open-source models struggle with **technical execution** - incorrect API usage, malformed patches, and syntax errors.

---

## 8. Insights and Analysis

### 8.1 The Complexity Gap

**From SWE-Bench Verified to SWE-Bench Pro**:
- Resolution rates dropped from >70% to <45%
- Average lines changed increased from ~20 to ~107
- Multi-file changes became the norm
- Real business logic replaced utility functions

**This gap reveals**:
- Current models handle isolated changes well
- Complex reasoning across subsystems remains challenging
- Enterprise codebases pose unique difficulties
- Long-horizon planning capabilities are limited

### 8.2 Model Capability Tiers

**Tier 1: Frontier Models (>20% resolve rate)**
- Strong technical execution
- Struggle with complex semantic understanding
- Can navigate large codebases
- Limited by reasoning depth

**Tier 2: Mid-Tier Models (10-20% resolve rate)**
- Context management issues
- Inefficient exploration strategies
- Reasonable understanding when context fits
- Resource-constrained

**Tier 3: Open-Source Models (<10% resolve rate)**
- Technical execution problems
- Tool use challenges
- Limited context windows
- Need significant improvement

### 8.3 Task Characteristics Affecting Difficulty

**Easier Tasks** (>50% resolution):
- Clear, unambiguous requirements
- Localized changes (1-2 files)
- Straightforward test failures
- Good documentation

**Harder Tasks** (<10% resolution):
- Ambiguous or underspecified requirements
- Cross-cutting concerns (5+ files)
- Complex integration logic
- Sparse documentation

---

## 9. Limitations

### 9.1 Current Limitations

1. **Language Coverage**
   - Underrepresentation of Java, C++, Rust
   - Focus on web/backend languages
   - Limited systems programming tasks

2. **Task Scope**
   - Restricted to patch-based resolution
   - No system design or architecture tasks
   - No code review or collaboration scenarios

3. **Evaluation Constraints**
   - Dependency on test suite quality
   - Single correct solution assumption
   - No evaluation of code quality or maintainability

4. **Specification Trade-offs**
   - Human augmentation may reduce authentic ambiguity
   - Interface definitions provide hints
   - More structured than real GitHub issues

### 9.2 Potential Biases

- **Repository Selection**: Manual curation may introduce bias
- **Test Coverage**: Higher-quality projects may not represent typical codebases
- **Human Augmentation**: Engineers may unconsciously simplify problems
- **License Restriction**: GPL requirement limits repository diversity

---

## 10. Future Work

### 10.1 Recommended Extensions

1. **Expanded Language Coverage**
   - Add Java, C++, Rust repositories
   - Include mobile development (Swift, Kotlin)
   - Systems programming tasks

2. **Broader Task Types**
   - System architecture design
   - Code review and critique
   - Performance optimization
   - Security vulnerability analysis

3. **Multi-Agent Scenarios**
   - Collaborative problem-solving
   - Agent-to-agent communication
   - Distributed debugging

4. **Enhanced Metrics**
   - Code quality assessment
   - Maintainability scoring
   - Security analysis
   - Performance impact measurement

### 10.2 Research Directions

1. **Contamination Detection**
   - Techniques to identify memorization vs. reasoning
   - Held-out set validation
   - Synthetic benchmark generation

2. **Automated Quality Control**
   - ML-based test relevance detection
   - Automated flaky test identification
   - Complexity estimation algorithms

3. **Agent Capabilities**
   - Improved context management strategies
   - Efficient codebase exploration
   - Better semantic understanding
   - Long-horizon planning algorithms

---

## 11. Conclusion

SWE-Bench Pro establishes a new, more rigorous standard for evaluating AI agents on software engineering tasks. By addressing contamination concerns, increasing task complexity, and incorporating enterprise codebases, it reveals significant gaps between current AI capabilities and professional development requirements.

**Key Takeaways**:

1. **Current models are not ready for autonomous enterprise development**
   - Even frontier models resolve <45% of tasks
   - Commercial codebases prove even harder
   - Multi-file reasoning remains challenging

2. **Contamination resistance is critical**
   - GPL licensing provides legal deterrent
   - Commercial codebases ensure freshness
   - Held-out set validates against overfitting

3. **Human augmentation improves clarity without oversimplification**
   - Three-stage verification ensures quality
   - Maintains realistic complexity
   - Reduces false negatives

4. **Comprehensive failure analysis guides improvement**
   - Frontier models need better reasoning
   - Mid-tier models need context efficiency
   - Open-source models need technical execution

SWE-Bench Pro provides researchers with a challenging, realistic benchmark for measuring progress toward truly autonomous software engineering agents. The gap between current performance and professional requirements highlights exciting opportunities for future research.

---

## Data Access

- **Public Dataset**: 731 instances available at [HuggingFace](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro)
- **Commercial Results**: Performance metrics published; codebases remain proprietary
- **Held-Out Set**: Reserved for future validation; not currently public
- **Code & Evaluation**: [GitHub Repository](https://github.com/scaleapi/SWE-bench_Pro-os)

---

## Citation

```bibtex
@article{sweбench_pro_2025,
  title={SWE-Bench Pro: Can AI Agents Solve Long-Horizon Software Engineering Tasks?},
  author={Scale AI Research Team},
  journal={arXiv preprint arXiv:2509.16941},
  year={2025}
}
```

---

## Acknowledgments

This benchmark was created through collaboration between:
- Scale AI Research Team
- Partner startups providing commercial codebases
- Open-source communities maintaining GPL-licensed repositories
- Professional engineers conducting human augmentation and validation

---

## Sources

- [SWE-Bench Pro Paper (arXiv)](https://arxiv.org/abs/2509.16941)
- [SWE-Bench Pro Dataset (HuggingFace)](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro)
- [Public Leaderboard](https://scale.com/leaderboard/swe_bench_pro_public)
- [Commercial Leaderboard](https://scale.com/leaderboard/swe_bench_pro_commercial)
- [Scale AI Blog Post](https://scale.com/blog/swe-bench-pro)
- [GitHub Repository](https://github.com/scaleapi/SWE-bench_Pro-os)
