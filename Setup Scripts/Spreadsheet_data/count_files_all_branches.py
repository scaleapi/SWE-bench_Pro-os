#!/usr/bin/env python3
"""
Script to count number of files across all task instance branches
in the SWE-bench Pro repositories, and add the data to the existing LOC CSV.

For each branch:
1. Checkout the branch
2. Count files using: git ls-files | wc -l
3. Add the file count to the existing CSV
"""

import os
import subprocess
import csv
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import threading

# Configuration
BASE_PATH = Path("/Users/jackblundin/SWE-bench_Pro-os/swebench_pro_repos")
CSV_PATH = Path("/Users/jackblundin/SWE-bench_Pro-os/Setup Scripts/loc_results/loc_results_20251215_202437.csv")

# Thread lock for printing
print_lock = threading.Lock()


def safe_print(*args, **kwargs):
    """Thread-safe print function."""
    with print_lock:
        print(*args, **kwargs)


def run_git_command(repo_path: Path, command: str, timeout: int = 300) -> Tuple[bool, str, str]:
    """Run a git command in the specified repository directory."""
    try:
        result = subprocess.run(
            command,
            cwd=repo_path,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return False, "", str(e)


def count_files_for_branch(repo_path: Path, branch_name: str) -> Tuple[str, Optional[int], str]:
    """
    Checkout a branch and count number of files.
    Returns: (branch_name, file_count, error_message)
    """
    # Checkout the branch
    success, stdout, stderr = run_git_command(repo_path, f"git checkout {branch_name}")
    if not success:
        return branch_name, None, f"Checkout failed: {stderr}"
    
    # Count files using git ls-files | wc -l
    success, stdout, stderr = run_git_command(
        repo_path,
        "git ls-files | wc -l",
        timeout=120
    )
    
    if not success:
        return branch_name, None, f"File count failed: {stderr}"
    
    try:
        file_count = int(stdout.strip()) if stdout.strip() else 0
        return branch_name, file_count, ""
    except ValueError:
        return branch_name, None, f"Could not parse file count: '{stdout}'"


def get_current_branch(repo_path: Path) -> str:
    """Get the current branch name."""
    success, stdout, stderr = run_git_command(repo_path, "git branch --show-current")
    if success and stdout:
        return stdout
    return "main"


def main():
    """Main function to count files and update CSV."""
    start_time = time.time()
    
    print("=" * 70)
    print("SWE-bench Pro - File Counter")
    print("=" * 70)
    print(f"Base path: {BASE_PATH}")
    print(f"CSV path: {CSV_PATH}")
    print()
    
    # Read existing CSV
    with open(CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames)
    
    print(f"Loaded {len(rows)} rows from CSV")
    
    # Add new column if not exists
    if 'file_count' not in fieldnames:
        fieldnames.append('file_count')
    
    # Group rows by repository for efficient processing
    repo_rows = {}
    for i, row in enumerate(rows):
        repo = row['repository']
        if repo not in repo_rows:
            repo_rows[repo] = []
        repo_rows[repo].append((i, row))
    
    # Process each repository
    for repo_name in sorted(repo_rows.keys()):
        repo_path = BASE_PATH / repo_name
        
        if not repo_path.exists():
            safe_print(f"Warning: Repository {repo_name} not found at {repo_path}")
            continue
        
        # Store original branch to return to
        original_branch = get_current_branch(repo_path)
        
        repo_items = repo_rows[repo_name]
        safe_print(f"\n{'='*60}")
        safe_print(f"Processing {repo_name} ({len(repo_items)} branches)")
        safe_print(f"{'='*60}")
        
        for j, (row_idx, row) in enumerate(repo_items, 1):
            branch = row['branch']
            
            branch_name, file_count, error = count_files_for_branch(repo_path, branch)
            
            if error:
                safe_print(f"  [{j}/{len(repo_items)}] {branch[:60]}...: ERROR - {error}")
                rows[row_idx]['file_count'] = ''
            else:
                safe_print(f"  [{j}/{len(repo_items)}] {branch[:60]}...: {file_count:,} files")
                rows[row_idx]['file_count'] = file_count
        
        # Return to original branch
        run_git_command(repo_path, f"git checkout {original_branch}")
    
    # Write updated CSV
    with open(CSV_PATH, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    safe_print(f"\nUpdated CSV saved to: {CSV_PATH}")
    
    elapsed = time.time() - start_time
    print(f"\nTotal execution time: {elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()
