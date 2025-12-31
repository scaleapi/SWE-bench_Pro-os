#!/usr/bin/env python3
"""
Script to count lines of code across all 731 task instance branches
in the SWE-bench Pro repositories.

For each branch:
1. Checkout the branch
2. Count LOC using: git ls-files | xargs wc -l
3. Log the result
4. Return to main branch before next iteration
"""

import os
import subprocess
import json
import csv
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configuration
BASE_PATH = Path("/Users/jackblundin/SWE-bench_Pro-os/swebench_pro_repos")
JSON_PATH = Path("/Users/jackblundin/SWE-bench_Pro-os/Setup Scripts/swebench_pro_grouped_chronological.json")
OUTPUT_DIR = Path("/Users/jackblundin/SWE-bench_Pro-os/Setup Scripts/loc_results")

# Repository name mapping (JSON name -> directory name)
REPO_NAME_MAP = {
    "NodeBB/NodeBB": "NodeBB__NodeBB",
    "qutebrowser/qutebrowser": "qutebrowser__qutebrowser",
    "ansible/ansible": "ansible__ansible",
    "element-hq/element-web": "element-hq__element-web",
    "flipt-io/flipt": "flipt-io__flipt",
    "future-architect/vuls": "future-architect__vuls",
    "gravitational/teleport": "gravitational__teleport",
    "internetarchive/openlibrary": "internetarchive__openlibrary",
    "navidrome/navidrome": "navidrome__navidrome",
    "ProtonMail/WebClients": "protonmail__webclients",
    "tutao/tutanota": "tutao__tutanota"
}

# Expected branch counts per repository (from screenshot)
EXPECTED_COUNTS = {
    "ansible__ansible": 96,
    "element-hq__element-web": 56,
    "flipt-io__flipt": 85,
    "future-architect__vuls": 62,
    "gravitational__teleport": 76,
    "internetarchive__openlibrary": 91,
    "navidrome__navidrome": 57,
    "NodeBB__NodeBB": 44,
    "protonmail__webclients": 65,
    "qutebrowser__qutebrowser": 79,
    "tutao__tutanota": 20
}

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


def get_all_branches(repo_path: Path) -> List[str]:
    """Get all task instance branches in a repository (excluding main/master)."""
    success, stdout, stderr = run_git_command(repo_path, "git branch -a")
    if not success:
        safe_print(f"Error getting branches for {repo_path}: {stderr}")
        return []
    
    branches = set()
    for line in stdout.split('\n'):
        line = line.strip()
        if not line or line.startswith('*') or 'HEAD' in line:
            continue
        
        # Remove 'remotes/origin/' prefix if present
        if line.startswith('remotes/origin/'):
            branch = line.replace('remotes/origin/', '')
        else:
            branch = line
        
        # Only include instance branches (they start with 'instance_')
        if branch.startswith('instance_'):
            branches.add(branch)
    
    return sorted(list(branches))


def count_loc_for_branch(repo_path: Path, branch_name: str) -> Tuple[str, Optional[int], str]:
    """
    Checkout a branch and count lines of code.
    Returns: (branch_name, loc_count, error_message)
    """
    # Checkout the branch
    success, stdout, stderr = run_git_command(repo_path, f"git checkout {branch_name}")
    if not success:
        return branch_name, None, f"Checkout failed: {stderr}"
    
    # Count lines of code using git ls-files | xargs wc -l
    # Use a more robust command that handles files with spaces and special characters
    success, stdout, stderr = run_git_command(
        repo_path,
        "git ls-files -z | xargs -0 wc -l 2>/dev/null | tail -1 | awk '{print $1}'",
        timeout=600  # 10 minutes for large repos
    )
    
    if not success:
        return branch_name, None, f"LOC count failed: {stderr}"
    
    try:
        loc = int(stdout.strip()) if stdout.strip() else 0
        return branch_name, loc, ""
    except ValueError:
        return branch_name, None, f"Could not parse LOC: '{stdout}'"


def get_current_branch(repo_path: Path) -> str:
    """Get the current branch name."""
    success, stdout, stderr = run_git_command(repo_path, "git branch --show-current")
    if success and stdout:
        return stdout
    return "main"


def process_repository(repo_dir_name: str, branches: List[str]) -> List[Dict]:
    """Process all branches in a single repository sequentially."""
    repo_path = BASE_PATH / repo_dir_name
    results = []
    
    if not repo_path.exists():
        safe_print(f"Warning: Repository {repo_dir_name} not found at {repo_path}")
        return results
    
    # Store original branch to return to
    original_branch = get_current_branch(repo_path)
    
    safe_print(f"\n{'='*60}")
    safe_print(f"Processing {repo_dir_name} ({len(branches)} branches)")
    safe_print(f"{'='*60}")
    
    for i, branch in enumerate(branches, 1):
        start_time = time.time()
        
        branch_name, loc, error = count_loc_for_branch(repo_path, branch)
        
        elapsed = time.time() - start_time
        
        result = {
            "repository": repo_dir_name,
            "branch": branch_name,
            "loc": loc,
            "error": error,
            "elapsed_seconds": round(elapsed, 2)
        }
        results.append(result)
        
        if error:
            safe_print(f"  [{i}/{len(branches)}] {branch_name}: ERROR - {error}")
        else:
            safe_print(f"  [{i}/{len(branches)}] {branch_name}: {loc:,} lines ({elapsed:.1f}s)")
    
    # Return to original branch
    run_git_command(repo_path, f"git checkout {original_branch}")
    
    return results


def load_branches_from_json() -> Dict[str, List[str]]:
    """Load branch names from the JSON file, grouped by repository."""
    with open(JSON_PATH, 'r') as f:
        data = json.load(f)
    
    repo_branches = {}
    
    for json_repo_name, repo_data in data.get("repositories", {}).items():
        dir_name = REPO_NAME_MAP.get(json_repo_name)
        if not dir_name:
            safe_print(f"Warning: No mapping for repository {json_repo_name}")
            continue
        
        branches = []
        for commit in repo_data.get("commits", []):
            instance_id = commit.get("instance_id")
            if instance_id:
                branches.append(instance_id)
        
        repo_branches[dir_name] = branches
    
    return repo_branches


def load_branches_from_git() -> Dict[str, List[str]]:
    """Load branch names directly from git repositories."""
    repo_branches = {}
    
    for dir_name in EXPECTED_COUNTS.keys():
        repo_path = BASE_PATH / dir_name
        if repo_path.exists():
            branches = get_all_branches(repo_path)
            repo_branches[dir_name] = branches
            safe_print(f"Found {len(branches)} branches in {dir_name}")
        else:
            safe_print(f"Warning: Repository {dir_name} not found")
    
    return repo_branches


def save_results(all_results: List[Dict], output_dir: Path):
    """Save results to CSV and JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save detailed CSV
    csv_path = output_dir / f"loc_results_{timestamp}.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["repository", "branch", "loc", "error", "elapsed_seconds"])
        writer.writeheader()
        writer.writerows(all_results)
    safe_print(f"\nDetailed results saved to: {csv_path}")
    
    # Save JSON
    json_path = output_dir / f"loc_results_{timestamp}.json"
    with open(json_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    safe_print(f"JSON results saved to: {json_path}")
    
    # Generate summary
    summary = generate_summary(all_results)
    summary_path = output_dir / f"loc_summary_{timestamp}.txt"
    with open(summary_path, 'w') as f:
        f.write(summary)
    safe_print(f"Summary saved to: {summary_path}")
    
    # Also print summary
    print(summary)
    
    return csv_path, json_path, summary_path


def generate_summary(all_results: List[Dict]) -> str:
    """Generate a summary report of the LOC counts."""
    lines = []
    lines.append("=" * 70)
    lines.append("SWE-bench Pro - Lines of Code Summary")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    lines.append("")
    
    # Group by repository
    repo_stats = {}
    for result in all_results:
        repo = result["repository"]
        if repo not in repo_stats:
            repo_stats[repo] = {"branches": 0, "total_loc": 0, "errors": 0, "loc_values": []}
        
        repo_stats[repo]["branches"] += 1
        if result["loc"] is not None:
            repo_stats[repo]["total_loc"] += result["loc"]
            repo_stats[repo]["loc_values"].append(result["loc"])
        if result["error"]:
            repo_stats[repo]["errors"] += 1
    
    # Per-repository summary
    lines.append("Per-Repository Summary:")
    lines.append("-" * 70)
    lines.append(f"{'Repository':<35} {'Branches':>10} {'Avg LOC':>12} {'Total LOC':>15}")
    lines.append("-" * 70)
    
    grand_total_branches = 0
    grand_total_loc = 0
    all_loc_values = []
    
    for repo in sorted(repo_stats.keys()):
        stats = repo_stats[repo]
        branches = stats["branches"]
        loc_values = stats["loc_values"]
        avg_loc = sum(loc_values) / len(loc_values) if loc_values else 0
        total_loc = stats["total_loc"]
        
        lines.append(f"{repo:<35} {branches:>10} {avg_loc:>12,.0f} {total_loc:>15,}")
        
        grand_total_branches += branches
        grand_total_loc += total_loc
        all_loc_values.extend(loc_values)
    
    lines.append("-" * 70)
    grand_avg = sum(all_loc_values) / len(all_loc_values) if all_loc_values else 0
    lines.append(f"{'TOTAL':<35} {grand_total_branches:>10} {grand_avg:>12,.0f} {grand_total_loc:>15,}")
    lines.append("")
    
    # Overall statistics
    if all_loc_values:
        lines.append("Overall Statistics:")
        lines.append("-" * 70)
        lines.append(f"Total branches processed: {grand_total_branches}")
        lines.append(f"Total lines of code: {grand_total_loc:,}")
        lines.append(f"Average LOC per branch: {grand_avg:,.0f}")
        lines.append(f"Minimum LOC: {min(all_loc_values):,}")
        lines.append(f"Maximum LOC: {max(all_loc_values):,}")
        
        # Calculate median
        sorted_values = sorted(all_loc_values)
        n = len(sorted_values)
        if n % 2 == 0:
            median = (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
        else:
            median = sorted_values[n//2]
        lines.append(f"Median LOC: {median:,.0f}")
    
    # Error summary
    total_errors = sum(stats["errors"] for stats in repo_stats.values())
    if total_errors > 0:
        lines.append("")
        lines.append(f"Errors encountered: {total_errors}")
    
    lines.append("")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def main():
    """Main function to orchestrate the LOC counting."""
    start_time = time.time()
    
    print("=" * 70)
    print("SWE-bench Pro - Lines of Code Counter")
    print("=" * 70)
    print(f"Base path: {BASE_PATH}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()
    
    # Load branches - try from git first, fall back to JSON
    print("Loading branches from git repositories...")
    repo_branches = load_branches_from_git()
    
    # Validate counts
    total_branches = sum(len(branches) for branches in repo_branches.values())
    print(f"\nTotal branches found: {total_branches}")
    print(f"Expected: 731")
    
    if total_branches < 731:
        print("\nWarning: Found fewer branches than expected!")
        print("Attempting to load from JSON file as fallback...")
        json_branches = load_branches_from_json()
        json_total = sum(len(branches) for branches in json_branches.values())
        print(f"JSON contains {json_total} branch references")
        
        # Use whichever has more branches
        if json_total > total_branches:
            print("Using JSON branch list")
            repo_branches = json_branches
            total_branches = json_total
    
    print("\nBranch counts per repository:")
    for repo, branches in sorted(repo_branches.items()):
        expected = EXPECTED_COUNTS.get(repo, "?")
        status = "✓" if len(branches) == expected else "⚠"
        print(f"  {status} {repo}: {len(branches)} (expected: {expected})")
    
    # Process each repository
    all_results = []
    
    for repo_name in sorted(repo_branches.keys()):
        branches = repo_branches[repo_name]
        if not branches:
            continue
        
        results = process_repository(repo_name, branches)
        all_results.extend(results)
    
    # Save results
    if all_results:
        save_results(all_results, OUTPUT_DIR)
    
    elapsed = time.time() - start_time
    print(f"\nTotal execution time: {elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()
