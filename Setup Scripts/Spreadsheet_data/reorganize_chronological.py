#!/usr/bin/env python3
"""
Reorganize swebench_pro_grouped_chronological.json to match the true chronological order
from Chronological_branches.txt.

The text file has the true order (line 1 = first chronologically).
This script reorders each repository's commits to match that order.
"""

import json
from pathlib import Path
from collections import defaultdict

def main():
    script_dir = Path(__file__).parent
    workspace_dir = script_dir.parent
    
    # Read the true chronological order from the text file
    branches_file = workspace_dir / "Chronological_branches.txt"
    with open(branches_file, 'r') as f:
        chronological_order = [line.strip() for line in f if line.strip()]
    
    # Create a mapping: instance_id -> chronological position (1-indexed)
    instance_to_position = {instance_id: idx + 1 for idx, instance_id in enumerate(chronological_order)}
    
    # Read the existing JSON file
    json_file = script_dir / "swebench_pro_grouped_chronological.json"
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Group instances by repo from the chronological order
    repo_order = defaultdict(list)
    for instance_id in chronological_order:
        # Extract repo name from instance_id
        # Format: instance_<owner>__<repo>-<commit>-<version>
        # e.g., instance_ansible__ansible-0ea40e09d1b35bcb69ff4d9cecf3d0defa4b36e8-v30a923fb5c164d6cd18280c02422f75e611e8fb2
        # Note: owner/repo names can contain hyphens, so we split on "__" first
        without_prefix = instance_id.replace("instance_", "")
        # Split on "__" to get owner and the rest
        owner_repo_split = without_prefix.split("__", 1)
        owner = owner_repo_split[0]
        # The repo name is everything before the first hyphen followed by a commit hash (40 hex chars)
        rest = owner_repo_split[1]
        # Find the repo name by looking for pattern: reponame-<40 hex chars>
        import re
        match = re.match(r'^([^-]+(?:-[^-]+)*?)-([a-f0-9]{40})', rest)
        if match:
            repo_name_part = match.group(1)
        else:
            # Fallback: split on first hyphen
            repo_name_part = rest.split("-", 1)[0]
        repo_key = f"{owner}/{repo_name_part}"
        repo_order[repo_key].append(instance_id)
    
    # Reorganize each repository's commits
    for repo_name, repo_data in data["repositories"].items():
        if repo_name not in repo_order:
            print(f"Warning: {repo_name} not found in chronological order")
            continue
        
        # Get the ordered instance_ids for this repo
        ordered_instances = repo_order[repo_name]
        
        # Create a mapping from instance_id to commit data
        instance_to_commit = {commit["instance_id"]: commit for commit in repo_data["commits"]}
        
        # Reorder commits based on chronological order
        new_commits = []
        for idx, instance_id in enumerate(ordered_instances, start=1):
            if instance_id in instance_to_commit:
                commit = instance_to_commit[instance_id].copy()
                commit["problem_number"] = idx  # Update problem number to reflect new order
                new_commits.append(commit)
            else:
                print(f"Warning: {instance_id} not found in JSON for {repo_name}")
        
        # Update the repository data
        repo_data["commits"] = new_commits
        repo_data["commit_count"] = len(new_commits)
        
        print(f"{repo_name}: {len(new_commits)} commits reordered")
    
    # Recalculate global problem numbers across all repos
    global_problem_number = 1
    for repo_name in data["repositories"]:
        for commit in data["repositories"][repo_name]["commits"]:
            commit["problem_number"] = global_problem_number
            global_problem_number += 1
    
    # Update metadata
    data["metadata"]["total_commits"] = global_problem_number - 1
    data["metadata"]["note"] = "Reorganized to match true chronological order from Chronological_branches.txt"
    
    # Write the reorganized JSON
    output_file = script_dir / "swebench_pro_grouped_chronological.json"
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nReorganized JSON saved to {output_file}")
    print(f"Total commits: {global_problem_number - 1}")

if __name__ == "__main__":
    main()
