#!/usr/bin/env python3
"""
Test script to check if the missing commits exist in the original repository
"""

import os
import sys
from git import Repo

# The two missing commits
MISSING_COMMITS = [
    "7fb29b60c6b33fab16fd5464786f74427c9eb16e",  # Problem #577
    "8b68951e795c21134273225efbd64e5999ffba0f"   # Problem #582
]

def test_commits_in_repo(repo_path, repo_name):
    """Test if the missing commits exist in the given repository."""
    print(f"\n🔍 Testing commits in {repo_name} at {repo_path}")
    
    if not os.path.exists(repo_path):
        print(f"❌ Repository path does not exist: {repo_path}")
        return False
    
    try:
        repo = Repo(repo_path)
        print(f"✅ Successfully opened repository")
        
        for i, commit_hash in enumerate(MISSING_COMMITS, 1):
            try:
                commit = repo.commit(commit_hash)
                print(f"✅ Commit #{i} FOUND: {commit_hash[:8]} - {commit.message.strip()[:50]}...")
            except Exception as e:
                print(f"❌ Commit #{i} NOT FOUND: {commit_hash[:8]} - {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to open repository: {e}")
        return False

def main():
    print("🔍 Testing Missing Commits in WebClients Repositories")
    print("=" * 60)
    
    # Test in your fork
    fork_path = "../swebench_pro_repos/protonmail__webclients"
    test_commits_in_repo(fork_path, "Your Fork")
    
    # Test in original repository (once cloned)
    original_path = "webclients_original"
    test_commits_in_repo(original_path, "Original Repository")

if __name__ == "__main__":
    main()
