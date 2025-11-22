#!/usr/bin/env python3
"""Script to show a random datapoint from SWE-bench Pro dataset."""

import random
from datasets import load_dataset

# Load the dataset
print("Loading SWE-bench Pro dataset...")
dataset = load_dataset('ScaleAI/SWE-bench_Pro', split='test')

# Select a random datapoint
random_idx = random.randint(0, len(dataset) - 1)
datapoint = dataset[random_idx]

print(f"\n{'='*80}")
print(f"Random Datapoint #{random_idx} from SWE-bench Pro")
print(f"{'='*80}\n")

# Display the datapoint
for key, value in datapoint.items():
    print(f"{key}:")
    if isinstance(value, str) and len(value) > 500:
        print(f"  {value[:500]}...")
        print(f"  ... (truncated, total length: {len(value)} chars)")
    else:
        print(f"  {value}")
    print()
