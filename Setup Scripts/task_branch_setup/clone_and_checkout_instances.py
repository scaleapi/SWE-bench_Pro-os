#!/usr/bin/env python3
"""
SWE-bench Pro Instance Setup Script - Part 1: Clone and Checkout

This script clones your forked repositories locally and creates branches for each
SWE-bench Pro task instance based on the base commits specified in the JSON file.

Usage:
    python clone_and_checkout_instances.py

Requirements:
    - GitPython (pip install GitPython)
    - Your GitHub forks must be accessible
"""

import os
import sys
import json
import time
from git import Repo, GitCommandError
import stat
import shutil

# Configuration
SWEBENCH_PRO_JSON = "swebench_pro_grouped_chronological.json"
BASE_WORK_DIR = "../swebench_pro_repos"  # Look one level up from Setup Scripts/

# Clone URLs mapping - extracted from your clone_urls file
CLONE_URLS = {
    "NodeBB/NodeBB": "https://github.com/jhmblundin/NodeBB.git",
    "qutebrowser/qutebrowser": "https://github.com/jhmblundin/qutebrowser.git", 
    "ansible/ansible": "https://github.com/jhmblundin/ansible.git",
    "internetarchive/openlibrary": "https://github.com/jhmblundin/openlibrary.git",
    "gravitational/teleport": "https://github.com/jhmblundin/teleport.git",
    "navidrome/navidrome": "https://github.com/jhmblundin/navidrome.git",
    "element-hq/element-web": "https://github.com/jhmblundin/element-web.git",
    "future-architect/vuls": "https://github.com/jhmblundin/vuls.git",
    "protonmail/webclients": "https://github.com/jhmblundin/webclients.git",
    "flipt-io/flipt": "https://github.com/jhmblundin/flipt.git",
    "tutao/tutanota": "https://github.com/jhmblundin/tutanota.git"
}

def print_header(message):
    """Prints a styled header to the console."""
    print(f"\n{'='*15} {message} {'='*15}")

def remove_readonly(func, path, _):
    """Error handler for shutil.rmtree to handle read-only files."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def load_swebench_data():
    """Load the SWE-bench Pro data from JSON file."""
    try:
        with open(SWEBENCH_PRO_JSON, 'r') as f:
            data = json.load(f)
        return data['repositories']
    except FileNotFoundError:
        print(f"❌ Error: {SWEBENCH_PRO_JSON} not found!")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        sys.exit(1)

def check_existing_repository(local_path):
    """Check if a repository already exists and is valid."""
    if not os.path.exists(local_path):
        return False
    
    git_dir = os.path.join(local_path, '.git')
    if not os.path.exists(git_dir):
        return False
    
    try:
        # Try to open the repository to verify it's valid
        repo = Repo(local_path)
        return True
    except:
        return False

def clone_repository(repo_name, clone_url, local_path):
    """Clone a repository to the local path, or skip if already exists."""
    
    # Check if repository already exists and is valid
    if check_existing_repository(local_path):
        print(f"📁 Repository {repo_name} already exists - skipping clone")
        try:
            repo = Repo(local_path)
            print(f"  ✅ Using existing repository")
            return repo
        except Exception as e:
            print(f"  ⚠️  Existing repository is corrupted, will re-clone: {e}")
            # Fall through to re-clone
    
    print(f"📥 Cloning {repo_name}...")
    
    # Remove existing directory if it exists but is invalid
    if os.path.exists(local_path):
        print(f"  - Removing existing directory: {local_path}")
        shutil.rmtree(local_path, onexc=remove_readonly)
    
    try:
        repo = Repo.clone_from(clone_url, local_path)
        print(f"  ✅ Successfully cloned {repo_name}")
        return repo
    except GitCommandError as e:
        print(f"  ❌ Failed to clone {repo_name}: {e}")
        return None

def checkout_instance_branches(repo, repo_name, commits_data):
    """Create and checkout branches for each task instance."""
    print(f"🌱 Creating instance branches for {repo_name}...")
    
    successful_branches = 0
    failed_branches = 0
    skipped_branches = 0
    failed_branch_details = []
    
    for commit_info in commits_data:
        instance_id = commit_info['instance_id']
        base_commit = commit_info['base_commit']
        problem_number = commit_info['problem_number']
        
        try:
            # Check if branch already exists
            if instance_id in [head.name for head in repo.heads]:
                print(f"  📁 Branch '{instance_id}' already exists - skipping (Problem #{problem_number})")
                skipped_branches += 1
                successful_branches += 1  # Count as successful since it exists
                continue
            
            # Check if the commit exists in the repository
            try:
                repo.commit(base_commit)
            except Exception as commit_error:
                error_msg = f"Commit {base_commit} not found"
                print(f"  ⚠️  {error_msg} for instance {instance_id}")
                failed_branches += 1
                failed_branch_details.append({
                    'repo': repo_name,
                    'instance_id': instance_id,
                    'base_commit': base_commit,
                    'problem_number': problem_number,
                    'error': error_msg,
                    'error_type': 'missing_commit'
                })
                continue
            
            # Create branch from the base commit
            branch = repo.create_head(instance_id, base_commit)
            print(f"  ✅ Created branch '{instance_id}' at commit {base_commit[:8]} (Problem #{problem_number})")
            successful_branches += 1
            
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ Failed to create branch '{instance_id}': {error_msg}")
            failed_branches += 1
            failed_branch_details.append({
                'repo': repo_name,
                'instance_id': instance_id,
                'base_commit': base_commit,
                'problem_number': problem_number,
                'error': error_msg,
                'error_type': 'branch_creation_error'
            })
    
    print(f"  📊 Summary: {successful_branches} successful ({skipped_branches} already existed), {failed_branches} failed")
    return successful_branches, failed_branches, failed_branch_details

def main():
    """Main execution function."""
    print_header("SWE-bench Pro Instance Setup - Part 1")
    print("This script will clone your forked repositories and create task instance branches.")
    print("⚡ Smart mode: Skips existing repositories and branches to save time on re-runs.")
    
    # Load SWE-bench Pro data
    print_header("Loading SWE-bench Pro Data")
    repo_data = load_swebench_data()
    
    total_repos = len(repo_data)
    total_instances = sum(len(data['commits']) for data in repo_data.values())
    
    print(f"📋 Found {total_repos} repositories with {total_instances} total task instances")
    
    # Create base working directory
    abs_work_dir = os.path.abspath(BASE_WORK_DIR)
    print(f"📁 Working directory: {abs_work_dir}")
    
    if not os.path.exists(BASE_WORK_DIR):
        os.makedirs(BASE_WORK_DIR)
        print(f"📁 Created working directory: {BASE_WORK_DIR}")
    else:
        existing_repos = [d for d in os.listdir(BASE_WORK_DIR) 
                         if os.path.isdir(os.path.join(BASE_WORK_DIR, d)) and 
                         os.path.exists(os.path.join(BASE_WORK_DIR, d, '.git'))]
        print(f"📁 Found {len(existing_repos)} existing repositories: {', '.join(existing_repos)}")
    
    # Process each repository
    results = {
        'processed_repos': 0,
        'skipped_repos': 0,
        'total_branches_created': 0,
        'total_branches_failed': 0,
        'skipped_repo_names': [],
        'all_failed_branches': []
    }
    
    for repo_fullname, repo_info in repo_data.items():
        print_header(f"Processing {repo_fullname}")
        
        # Check if we have a clone URL for this repo
        if repo_fullname not in CLONE_URLS:
            print(f"❌ No clone URL found for {repo_fullname}. Skipping.")
            results['skipped_repos'] += 1
            results['skipped_repo_names'].append(repo_fullname)
            continue
        
        clone_url = CLONE_URLS[repo_fullname]
        local_repo_path = os.path.join(BASE_WORK_DIR, repo_fullname.replace("/", "__"))
        
        # Clone the repository
        repo = clone_repository(repo_fullname, clone_url, local_repo_path)
        if not repo:
            results['skipped_repos'] += 1
            results['skipped_repo_names'].append(repo_fullname)
            continue
        
        # Create instance branches
        successful, failed, failed_details = checkout_instance_branches(repo, repo_fullname, repo_info['commits'])
        results['total_branches_created'] += successful
        results['total_branches_failed'] += failed
        results['all_failed_branches'].extend(failed_details)
        results['processed_repos'] += 1
        
        print(f"✅ Completed processing {repo_fullname}")
    
    # Print final summary
    print_header("🎉 Final Summary 🎉")
    print(f"✅ Successfully processed: {results['processed_repos']}/{total_repos} repositories")
    print(f"🌱 Total branches created: {results['total_branches_created']}")
    print(f"❌ Total branches failed: {results['total_branches_failed']}")
    
    if results['skipped_repos'] > 0:
        print(f"\n⚠️  Skipped repositories ({results['skipped_repos']}):")
        for repo_name in results['skipped_repo_names']:
            print(f"  - {repo_name}")
    
    # Show detailed information about failed branches
    if results['all_failed_branches']:
        print(f"\n❌ Failed Branch Details ({len(results['all_failed_branches'])} failures):")
        print("=" * 80)
        for i, failure in enumerate(results['all_failed_branches'], 1):
            print(f"{i}. Repository: {failure['repo']}")
            print(f"   Instance ID: {failure['instance_id']}")
            print(f"   Problem #: {failure['problem_number']}")
            print(f"   Base Commit: {failure['base_commit']}")
            print(f"   Error Type: {failure['error_type']}")
            print(f"   Error: {failure['error']}")
            print("-" * 40)
    
    if results['processed_repos'] > 0:
        print(f"\n📁 All repositories cloned to: {os.path.abspath(BASE_WORK_DIR)}")
        print("🚀 Ready for Part 2: Push to blitzy-showcase organization")
    
    print_header("Setup Complete")

if __name__ == "__main__":
    main()
