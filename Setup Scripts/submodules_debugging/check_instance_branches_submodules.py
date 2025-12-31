#!/usr/bin/env python3
"""
Script to locate all 729 task instance branches across SWE-bench Pro repos
and check which branches contain submodules.
"""

import os
import subprocess
from pathlib import Path
from collections import defaultdict


REPOS_DIR = Path(__file__).parent.parent / "swebench_pro_repos"
EXPECTED_BRANCH_COUNT = 729


def run_git_command(repo_path: Path, args: list[str]) -> str:
    """Run a git command in the specified repo and return stdout."""
    result = subprocess.run(
        ["git"] + args,
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    return result.stdout.strip()


def get_instance_branches(repo_path: Path) -> list[str]:
    """Get all branches matching the instance_* pattern in a repo."""
    output = run_git_command(repo_path, ["branch", "--list", "instance_*"])
    branches = []
    for line in output.splitlines():
        branch = line.strip().lstrip("* ")
        if branch:
            branches.append(branch)
    return branches


def check_branch_has_submodules(repo_path: Path, branch: str) -> bool:
    """Check if a branch contains a .gitmodules file."""
    result = subprocess.run(
        ["git", "show", f"{branch}:.gitmodules"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def get_submodule_info(repo_path: Path, branch: str) -> list[dict]:
    """Get submodule information from a branch's .gitmodules file."""
    result = subprocess.run(
        ["git", "show", f"{branch}:.gitmodules"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return []
    
    submodules = []
    current_submodule = {}
    
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("[submodule"):
            if current_submodule:
                submodules.append(current_submodule)
            current_submodule = {"name": line.split('"')[1]}
        elif "=" in line:
            key, value = line.split("=", 1)
            current_submodule[key.strip()] = value.strip()
    
    if current_submodule:
        submodules.append(current_submodule)
    
    return submodules


def main():
    print("=" * 70)
    print("SWE-bench Pro Instance Branches & Submodules Analysis")
    print("=" * 70)
    
    # Find all repos
    repos = [d for d in REPOS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
    repos.sort()
    
    print(f"\nFound {len(repos)} repositories in {REPOS_DIR}\n")
    
    # Collect all branches
    all_branches = {}  # repo_name -> list of branches
    total_branches = 0
    
    for repo in repos:
        branches = get_instance_branches(repo)
        all_branches[repo.name] = branches
        total_branches += len(branches)
        print(f"  {repo.name}: {len(branches)} instance branches")
    
    print(f"\n{'=' * 70}")
    print(f"TOTAL INSTANCE BRANCHES: {total_branches}")
    print(f"EXPECTED: {EXPECTED_BRANCH_COUNT}")
    
    if total_branches == EXPECTED_BRANCH_COUNT:
        print("✓ SUCCESS: Found all expected branches!")
    else:
        diff = total_branches - EXPECTED_BRANCH_COUNT
        print(f"⚠ MISMATCH: Found {'+' if diff > 0 else ''}{diff} branches than expected")
    
    print(f"{'=' * 70}\n")
    
    # Check for submodules in each branch
    print("Checking branches for submodules...\n")
    
    branches_with_submodules = defaultdict(list)  # repo_name -> list of (branch, submodules)
    total_with_submodules = 0
    
    for repo in repos:
        branches = all_branches[repo.name]
        repo_submodule_count = 0
        
        for branch in branches:
            if check_branch_has_submodules(repo, branch):
                submodules = get_submodule_info(repo, branch)
                branches_with_submodules[repo.name].append((branch, submodules))
                repo_submodule_count += 1
                total_with_submodules += 1
        
        if repo_submodule_count > 0:
            print(f"  {repo.name}: {repo_submodule_count}/{len(branches)} branches have submodules")
    
    print(f"\n{'=' * 70}")
    print(f"BRANCHES WITH SUBMODULES: {total_with_submodules} / {total_branches}")
    print(f"{'=' * 70}\n")
    
    # Detailed submodule report
    if branches_with_submodules:
        print("DETAILED SUBMODULE REPORT:")
        print("-" * 70)
        
        for repo_name, branch_list in sorted(branches_with_submodules.items()):
            print(f"\n{repo_name} ({len(branch_list)} branches with submodules):")
            
            # Group by unique submodule configurations
            submodule_configs = defaultdict(list)
            for branch, submodules in branch_list:
                # Create a hashable key from submodule URLs
                key = tuple(sorted((s.get("name", ""), s.get("url", "")) for s in submodules))
                submodule_configs[key].append(branch)
            
            for config, branches in submodule_configs.items():
                print(f"\n  Submodule configuration ({len(branches)} branches):")
                for name, url in config:
                    print(f"    - {name}: {url}")
                print(f"  Example branches: {branches[:3]}{'...' if len(branches) > 3 else ''}")
    else:
        print("No branches contain submodules.")
    
    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print("=" * 70)
    print(f"Total repositories: {len(repos)}")
    print(f"Total instance branches: {total_branches}")
    print(f"Branches with submodules: {total_with_submodules}")
    print(f"Branches without submodules: {total_branches - total_with_submodules}")
    
    repos_with_submodules = [r for r in repos if branches_with_submodules.get(r.name)]
    if repos_with_submodules:
        print(f"\nRepositories containing branches with submodules:")
        for repo in repos_with_submodules:
            count = len(branches_with_submodules[repo.name])
            print(f"  - {repo.name}: {count} branches")


if __name__ == "__main__":
    main()
