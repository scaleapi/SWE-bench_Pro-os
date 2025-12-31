#!/usr/bin/env python3
"""
Verify submodule states across all task instance branches for SWE-bench Pro repos.

This script:
1. Identifies which repos have submodules
2. For each branch, extracts the expected submodule commit SHA
3. Reports any issues or inconsistencies
"""

import subprocess
import os
import json
from pathlib import Path

REPOS_DIR = Path("/Users/jackblundin/SWE-bench_Pro-os/swebench_pro_repos")

# Repos known to have submodules
REPOS_WITH_SUBMODULES = {
    "future-architect__vuls": ["integration"],
    "gravitational__teleport": ["e", "webassets"],
    "internetarchive__openlibrary": ["vendor/infogami", "vendor/js/wmd"],
}


def run_git(repo_path: Path, args: list[str]) -> tuple[int, str]:
    """Run a git command and return (exit_code, output)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip() + result.stderr.strip()


def get_local_branches(repo_path: Path) -> list[str]:
    """Get all local branch names."""
    code, output = run_git(repo_path, ["branch", "--format=%(refname:short)"])
    if code != 0:
        return []
    return [b.strip() for b in output.split("\n") if b.strip()]


def get_submodule_sha_for_branch(repo_path: Path, branch: str, submodule_path: str) -> str | None:
    """Get the submodule commit SHA recorded in a specific branch."""
    # Use git ls-tree to get the gitlink entry for the submodule
    code, output = run_git(repo_path, ["ls-tree", branch, submodule_path])
    if code != 0 or not output:
        return None
    
    # Output format: "160000 commit <sha>\t<path>"
    parts = output.split()
    if len(parts) >= 3 and parts[0] == "160000":
        return parts[2]
    return None


def get_gitmodules_content(repo_path: Path, branch: str) -> str | None:
    """Get the .gitmodules file content for a specific branch."""
    code, output = run_git(repo_path, ["show", f"{branch}:.gitmodules"])
    if code != 0:
        return None
    return output


def analyze_repo(repo_name: str, submodule_paths: list[str]) -> dict:
    """Analyze submodule states across all branches for a repo."""
    repo_path = REPOS_DIR / repo_name
    
    if not repo_path.exists():
        return {"error": f"Repo not found: {repo_path}"}
    
    branches = get_local_branches(repo_path)
    print(f"\n{'='*60}")
    print(f"Analyzing: {repo_name}")
    print(f"Branches: {len(branches)}")
    print(f"Submodules: {submodule_paths}")
    print(f"{'='*60}")
    
    results = {
        "repo": repo_name,
        "branch_count": len(branches),
        "submodules": submodule_paths,
        "branches": {},
        "issues": [],
    }
    
    for branch in branches:
        branch_data = {}
        for submodule_path in submodule_paths:
            sha = get_submodule_sha_for_branch(repo_path, branch, submodule_path)
            branch_data[submodule_path] = sha
            
            if sha is None:
                results["issues"].append({
                    "branch": branch,
                    "submodule": submodule_path,
                    "issue": "No submodule entry found (may not exist in this branch)"
                })
        
        results["branches"][branch] = branch_data
    
    return results


def print_summary(results: dict):
    """Print a summary of the analysis."""
    print(f"\n--- Summary for {results['repo']} ---")
    print(f"Total branches: {results['branch_count']}")
    
    # Count unique SHAs per submodule
    for submodule in results["submodules"]:
        shas = set()
        missing = 0
        for branch, data in results["branches"].items():
            sha = data.get(submodule)
            if sha:
                shas.add(sha)
            else:
                missing += 1
        
        print(f"\nSubmodule: {submodule}")
        print(f"  Unique SHAs across branches: {len(shas)}")
        print(f"  Branches missing this submodule: {missing}")
        
        if len(shas) <= 10:
            print(f"  SHA values: {list(shas)}")
    
    if results["issues"]:
        print(f"\nIssues found: {len(results['issues'])}")
        # Group issues by type
        missing_submodules = [i for i in results["issues"] if "No submodule entry" in i["issue"]]
        if missing_submodules:
            print(f"  - Branches without submodule entry: {len(missing_submodules)}")


def main():
    print("=" * 60)
    print("SWE-bench Pro Submodule Verification")
    print("=" * 60)
    
    all_results = {}
    
    for repo_name, submodule_paths in REPOS_WITH_SUBMODULES.items():
        results = analyze_repo(repo_name, submodule_paths)
        all_results[repo_name] = results
        print_summary(results)
    
    # Save detailed results to JSON
    output_file = Path("/Users/jackblundin/SWE-bench_Pro-os/Setup Scripts/loc_results/submodule_analysis.json")
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n\nDetailed results saved to: {output_file}")
    
    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    
    total_issues = sum(len(r.get("issues", [])) for r in all_results.values())
    print(f"Total repos with submodules: {len(REPOS_WITH_SUBMODULES)}")
    print(f"Total issues found: {total_issues}")
    
    if total_issues == 0:
        print("\n✓ All submodule references appear to be correctly recorded in each branch!")
        print("  The gitlink entries are stored in each branch's commit metadata.")
    else:
        print("\n⚠ Some branches may have missing or inconsistent submodule references.")
        print("  Review the detailed JSON output for specifics.")


if __name__ == "__main__":
    main()
