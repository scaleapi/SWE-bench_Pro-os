#!/usr/bin/env python3
"""
Setup script for forking and configuring submodule repositories for SWE-bench Pro.

This script:
1. Forks the required submodule repos to your organization
2. Clones them locally (to ensure all commits are available)
3. Pushes to your organization
4. Updates the submodule URL configs in the parent repos

Usage:
    python setup_submodule_forks.py --org YOUR_ORG_NAME [--dry-run]
"""

import subprocess
import argparse
import os
from pathlib import Path

# Configuration
REPOS_DIR = Path("/Users/jackblundin/SWE-bench_Pro-os/swebench_pro_repos")
SUBMODULE_REPOS_DIR = Path("/Users/jackblundin/SWE-bench_Pro-os/swebench_pro_submodules")

# Submodule definitions
SUBMODULES = {
    "future-architect__vuls": {
        "integration": {
            "original_url": "https://github.com/vulsio/integration",
            "repo_name": "vulsio__integration",
        }
    },
    "gravitational__teleport": {
        "e": {
            "original_url": "git@github.com:gravitational/teleport.e.git",
            "repo_name": "gravitational__teleport.e",
            "note": "This may be a private repo - check access"
        },
        "webassets": {
            "original_url": "https://github.com/gravitational/webassets.git",
            "repo_name": "gravitational__webassets",
        }
    },
    "internetarchive__openlibrary": {
        "vendor/infogami": {
            "original_url": "https://github.com/internetarchive/infogami.git",
            "repo_name": "internetarchive__infogami",
        },
        "vendor/js/wmd": {
            "original_url": "https://github.com/internetarchive/wmd.git",
            "repo_name": "internetarchive__wmd",
        }
    }
}


def run_command(cmd: list[str], cwd: Path = None, check: bool = True) -> tuple[int, str]:
    """Run a command and return (exit_code, output)."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"Output: {output}")
    return result.returncode, output.strip()


def clone_submodule_repo(original_url: str, repo_name: str, dry_run: bool = False) -> bool:
    """Clone a submodule repo locally."""
    target_dir = SUBMODULE_REPOS_DIR / repo_name
    
    if target_dir.exists():
        print(f"  Already cloned: {repo_name}")
        return True
    
    # Convert SSH URL to HTTPS if needed
    clone_url = original_url
    if clone_url.startswith("git@github.com:"):
        clone_url = clone_url.replace("git@github.com:", "https://github.com/")
    if clone_url.endswith(".git"):
        clone_url = clone_url[:-4]
    if not clone_url.endswith(".git"):
        clone_url += ".git"
    
    print(f"  Cloning {clone_url} -> {target_dir}")
    
    if dry_run:
        print(f"  [DRY RUN] Would clone {clone_url}")
        return True
    
    SUBMODULE_REPOS_DIR.mkdir(parents=True, exist_ok=True)
    code, output = run_command(
        ["git", "clone", "--mirror", clone_url, str(target_dir)],
        check=False
    )
    
    if code != 0:
        print(f"  ❌ Failed to clone: {output}")
        return False
    
    print(f"  ✓ Cloned successfully")
    return True


def push_to_org(repo_name: str, org: str, dry_run: bool = False) -> bool:
    """Push a mirrored repo to the organization."""
    repo_dir = SUBMODULE_REPOS_DIR / repo_name
    
    if not repo_dir.exists():
        print(f"  ❌ Repo not found: {repo_dir}")
        return False
    
    target_url = f"https://github.com/{org}/{repo_name}.git"
    
    print(f"  Pushing to {target_url}")
    
    if dry_run:
        print(f"  [DRY RUN] Would push to {target_url}")
        return True
    
    # Add remote if not exists
    run_command(["git", "remote", "add", "enterprise", target_url], cwd=repo_dir, check=False)
    
    # Push all refs
    code, output = run_command(
        ["git", "push", "--mirror", "enterprise"],
        cwd=repo_dir,
        check=False
    )
    
    if code != 0:
        print(f"  ❌ Failed to push: {output}")
        return False
    
    print(f"  ✓ Pushed successfully")
    return True


def update_submodule_config(parent_repo: str, submodule_path: str, new_url: str, dry_run: bool = False) -> bool:
    """Update the submodule URL in the parent repo's config."""
    repo_dir = REPOS_DIR / parent_repo
    
    if not repo_dir.exists():
        print(f"  ❌ Parent repo not found: {repo_dir}")
        return False
    
    print(f"  Updating config for {submodule_path} -> {new_url}")
    
    if dry_run:
        print(f"  [DRY RUN] Would update submodule config")
        return True
    
    # Update the config
    config_key = f"submodule.{submodule_path}.url"
    code, _ = run_command(
        ["git", "config", config_key, new_url],
        cwd=repo_dir,
        check=False
    )
    
    if code != 0:
        return False
    
    # Sync the submodule
    code, _ = run_command(
        ["git", "submodule", "sync", submodule_path],
        cwd=repo_dir,
        check=False
    )
    
    print(f"  ✓ Config updated")
    return True


def main():
    parser = argparse.ArgumentParser(description="Setup submodule forks for SWE-bench Pro")
    parser.add_argument("--org", required=True, help="GitHub organization name")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")
    parser.add_argument("--skip-clone", action="store_true", help="Skip cloning (if already done)")
    parser.add_argument("--skip-push", action="store_true", help="Skip pushing (if already done)")
    parser.add_argument("--only-config", action="store_true", help="Only update local git configs")
    args = parser.parse_args()
    
    print("=" * 60)
    print("SWE-bench Pro Submodule Setup")
    print(f"Organization: {args.org}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 60)
    
    # Step 1: Clone submodule repos
    if not args.skip_clone and not args.only_config:
        print("\n--- Step 1: Cloning submodule repositories ---")
        for parent_repo, submodules in SUBMODULES.items():
            for submodule_path, info in submodules.items():
                print(f"\n{parent_repo} / {submodule_path}:")
                if "note" in info:
                    print(f"  ⚠️  {info['note']}")
                clone_submodule_repo(info["original_url"], info["repo_name"], args.dry_run)
    
    # Step 2: Push to organization
    if not args.skip_push and not args.only_config:
        print("\n--- Step 2: Pushing to organization ---")
        for parent_repo, submodules in SUBMODULES.items():
            for submodule_path, info in submodules.items():
                print(f"\n{parent_repo} / {submodule_path}:")
                push_to_org(info["repo_name"], args.org, args.dry_run)
    
    # Step 3: Update local configs
    print("\n--- Step 3: Updating local submodule configs ---")
    for parent_repo, submodules in SUBMODULES.items():
        for submodule_path, info in submodules.items():
            new_url = f"https://github.com/{args.org}/{info['repo_name']}.git"
            print(f"\n{parent_repo} / {submodule_path}:")
            update_submodule_config(parent_repo, submodule_path, new_url, args.dry_run)
    
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("""
1. Create empty repos in your org for each submodule:
   - {org}/vulsio__integration
   - {org}/gravitational__teleport.e
   - {org}/gravitational__webassets
   - {org}/internetarchive__infogami
   - {org}/internetarchive__wmd

2. Run this script without --dry-run to clone and push

3. To initialize submodules when working with a branch:
   git checkout <branch> --recurse-submodules
   git submodule update --init --recursive
""".format(org=args.org))


if __name__ == "__main__":
    main()
