#!/usr/bin/env python3
"""
SWE-bench Pro Instance Setup Script - Part 2: Push to Organization

This script pushes all locally cloned repositories (with their task instance branches)
to the blitzy-showcase GitHub organization.

Usage:
    python push_to_organization.py

Requirements:
    - GitPython (pip install GitPython)
    - requests (pip install requests)
    - Valid GitHub PAT with organization access
    - Repositories must be cloned locally (run Part 1 first)
"""

import os
import sys
import json
import time
import requests
from git import Repo, GitCommandError
import stat

# Configuration
BASE_WORK_DIR = "../swebench_pro_repos"  # Look one level up from Setup Scripts/
GITHUB_CREDENTIALS_FILE = "github_credentials"
ORGANIZATION = "blitzy-showcase"

def print_header(message):
    """Prints a styled header to the console."""
    print(f"\n{'='*15} {message} {'='*15}")

def load_github_credentials():
    """Load GitHub credentials from the credentials file."""
    try:
        with open(GITHUB_CREDENTIALS_FILE, 'r') as f:
            lines = f.read().strip().split('\n')
        
        credentials = {}
        for line in lines:
            if line.startswith('PAT with organization level acces:'):
                credentials['token'] = line.split(': ')[1].strip()
            elif line.startswith('Username:'):
                credentials['username'] = line.split(': ')[1].strip()
            elif line.startswith('organization:'):
                credentials['organization'] = line.split(': ')[1].strip()
        
        return credentials
    except FileNotFoundError:
        print(f"❌ Error: {GITHUB_CREDENTIALS_FILE} not found!")
        sys.exit(1)

def create_github_repo(repo_name, token, organization):
    """Create a new repository in the GitHub organization."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Create repository in organization
    create_url = f"https://api.github.com/orgs/{organization}/repos"
    payload = {
        "name": repo_name,
        "private": False,  # Making them public for SWE-bench Pro
        "description": f"SWE-bench Pro repository: {repo_name} with task instance branches"
    }
    
    print(f"  📝 Creating repository {organization}/{repo_name}...")
    
    response = requests.post(create_url, headers=headers, json=payload)
    
    if response.status_code == 201:
        print(f"  ✅ Successfully created {organization}/{repo_name}")
        return True
    elif response.status_code == 422:
        # Repository already exists
        print(f"  ⚠️  Repository {organization}/{repo_name} already exists")
        return True
    else:
        print(f"  ❌ Failed to create repository: {response.status_code} - {response.text}")
        return False

def push_large_repository(local_repo_path, repo_name, credentials):
    """Push a large repository using a conservative approach."""
    try:
        repo = Repo(local_repo_path)
    except:
        print(f"  ❌ Failed to open repository at {local_repo_path}")
        return False
    
    organization = credentials['organization']
    token = credentials['token']
    username = credentials['username']
    
    # Create the repository on GitHub
    if not create_github_repo(repo_name, token, organization):
        return False
    
    # Set up remote URL with authentication
    remote_url = f"https://{username}:{token}@github.com/{organization}/{repo_name}.git"
    
    print(f"  🔗 Setting up remote for {organization}/{repo_name}...")
    
    try:
        # Remove existing origin remote if it exists
        if "origin" in repo.remotes:
            repo.delete_remote("origin")
        
        # Add new remote pointing to organization repo
        origin = repo.create_remote("origin", remote_url)
        
        # Step 1: Push main branch first to establish the repository
        print(f"  📤 Step 1: Pushing main branch to establish repository...")
        try:
            repo.git.push("origin", "main:main", "--force")
            print(f"    ✅ Main branch pushed successfully")
        except GitCommandError as e:
            print(f"    ⚠️  Main branch push failed, trying master: {e}")
            try:
                repo.git.push("origin", "master:master", "--force")
                print(f"    ✅ Master branch pushed successfully")
            except GitCommandError as e2:
                print(f"    ❌ Both main and master failed: {e2}")
                return False
        
        # Step 2: Push task instance branches one by one with delays
        print(f"  📤 Step 2: Pushing task instance branches individually...")
        task_branches = [head.name for head in repo.heads if head.name.startswith("instance_")]
        
        success_count = 0
        for i, branch_name in enumerate(task_branches, 1):
            try:
                print(f"    📤 Pushing branch {i}/{len(task_branches)}: {branch_name[:50]}...")
                repo.git.push("origin", f"{branch_name}:{branch_name}", "--force")
                success_count += 1
                
                # Add small delay to avoid overwhelming GitHub
                if i % 5 == 0:
                    print(f"    ⏸️  Brief pause after {i} branches...")
                    time.sleep(2)
                    
            except GitCommandError as e:
                print(f"      ⚠️  Failed to push branch {branch_name}: {e}")
        
        print(f"  📊 Successfully pushed {success_count}/{len(task_branches)} task instance branches")
        
        # Step 3: Push any remaining branches
        other_branches = [head.name for head in repo.heads if not head.name.startswith("instance_") and head.name not in ["main", "master"]]
        if other_branches:
            print(f"  📤 Step 3: Pushing {len(other_branches)} other branches...")
            for branch_name in other_branches:
                try:
                    repo.git.push("origin", f"{branch_name}:{branch_name}", "--force")
                except GitCommandError as e:
                    print(f"      ⚠️  Failed to push branch {branch_name}: {e}")
        
        print(f"  ✅ Successfully pushed {repo_name} to {organization}")
        return True
        
    except Exception as e:
        print(f"  ❌ Unexpected error pushing {repo_name}: {e}")
        return False

def push_repository(local_repo_path, repo_name, credentials):
    """Push a local repository to the GitHub organization."""
    try:
        repo = Repo(local_repo_path)
    except:
        print(f"  ❌ Failed to open repository at {local_repo_path}")
        return False
    
    organization = credentials['organization']
    token = credentials['token']
    username = credentials['username']
    
    # Create the repository on GitHub
    if not create_github_repo(repo_name, token, organization):
        return False
    
    # Set up remote URL with authentication
    remote_url = f"https://{username}:{token}@github.com/{organization}/{repo_name}.git"
    
    print(f"  🔗 Setting up remote for {organization}/{repo_name}...")
    
    try:
        # Remove existing origin remote if it exists
        if "origin" in repo.remotes:
            repo.delete_remote("origin")
        
        # Add new remote pointing to organization repo
        origin = repo.create_remote("origin", remote_url)
        
        print(f"  📤 Pushing all branches to {organization}/{repo_name}...")
        
        # For large repositories, push branches in batches to avoid timeouts
        all_branches = [head.name for head in repo.heads]
        batch_size = 20 if len(all_branches) > 50 else len(all_branches)
        
        if len(all_branches) > 50:
            print(f"  📊 Large repository detected ({len(all_branches)} branches), pushing in batches of {batch_size}")
            
            for i in range(0, len(all_branches), batch_size):
                batch = all_branches[i:i + batch_size]
                print(f"    📤 Pushing batch {i//batch_size + 1}/{(len(all_branches) + batch_size - 1)//batch_size}: {len(batch)} branches")
                
                for branch_name in batch:
                    try:
                        repo.git.push("origin", f"{branch_name}:{branch_name}", "--force")
                    except GitCommandError as e:
                        print(f"      ⚠️  Failed to push branch {branch_name}: {e}")
        else:
            # Push all branches at once for smaller repositories
            repo.git.push("origin", "--all", "--force")
        
        # Also push tags if any
        try:
            repo.git.push("origin", "--tags", "--force")
        except GitCommandError:
            # Tags push might fail if there are no tags, which is fine
            pass
        
        print(f"  ✅ Successfully pushed {repo_name} to {organization}")
        return True
        
    except GitCommandError as e:
        print(f"  ❌ Failed to push {repo_name}: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error pushing {repo_name}: {e}")
        return False

def get_local_repositories():
    """Get list of locally cloned repositories."""
    if not os.path.exists(BASE_WORK_DIR):
        print(f"❌ Working directory {BASE_WORK_DIR} not found!")
        print("Please run Part 1 (clone_and_checkout_instances.py) first.")
        sys.exit(1)
    
    repos = []
    for item in os.listdir(BASE_WORK_DIR):
        item_path = os.path.join(BASE_WORK_DIR, item)
        if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, '.git')):
            # Convert directory name back to repo name
            repo_name = item.replace("__", "/")
            repos.append((repo_name, item_path))
    
    return repos

def count_branches(repo_path):
    """Count the number of branches in a repository."""
    try:
        repo = Repo(repo_path)
        return len(list(repo.heads))
    except:
        return 0

def main():
    """Main execution function."""
    print_header("SWE-bench Pro Instance Setup - Part 2")
    print("This script will push all repositories with task instance branches to blitzy-showcase.")
    
    # Load GitHub credentials
    print_header("Loading GitHub Credentials")
    credentials = load_github_credentials()
    
    if not all(key in credentials for key in ['token', 'username', 'organization']):
        print("❌ Missing required credentials (token, username, or organization)")
        sys.exit(1)
    
    print(f"✅ Loaded credentials for {credentials['username']} -> {credentials['organization']}")
    
    # Verify GitHub access
    print_header("Verifying GitHub Access")
    headers = {"Authorization": f"Bearer {credentials['token']}", "Accept": "application/vnd.github.v3+json"}
    
    try:
        # Test authentication
        auth_response = requests.get("https://api.github.com/user", headers=headers)
        auth_response.raise_for_status()
        user_info = auth_response.json()
        print(f"✅ Authenticated as {user_info['login']}")
        
        # Test organization access
        org_response = requests.get(f"https://api.github.com/orgs/{credentials['organization']}", headers=headers)
        org_response.raise_for_status()
        print(f"✅ Organization access confirmed for {credentials['organization']}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ GitHub access verification failed: {e}")
        sys.exit(1)
    
    # Get local repositories
    print_header("Scanning Local Repositories")
    abs_work_dir = os.path.abspath(BASE_WORK_DIR)
    print(f"📁 Looking for repositories in: {abs_work_dir}")
    
    local_repos = get_local_repositories()
    
    if not local_repos:
        print("❌ No local repositories found!")
        print("Please run Part 1 (clone_and_checkout_instances.py) first.")
        sys.exit(1)
    
    print(f"📋 Found {len(local_repos)} local repositories:")
    total_branches = 0
    for repo_name, repo_path in local_repos:
        branch_count = count_branches(repo_path)
        total_branches += branch_count
        print(f"  - {repo_name} ({branch_count} branches)")
    
    print(f"🌱 Total branches to push: {total_branches}")
    
    # Confirm before proceeding
    print(f"\n⚠️  This will create/update {len(local_repos)} repositories in {credentials['organization']}")
    confirm = input("Do you want to proceed? (y/N): ").strip().lower()
    
    if confirm != 'y':
        print("❌ Operation cancelled by user")
        sys.exit(0)
    
    # Process each repository
    print_header("Pushing Repositories")
    results = {
        'successful': 0,
        'failed': 0,
        'failed_repos': []
    }
    
    for i, (repo_name, repo_path) in enumerate(local_repos, 1):
        print(f"\n📦 Processing {i}/{len(local_repos)}: {repo_name}")
        
        # Special handling for large webclients repository
        if repo_name == "protonmail/webclients":
            print(f"  🔧 Special handling for large repository: {repo_name} (2.9GB)")
            if push_large_repository(repo_path, repo_name.split('/')[-1], credentials):
                results['successful'] += 1
            else:
                results['failed'] += 1
                results['failed_repos'].append(repo_name)
            continue
        
        # Extract just the repository name (without org prefix)
        repo_simple_name = repo_name.split('/')[-1]
        
        if push_repository(repo_path, repo_simple_name, credentials):
            results['successful'] += 1
        else:
            results['failed'] += 1
            results['failed_repos'].append(repo_name)
    
    # Print final summary
    print_header("🎉 Push Summary 🎉")
    print(f"✅ Successfully pushed: {results['successful']}/{len(local_repos)} repositories")
    print(f"❌ Failed: {results['failed']} repositories")
    
    if results['failed_repos']:
        print(f"\n⚠️  Failed repositories:")
        for repo_name in results['failed_repos']:
            print(f"  - {repo_name}")
    
    if results['successful'] > 0:
        print(f"\n🚀 All successful repositories are now available at:")
        print(f"   https://github.com/{credentials['organization']}")
        print(f"\n🌱 Total task instance branches pushed: {total_branches}")
    
    print_header("Push Complete")

if __name__ == "__main__":
    main()
