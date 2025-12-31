# SWE-bench Pro Submodule Setup Guide

## Summary

**3 out of 11 repos have submodules:**

| Repo                           | Submodule         | URL                                             | Branches Using It |
| ------------------------------ | ----------------- | ----------------------------------------------- | ----------------- |
| `future-architect__vuls`       | `integration`     | https://github.com/vulsio/integration           | 39 of 63          |
| `gravitational__teleport`      | `e`               | git@github.com:gravitational/teleport.e.git     | 77 of 77          |
| `gravitational__teleport`      | `webassets`       | https://github.com/gravitational/webassets.git  | 64 of 77          |
| `internetarchive__openlibrary` | `vendor/infogami` | https://github.com/internetarchive/infogami.git | 92 of 92          |
| `internetarchive__openlibrary` | `vendor/js/wmd`   | https://github.com/internetarchive/wmd.git      | 92 of 92          |

## Submodule Repos to Fork

You need to fork these 5 repositories to your Enterprise GitHub:

1. **https://github.com/vulsio/integration** ✅ Public
2. **https://github.com/gravitational/teleport.e** ❌ **PRIVATE** - Enterprise features, not accessible
3. **https://github.com/gravitational/webassets** ✅ Public
4. **https://github.com/internetarchive/infogami** ✅ Public
5. **https://github.com/internetarchive/wmd** ✅ Public

⚠️ **IMPORTANT:** `gravitational/teleport.e` is a **private repository** containing Teleport's enterprise features. You will NOT be able to fork this. The `e` submodule will fail to initialize for the 77 teleport branches. This may or may not affect your task instances depending on whether they require enterprise features.

## What's Already Correct

✅ Each task instance branch already contains the correct submodule commit SHA (gitlink)  
✅ When you pushed the branches, the gitlink metadata was preserved  
✅ The submodule references are stored in each branch's tree, not in a separate file

## What Needs to Be Done

### Option A: Keep Public URLs (Simplest)

If your Enterprise GitHub can access public GitHub repos, **no changes needed**. Just run:

```bash
git submodule update --init --recursive
```

When checking out any branch, this will fetch the correct submodule version from the public repos.

### Option B: Fork Submodules to Enterprise GitHub

If your Enterprise environment has restricted internet access:

1. Fork each submodule repo to your Enterprise GitHub org
2. Update the submodule URLs in your local config (not in .gitmodules - that would require changing every branch)

**Per-repo URL override (doesn't modify commits):**

```bash
# For future-architect__vuls
git config submodule.integration.url https://your-enterprise-github.com/your-org/integration.git
git submodule sync
git submodule update --init --recursive

# For gravitational__teleport
git config submodule.e.url https://your-enterprise-github.com/your-org/teleport.e.git
git config submodule.webassets.url https://your-enterprise-github.com/your-org/webassets.git
git submodule sync
git submodule update --init --recursive

# For internetarchive__openlibrary
git config submodule.vendor/infogami.url https://your-enterprise-github.com/your-org/infogami.git
git config submodule.vendor/js/wmd.url https://your-enterprise-github.com/your-org/wmd.git
git submodule sync
git submodule update --init --recursive
```

## Verification Commands

### Check submodule SHA for current branch:

```bash
git ls-tree HEAD <submodule_path>
# Example: git ls-tree HEAD integration
```

### Check if submodule is at correct version:

```bash
git submodule status
# Clean output: " <sha> <path>"
# Dirty output: "+<sha> <path>" (submodule at different commit)
# Missing: "-<sha> <path>" (submodule not initialized)
```

### Switch branches with submodules:

```bash
git checkout <branch> --recurse-submodules
```

## For Docker/CI Environments

When running task instances in containers, add this to your setup:

```bash
git checkout $TASK_BRANCH --recurse-submodules
git submodule update --init --recursive
```

This ensures the submodule is at the exact SHA recorded for that task instance.
