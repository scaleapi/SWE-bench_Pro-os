#!/usr/bin/env python3
"""
Quick test script to count branches across all repositories
"""

import os
import subprocess
from pathlib import Path

def run_git_command(repo_path, command):
    """Run a git command in the specified repository directory."""
    try:
        result = subprocess.run(
            command,
            cwd=repo_path,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def get_all_branches(repo_path):
    """Get all branches in a repository."""
    success, stdout, stderr = run_git_command(repo_path, "git branch -a")
    if not success:
        print(f"Error getting branches for {repo_path}: {stderr}")
        return []
    
    branches = []
    for line in stdout.split('\n'):
        line = line.strip()
        if line and not line.startswith('*') and 'HEAD' not in line:
            # Remove 'remotes/origin/' prefix if present
            if line.startswith('remotes/origin/'):
                branch = line.replace('remotes/origin/', '')
                if branch not in ['main', 'master']:
                    branches.append(branch)
            elif line not in ['main', 'master']:
                branches.append(line)
    
    return list(set(branches))  # Remove duplicates

def main():
    base_path = Path("/Users/jackblundin/SWE-bench_Pro-os/swebench_pro_repos")
    
    repositories = [
        "NodeBB__NodeBB",
        "ansible__ansible", 
        "element-hq__element-web",
        "flipt-io__flipt",
        "future-architect__vuls",
        "gravitational__teleport",
        "internetarchive__openlibrary",
        "navidrome__navidrome",
        "protonmail__webclients",
        "qutebrowser__qutebrowser",
        "tutao__tutanota"
    ]
    
    total_branches = 0
    
    print("Counting branches across all repositories...")
    for repo_name in repositories:
        repo_path = base_path / repo_name
        if not repo_path.exists():
            print(f"Warning: Repository {repo_name} not found")
            continue
        
        print(f"Checking {repo_name}...", end=" ")
        branches = get_all_branches(repo_path)
        branch_count = len(branches)
        total_branches += branch_count
        print(f"{branch_count} branches")
        
        # Show first few branch names as sample
        if branches:
            print(f"  Sample branches: {', '.join(branches[:3])}")
    
    print(f"\nTotal branches found: {total_branches}")
    print(f"Expected: 731")
    
    if total_branches >= 731:
        print("✓ Found expected number of branches!")
    else:
        print(f"⚠ Found fewer branches than expected ({total_branches} vs 731)")

if __name__ == "__main__":
    main()
