#!/usr/bin/env python3
"""Script to extract patches from a specific SWE-bench Pro datapoint."""

from datasets import load_dataset

# Load the dataset
print("Loading SWE-bench Pro dataset...")
dataset = load_dataset('ScaleAI/SWE-bench_Pro', split='test')

# Get datapoint #145
datapoint = dataset[145]

# Write golden patch
with open('golden_patch_145.diff', 'w') as f:
    f.write(datapoint['patch'])

# Write test patch
with open('test_patch_145.diff', 'w') as f:
    f.write(datapoint['test_patch'])

print("Created files:")
print("  - golden_patch_145.diff")
print("  - test_patch_145.diff")
