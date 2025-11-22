#!/usr/bin/env python3
"""Check available languages in SWE-bench Pro dataset."""

from collections import Counter
from datasets import load_dataset

print("Loading SWE-bench Pro dataset...")
dataset = load_dataset('ScaleAI/SWE-bench_Pro', split='test')

# Count languages
language_counts = Counter(d['repo_language'] for d in dataset)

print("\nAvailable languages in SWE-bench Pro:")
print("="*50)
for lang, count in sorted(language_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"{lang:20s}: {count:4d} examples")
print("="*50)
print(f"Total: {len(dataset)} examples")
