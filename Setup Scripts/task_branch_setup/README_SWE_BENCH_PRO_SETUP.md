# SWE-bench Pro Instance Setup Scripts

This repository contains two Python scripts to set up all 731 SWE-bench Pro task instances by cloning repositories and creating branches for each task instance.

## Overview

SWE-bench Pro contains 731 problems across 11 repositories. Each problem represents a repository state at a specific commit (base_commit) where an issue is present. The scripts automate the process of:

1. **Part 1**: Cloning your forked repositories and creating task instance branches
2. **Part 2**: Pushing all repositories with their branches to the blitzy-showcase organization

## Files

- `clone_and_checkout_instances.py` - Part 1: Clone repos and create instance branches
- `push_to_organization.py` - Part 2: Push repos to blitzy-showcase organization
- `swebench_pro_grouped_chronological.json` - Contains all 731 task instances
- `github_credentials` - Contains your GitHub PAT and organization info
- `clone_urls` - Contains URLs of your forked repositories

## Prerequisites

1. **Python Dependencies**:
   ```bash
   pip install GitPython requests
   ```

2. **GitHub Setup**:
   - Your personal forks of all 11 SWE-bench Pro repositories
   - GitHub Personal Access Token (PAT) with organization access
   - Access to the `blitzy-showcase` organization

3. **Repository Forks**:
   The scripts expect you to have forked these repositories:
   - NodeBB/NodeBB
   - qutebrowser/qutebrowser
   - ansible/ansible
   - internetarchive/openlibrary
   - gravitational/teleport
   - navidrome/navidrome
   - element-hq/element-web
   - future-architect/vuls
   - protonmail/webclients
   - flipt-io/flipt
   - tutao/tutanota

## Usage

### Part 1: Clone and Create Instance Branches

```bash
python clone_and_checkout_instances.py
```

This script will:
- Clone all your forked repositories to `swebench_pro_repos/` directory
- Create a branch for each task instance named after the instance_id
- Each branch will be checked out at the corresponding base_commit

**Example branch names**:
- `instance_NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5-vnan`
- `instance_qutebrowser__qutebrowser-f91ace96223cac8161c16dd061907e138fe85111-v059c6fdc75567943479b23ebca7c07b5e9a7f34c`

### Part 2: Push to Organization

```bash
python push_to_organization.py
```

This script will:
- Create repositories in the blitzy-showcase organization
- Push all local repositories with their task instance branches
- Preserve all branch history and commits

## Expected Results

After running both scripts successfully:

- **11 repositories** will be created in the blitzy-showcase organization
- **731 task instance branches** will be available across all repositories
- Each branch represents a specific SWE-bench Pro problem at the correct commit state

## Repository Structure

```
swebench_pro_repos/
├── NodeBB__NodeBB/
│   ├── .git/
│   └── [44 instance branches]
├── qutebrowser__qutebrowser/
│   ├── .git/
│   └── [79 instance branches]
├── ansible__ansible/
│   ├── .git/
│   └── [96 instance branches]
└── [8 more repositories...]
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Verify your GitHub PAT has the correct permissions
   - Ensure you have access to the blitzy-showcase organization

2. **Clone Failures**:
   - Check that your forks are accessible
   - Verify the repository URLs in the clone_urls mapping

3. **Missing Commits**:
   - Some base commits might not exist in your forks
   - The script will skip these and report them

4. **Branch Creation Failures**:
   - Usually due to missing commits or Git errors
   - Check the detailed error messages in the output

### Verification

To verify the setup worked correctly:

1. Check the blitzy-showcase organization on GitHub
2. Verify each repository has the expected number of branches
3. Spot-check a few branches to ensure they're at the correct commits

## Statistics

- **Total Repositories**: 11
- **Total Task Instances**: 731
- **Repository Breakdown**:
  - NodeBB/NodeBB: 44 instances
  - qutebrowser/qutebrowser: 79 instances
  - ansible/ansible: 96 instances
  - [Additional repositories with their instance counts]

## Notes

- The scripts are designed to be idempotent - you can run them multiple times
- Existing repositories and branches will be overwritten
- All repositories will be created as public in the organization
- The scripts include comprehensive error handling and progress reporting

## Support

If you encounter issues:
1. Check the detailed console output for specific error messages
2. Verify all prerequisites are met
3. Ensure your GitHub credentials and permissions are correct
