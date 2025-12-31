#!/usr/bin/env python3
"""
Rewrite .gitmodules in all affected task instance branches to point to your org's forks.

This script:
1. Identifies all branches with .gitmodules
2. For each branch, rewrites the submodule URLs to point to your org
3. Commits the change
4. Pushes to your fork

Usage:
    python rewrite_gitmodules_all_branches.py --org YOUR_ORG_NAME [--dry-run] [--push]
"""

import subprocess
import argparse
import re
from pathlib import Path

REPOS_DIR = Path("/Users/jackblundin/SWE-bench_Pro-os/swebench_pro_repos")

# URL rewrite mappings: original URL -> new repo name in blitzy-showcase org
# Your forks:
#   https://github.com/blitzy-showcase/infogami
#   https://github.com/blitzy-showcase/webassets
#   https://github.com/blitzy-showcase/wmd
#   https://github.com/blitzy-showcase/integration
URL_REWRITES = {
    # vuls - integration submodule
    "https://github.com/vulsio/integration": "integration",
    "https://github.com/vulsio/integration.git": "integration",
    
    # teleport - webassets submodule (public)
    "https://github.com/gravitational/webassets.git": "webassets",
    "https://github.com/gravitational/webassets": "webassets",
    # teleport - private submodules (cannot be forked, will still point to original)
    "git@github.com:gravitational/teleport.e.git": None,  # PRIVATE - skip
    "git@github.com:gravitational/ops.git": None,  # PRIVATE - skip
    
    # openlibrary - infogami submodule
    "https://github.com/internetarchive/infogami.git": "infogami",
    "https://github.com/internetarchive/infogami": "infogami",
    "git://github.com/internetarchive/infogami.git": "infogami",
    # openlibrary - wmd submodule
    "https://github.com/internetarchive/wmd.git": "wmd",
    "https://github.com/internetarchive/wmd": "wmd",
    "git://github.com/internetarchive/wmd.git": "wmd",
}

# Repos that have submodules in task instance branches
REPOS_WITH_SUBMODULES = [
    "future-architect__vuls",
    "gravitational__teleport",
    "internetarchive__openlibrary",
]


def run_git(repo_path: Path, args: list[str], check: bool = True) -> tuple[int, str, str]:
    """Run a git command and return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_task_instance_branches(repo_path: Path) -> list[str]:
    """Get all task instance branches."""
    code, stdout, _ = run_git(repo_path, ["branch", "--format=%(refname:short)"])
    if code != 0:
        return []
    return [b for b in stdout.split("\n") if b.startswith("instance_")]


def get_gitmodules_content(repo_path: Path, branch: str) -> str | None:
    """Get .gitmodules content for a branch."""
    code, stdout, _ = run_git(repo_path, ["show", f"{branch}:.gitmodules"])
    if code != 0 or not stdout:
        return None
    return stdout


def rewrite_gitmodules(content: str, target_org: str) -> str:
    """Rewrite all URLs in .gitmodules to point to target org."""
    new_content = content
    
    for original_url, repo_name in URL_REWRITES.items():
        if repo_name is None:
            # Skip private repos that can't be forked
            continue
        new_url = f"https://github.com/{target_org}/{repo_name}.git"
        # Replace the URL (handle with or without .git suffix)
        new_content = new_content.replace(original_url, new_url)
    
    return new_content


def process_branch(repo_path: Path, branch: str, target_org: str, dry_run: bool = True) -> dict:
    """Process a single branch: rewrite .gitmodules and commit."""
    result = {
        "branch": branch,
        "status": "skipped",
        "message": "",
    }
    
    # Get current .gitmodules
    original_content = get_gitmodules_content(repo_path, branch)
    if not original_content:
        result["status"] = "skipped"
        result["message"] = "No .gitmodules found"
        return result
    
    # Rewrite URLs
    new_content = rewrite_gitmodules(original_content, target_org)
    
    if new_content == original_content:
        result["status"] = "unchanged"
        result["message"] = "No URLs needed rewriting"
        return result
    
    if dry_run:
        result["status"] = "would_modify"
        result["message"] = "Would rewrite .gitmodules"
        result["original"] = original_content
        result["new"] = new_content
        return result
    
    # Checkout the branch
    code, _, stderr = run_git(repo_path, ["checkout", branch])
    if code != 0:
        result["status"] = "error"
        result["message"] = f"Failed to checkout: {stderr}"
        return result
    
    # Write new .gitmodules
    gitmodules_path = repo_path / ".gitmodules"
    gitmodules_path.write_text(new_content)
    
    # Stage the change
    code, _, stderr = run_git(repo_path, ["add", ".gitmodules"])
    if code != 0:
        result["status"] = "error"
        result["message"] = f"Failed to stage: {stderr}"
        return result
    
    # Commit
    commit_msg = f"chore: rewrite submodule URLs to point to {target_org} org"
    code, _, stderr = run_git(repo_path, ["commit", "-m", commit_msg])
    if code != 0:
        # Check if nothing to commit (already done)
        if "nothing to commit" in stderr:
            result["status"] = "unchanged"
            result["message"] = "Already up to date"
            return result
        result["status"] = "error"
        result["message"] = f"Failed to commit: {stderr}"
        return result
    
    result["status"] = "modified"
    result["message"] = "Successfully rewrote .gitmodules"
    return result


def push_branch(repo_path: Path, branch: str, remote: str = "origin") -> tuple[bool, str]:
    """Push a branch to remote."""
    code, _, stderr = run_git(repo_path, ["push", remote, branch])
    if code != 0:
        return False, stderr
    return True, "Pushed successfully"


def main():
    parser = argparse.ArgumentParser(description="Rewrite .gitmodules in all task instance branches")
    parser.add_argument("--org", required=True, help="Target GitHub organization name")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--push", action="store_true", help="Push changes after committing")
    parser.add_argument("--repo", help="Process only this repo (for testing)")
    parser.add_argument("--branch", help="Process only this branch (for testing)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()
    
    print("=" * 70)
    print("Rewrite .gitmodules in Task Instance Branches")
    print(f"Target org: {args.org}")
    print(f"Dry run: {args.dry_run}")
    print(f"Push: {args.push}")
    print("=" * 70)
    
    repos_to_process = [args.repo] if args.repo else REPOS_WITH_SUBMODULES
    
    total_modified = 0
    total_errors = 0
    total_skipped = 0
    
    for repo_name in repos_to_process:
        repo_path = REPOS_DIR / repo_name
        
        if not repo_path.exists():
            print(f"\n❌ Repo not found: {repo_path}")
            continue
        
        print(f"\n{'='*60}")
        print(f"Processing: {repo_name}")
        print(f"{'='*60}")
        
        # Save current branch to restore later
        _, original_branch, _ = run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        
        branches = get_task_instance_branches(repo_path)
        if args.branch:
            branches = [b for b in branches if b == args.branch]
        
        print(f"Found {len(branches)} task instance branches")
        
        for i, branch in enumerate(branches, 1):
            result = process_branch(repo_path, branch, args.org, args.dry_run)
            
            status_icon = {
                "modified": "✓",
                "would_modify": "○",
                "unchanged": "·",
                "skipped": "·",
                "error": "✗",
            }.get(result["status"], "?")
            
            if args.verbose or result["status"] in ["error", "modified", "would_modify"]:
                print(f"  [{i}/{len(branches)}] {status_icon} {branch[:60]}...")
                if result["message"]:
                    print(f"      {result['message']}")
            
            if result["status"] == "modified":
                total_modified += 1
                if args.push:
                    success, msg = push_branch(repo_path, branch)
                    if success:
                        print(f"      Pushed to origin")
                    else:
                        print(f"      Push failed: {msg}")
            elif result["status"] == "would_modify":
                total_modified += 1
            elif result["status"] == "error":
                total_errors += 1
            else:
                total_skipped += 1
        
        # Restore original branch
        if not args.dry_run:
            run_git(repo_path, ["checkout", original_branch])
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Modified/Would modify: {total_modified}")
    print(f"Skipped/Unchanged: {total_skipped}")
    print(f"Errors: {total_errors}")
    
    if args.dry_run:
        print("\n⚠️  This was a dry run. No changes were made.")
        print("   Run without --dry-run to apply changes.")
        print("   Add --push to also push changes to remote.")


if __name__ == "__main__":
    main()
