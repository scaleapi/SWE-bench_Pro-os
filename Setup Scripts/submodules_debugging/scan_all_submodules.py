#!/usr/bin/env python3
"""
Comprehensive scan of ALL task instance branches across ALL repos for submodules.

This script identifies:
1. Which repos have submodules in any task instance branch
2. What submodule URLs are referenced
3. Which branches need submodule handling for Blitzy onboarding
"""

import subprocess
import json
from pathlib import Path
from collections import defaultdict

REPOS_DIR = Path("/Users/jackblundin/SWE-bench_Pro-os/swebench_pro_repos")

REPOS = [
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
    "tutao__tutanota",
]


def run_git(repo_path: Path, args: list[str]) -> tuple[int, str]:
    """Run a git command and return (exit_code, output)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip()


def get_task_instance_branches(repo_path: Path) -> list[str]:
    """Get all task instance branches (those starting with 'instance_')."""
    code, output = run_git(repo_path, ["branch", "--format=%(refname:short)"])
    if code != 0:
        return []
    return [b for b in output.split("\n") if b.startswith("instance_")]


def get_gitmodules_content(repo_path: Path, branch: str) -> str | None:
    """Get .gitmodules content for a branch, or None if it doesn't exist."""
    code, output = run_git(repo_path, ["show", f"{branch}:.gitmodules"])
    if code != 0 or not output:
        return None
    return output


def parse_gitmodules(content: str) -> list[dict]:
    """Parse .gitmodules content into a list of submodule definitions."""
    submodules = []
    current = {}
    
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("[submodule"):
            if current:
                submodules.append(current)
            name = line.split('"')[1] if '"' in line else ""
            current = {"name": name}
        elif "=" in line and current:
            key, value = line.split("=", 1)
            current[key.strip()] = value.strip()
    
    if current:
        submodules.append(current)
    
    return submodules


def get_submodule_sha(repo_path: Path, branch: str, submodule_path: str) -> str | None:
    """Get the commit SHA for a submodule in a specific branch."""
    code, output = run_git(repo_path, ["ls-tree", branch, submodule_path])
    if code != 0 or not output:
        return None
    parts = output.split()
    if len(parts) >= 3 and parts[0] == "160000":
        return parts[2]
    return None


def scan_repo(repo_name: str) -> dict:
    """Scan a repo for submodules in task instance branches."""
    repo_path = REPOS_DIR / repo_name
    
    if not repo_path.exists():
        return {"error": f"Repo not found: {repo_path}"}
    
    branches = get_task_instance_branches(repo_path)
    
    result = {
        "repo": repo_name,
        "total_task_branches": len(branches),
        "branches_with_submodules": 0,
        "submodule_urls": set(),
        "affected_branches": [],
        "submodule_details": defaultdict(list),
    }
    
    for branch in branches:
        gitmodules = get_gitmodules_content(repo_path, branch)
        if gitmodules:
            result["branches_with_submodules"] += 1
            submodules = parse_gitmodules(gitmodules)
            
            branch_info = {
                "branch": branch,
                "submodules": []
            }
            
            for sm in submodules:
                url = sm.get("url", "")
                path = sm.get("path", "")
                sha = get_submodule_sha(repo_path, branch, path)
                
                result["submodule_urls"].add(url)
                result["submodule_details"][url].append({
                    "branch": branch,
                    "path": path,
                    "sha": sha
                })
                
                branch_info["submodules"].append({
                    "path": path,
                    "url": url,
                    "sha": sha
                })
            
            result["affected_branches"].append(branch_info)
    
    # Convert set to list for JSON serialization
    result["submodule_urls"] = list(result["submodule_urls"])
    result["submodule_details"] = dict(result["submodule_details"])
    
    return result


def main():
    print("=" * 70)
    print("SWE-bench Pro - Comprehensive Submodule Scan")
    print("Scanning ALL task instance branches across ALL repos")
    print("=" * 70)
    
    all_results = {}
    repos_with_submodules = []
    all_submodule_urls = set()
    total_affected_branches = 0
    
    for repo_name in REPOS:
        print(f"\nScanning {repo_name}...", end=" ", flush=True)
        result = scan_repo(repo_name)
        all_results[repo_name] = result
        
        if result.get("branches_with_submodules", 0) > 0:
            repos_with_submodules.append(repo_name)
            total_affected_branches += result["branches_with_submodules"]
            all_submodule_urls.update(result["submodule_urls"])
            print(f"✓ {result['branches_with_submodules']}/{result['total_task_branches']} branches have submodules")
        else:
            print(f"✓ No submodules in task instance branches")
    
    # Save detailed results
    output_file = Path("/Users/jackblundin/SWE-bench_Pro-os/Setup Scripts/loc_results/submodule_full_scan.json")
    
    # Convert sets to lists for JSON
    json_results = {}
    for repo, data in all_results.items():
        json_results[repo] = {k: v for k, v in data.items()}
    
    with open(output_file, "w") as f:
        json.dump(json_results, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print(f"\nRepos with submodules in task instance branches: {len(repos_with_submodules)}")
    for repo in repos_with_submodules:
        r = all_results[repo]
        print(f"  - {repo}: {r['branches_with_submodules']}/{r['total_task_branches']} branches")
    
    print(f"\nTotal affected task instance branches: {total_affected_branches}")
    
    print(f"\nUnique submodule URLs to fork ({len(all_submodule_urls)}):")
    for url in sorted(all_submodule_urls):
        print(f"  - {url}")
    
    print(f"\nDetailed results saved to: {output_file}")
    
    # Generate URL rewrite commands
    if all_submodule_urls:
        print("\n" + "=" * 70)
        print("RECOMMENDED: Git URL Rewrite Commands for Blitzy")
        print("=" * 70)
        print("\nAdd these to Blitzy's git config before cloning:")
        print()
        for url in sorted(all_submodule_urls):
            # Extract repo name from URL
            if url.startswith("git@"):
                # git@github.com:org/repo.git
                repo_part = url.split(":")[-1].replace(".git", "")
            elif url.startswith("git://"):
                # git://github.com/org/repo.git
                repo_part = url.replace("git://github.com/", "").replace(".git", "")
            else:
                # https://github.com/org/repo or https://github.com/org/repo.git
                repo_part = url.replace("https://github.com/", "").replace(".git", "")
            
            parts = repo_part.split("/")
            if len(parts) >= 2:
                org, name = parts[0], parts[-1]
            else:
                org, name = "unknown", repo_part
            new_name = f"{org}__{name}"
            
            print(f'git config --global url."https://github.com/YOUR_ORG/{new_name}".insteadOf "{url}"')
            if not url.endswith(".git"):
                print(f'git config --global url."https://github.com/YOUR_ORG/{new_name}".insteadOf "{url}.git"')


if __name__ == "__main__":
    main()
