#!/usr/bin/env python3
"""Script to generate 30 example folders from SWE-bench Pro dataset."""

import os
import random
from datasets import load_dataset

def create_example_folder(datapoint, folder_name, index):
    """Create a folder with README and patch files for a datapoint."""

    # Create folder
    os.makedirs(folder_name, exist_ok=True)

    # Extract repo info
    repo = datapoint['repo']
    instance_id = datapoint['instance_id']
    base_commit = datapoint['base_commit']
    problem_statement = datapoint['problem_statement']
    requirements = datapoint.get('requirements', 'N/A')
    interface = datapoint.get('interface', 'N/A')
    language = datapoint['repo_language']

    # Create README.md
    readme_content = f"""# Example {index}: {repo}

## Basic Information

- **Repository:** [{repo}](https://github.com/{repo})
- **Language:** {language}
- **Instance ID:** `{instance_id}`
- **Base Commit:** [`{base_commit}`](https://github.com/{repo}/commit/{base_commit})

## Problem Statement

{problem_statement}

## Requirements

{requirements}

## Interface

{interface}

## Files

- `golden_patch.diff` - The solution patch that solves the issue
- `test_patch.diff` - Test changes to validate the solution

## Setup Commands

```bash
git clone https://github.com/{repo}
cd {repo.split('/')[-1]}
git checkout {base_commit}
```

## Apply Golden Patch

```bash
git apply golden_patch.diff
```

## Apply Test Patch

```bash
git apply test_patch.diff
```
"""

    with open(os.path.join(folder_name, 'README.md'), 'w') as f:
        f.write(readme_content)

    # Write golden patch
    with open(os.path.join(folder_name, 'golden_patch.diff'), 'w') as f:
        f.write(datapoint['patch'])

    # Write test patch
    with open(os.path.join(folder_name, 'test_patch.diff'), 'w') as f:
        f.write(datapoint['test_patch'])

    print(f"Created: {folder_name}")
    return {
        'folder': folder_name,
        'repo': repo,
        'language': language,
        'instance_id': instance_id
    }

def main():
    print("Loading SWE-bench Pro dataset...")
    dataset = load_dataset('ScaleAI/SWE-bench_Pro', split='test')

    # Filter by language
    python_examples = [d for d in dataset if d['repo_language'] == 'python']
    js_examples = [d for d in dataset if d['repo_language'] in ['js', 'ts']]
    go_examples = [d for d in dataset if d['repo_language'] == 'go']

    print(f"Found {len(python_examples)} Python examples")
    print(f"Found {len(js_examples)} JavaScript/TypeScript examples")
    print(f"Found {len(go_examples)} Go examples")

    # Randomly select examples
    random.seed(42)  # For reproducibility
    selected_python = random.sample(python_examples, min(10, len(python_examples)))
    selected_js = random.sample(js_examples, min(10, len(js_examples)))
    selected_go = random.sample(go_examples, min(10, len(go_examples)))

    # Create examples directory
    examples_dir = 'examples'
    os.makedirs(examples_dir, exist_ok=True)

    created_examples = []

    # Create Python examples
    print("\nCreating Python examples...")
    for i, datapoint in enumerate(selected_python, 1):
        folder_name = os.path.join(examples_dir, f'python_{i:02d}')
        result = create_example_folder(datapoint, folder_name, f"Python {i}")
        created_examples.append(result)

    # Create JS/TS examples
    print("\nCreating JavaScript/TypeScript examples...")
    for i, datapoint in enumerate(selected_js, 1):
        folder_name = os.path.join(examples_dir, f'js_{i:02d}')
        result = create_example_folder(datapoint, folder_name, f"JS/TS {i}")
        created_examples.append(result)

    # Create Go examples
    print("\nCreating Go examples...")
    for i, datapoint in enumerate(selected_go, 1):
        folder_name = os.path.join(examples_dir, f'go_{i:02d}')
        result = create_example_folder(datapoint, folder_name, f"Go {i}")
        created_examples.append(result)

    # Create index file
    print("\nCreating index...")
    index_content = """# SWE-Bench Pro Examples

This directory contains 30 curated examples from the SWE-Bench Pro dataset.

## Python Examples (10)

"""

    for example in created_examples[:10]:
        folder_name = os.path.basename(example['folder'])
        index_content += f"- [{folder_name}](./{folder_name}/README.md) - {example['repo']}\n"

    index_content += "\n## JavaScript/TypeScript Examples (10)\n\n"

    for example in created_examples[10:20]:
        folder_name = os.path.basename(example['folder'])
        index_content += f"- [{folder_name}](./{folder_name}/README.md) - {example['repo']}\n"

    index_content += "\n## Go Examples (10)\n\n"

    for example in created_examples[20:30]:
        folder_name = os.path.basename(example['folder'])
        index_content += f"- [{folder_name}](./{folder_name}/README.md) - {example['repo']}\n"

    with open(os.path.join(examples_dir, 'README.md'), 'w') as f:
        f.write(index_content)

    print(f"\n✅ Created {len(created_examples)} examples in '{examples_dir}/' directory")
    print(f"   - {len(created_examples[:10])} Python examples")
    print(f"   - {len(created_examples[10:20])} JavaScript/TypeScript examples")
    print(f"   - {len(created_examples[20:30])} Go examples")

if __name__ == '__main__':
    main()
