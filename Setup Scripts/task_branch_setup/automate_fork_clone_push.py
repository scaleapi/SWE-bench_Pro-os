import os
import sys
import json
import time
import requests
import shutil
from git import Repo, GitCommandError
import stat

# =================== CONFIGURATION ===================
REPOS_JSON_PATH = "repos_grouped_chronologically.json"
BASE_WORK_DIR = "swebench_onboarded"
# =====================================================

# === HELPER FUNCTIONS ===
def print_header(message):
    """Prints a styled header to the console."""
    print(f"\n{'='*10} {message} {'='*10}")

def remove_readonly(func, path, _):
    """Error handler for shutil.rmtree."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def get_secure_token():
    """Gets the GitHub token from an environment variable."""
    token = os.getenv("GITHUB_PAT")
    if not token:
        print("❌ SECURITY ERROR: GitHub token not found."); sys.exit(1)
    return token

def delete_repo(owner, repo_name, headers, repo_type="repo"):
    """Deletes a GitHub repository."""
    print(f"  - Checking for '{owner}/{repo_name}' to delete...")
    delete_url = f"https://api.github.com/repos/{owner}/{repo_name}"

    # 🧪 DEBUG PRINTS
    # print(f"    🔍 DELETE URL: {delete_url}")
    # print(f"    🔐 HEADERS: {headers}")

    response = requests.delete(delete_url, headers=headers)
    if response.status_code == 204:
        print(f"    ✅ Successfully deleted '{owner}/{repo_name}'.")
        return True
    elif response.status_code == 404:
        return True # It's already gone, which is a success for our purposes.
    else:
        print(f"    ❌ Failed to delete '{owner}/{repo_name}': {response.status_code} - {response.text}")
        return False

# === MAIN WORKFLOW AND CLEANUP FUNCTIONS ===
def run_cleanup(repo_data, auth_info):
    """Deletes all repositories associated with this script from the user's account."""
    repo_owner = auth_info["repo_owner"]
    headers = auth_info["headers"]
    
    print_header(f"Starting Cleanup for account: {repo_owner}")
    print("This will find and delete repositories with the following names if they exist:")
    for repo_fullname in repo_data.keys():
        _, repo_name = repo_fullname.split("/")
        print(f"  - {repo_owner}/{repo_name}")

    print("\n" + "!"*60)
    print("!!! WARNING: THIS ACTION IS DESTRUCTIVE AND CANNOT BE UNDONE. !!!")
    print("!"*60)
    confirm_text = input(f"To proceed, please type the account name '{repo_owner}' to confirm deletion: ")
    
    if confirm_text != repo_owner:
        print("\n❌ Confirmation did not match. Aborting cleanup."); return

    print("\n✅ Confirmation received. Proceeding with deletion...")
    for repo_fullname in repo_data.keys():
        _, repo_name = repo_fullname.split("/")
        delete_repo(repo_owner, repo_name, headers)


def run_main_workflow(repo_data, auth_info):
    """Executes the primary workflow to create and onboard repositories."""
    results = {"processed": [], "skipped": []}
    
    for repo_fullname in repo_data.keys():
        data = repo_data[repo_fullname]
        original_org, repo_name = repo_fullname.split("/")
        local_repo_dir = os.path.join(BASE_WORK_DIR, repo_fullname.replace("/", "__"))
        
        print_header(f"Processing: {repo_fullname}")
        
        if os.path.exists(local_repo_dir):
            shutil.rmtree(local_repo_dir, onexc=remove_readonly)
        
        repo_obj = None
        # Special 'Direct Clone' strategy for SymPy
        if repo_fullname == "sympy/sympy":
            print("⚠️ SymPy detected. Using special 'Direct Clone' strategy.")
            delete_repo(auth_info["repo_owner"], repo_name, auth_info["headers"])
            original_repo_url = f"https://github.com/{repo_fullname}.git"
            print(f"📥 Cloning original repo from '{original_repo_url}'...")
            repo_obj = Repo.clone_from(original_repo_url, local_repo_dir)
        # Standard 'Fork, Delete, Recreate' strategy for all others
        else:
            print(f"🍴 Using 'Fork, Delete, Recreate' strategy...")
            fork_api_url = f"https://api.github.com/repos/{auth_info['repo_owner']}/{repo_name}"
            if requests.get(fork_api_url, headers=auth_info["headers"]).status_code == 200:
                print("⚠️ Public fork already exists. Deleting it to start fresh.")
                if not delete_repo(auth_info["repo_owner"], repo_name, auth_info["headers"], repo_type="fork"):
                    results["skipped"].append(repo_fullname); continue
            
            fork_url = f"https://api.github.com/repos/{repo_fullname}/forks"
            org_name = auth_info["repo_owner"] if auth_info["repo_owner"] != auth_info["user_login"] else None
            fork_payload = {"organization": org_name} if org_name else {}
            fork_res = requests.post(fork_url, headers=auth_info["headers"], json=fork_payload)
            
            if fork_res.status_code == 202:
                print("   - Forking request accepted. Waiting (up to 10 minutes)...")
                max_wait_time = 600; poll_interval = 15; start_time = time.time()
                fork_exists = False
                while time.time() - start_time < max_wait_time:
                    if requests.get(fork_api_url, headers=auth_info["headers"]).status_code == 200:
                        print("   - Fork is ready!")
                        fork_exists = True; break
                    elapsed = int(time.time() - start_time)
                    print(f"     - Waiting... (elapsed: {elapsed}s / {max_wait_time}s)")
                    time.sleep(poll_interval)
                if not fork_exists:
                    print(f"❌ Forking timed out. Skipping."); results["skipped"].append(repo_fullname); continue
            else:
                print(f"❌ Forking failed: {fork_res.text}"); results["skipped"].append(repo_fullname); continue

            # --- THIS IS THE FIX: A retry loop for the clone operation ---
            max_clone_attempts = 3
            for attempt in range(max_clone_attempts):
                print(f"   - Attempting to clone fork (attempt {attempt + 1} of {max_clone_attempts})...")
                try:
                    repo_obj = Repo.clone_from(f"https://github.com/{auth_info['repo_owner']}/{repo_name}.git", local_repo_dir)
                    print("   - ✅ Clone successful!")
                    break # Exit the loop on success
                except GitCommandError as e:
                    print(f"     - Clone failed: {e.stderr.strip()}")
                    if attempt < max_clone_attempts - 1:
                        print("     - Waiting 20 seconds before retrying...")
                        time.sleep(20)
                    else:
                        print(f"❌ Failed to clone after {max_clone_attempts} attempts. Skipping repo.")
                        repo_obj = None # Ensure repo_obj is None so we skip this repo
            
            if not repo_obj:
                results["skipped"].append(repo_fullname); continue
            
            if not delete_repo(auth_info["repo_owner"], repo_name, auth_info["headers"], repo_type="fork"):
                results["skipped"].append(repo_fullname); continue

        # --- Onboard, Create Private Repo, and Push ---
        print("🌱 Creating local branches...")
        with repo_obj.config_writer() as cw:
            cw.set_value("user", "name", auth_info["git_author_name"])
            cw.set_value("user", "email", auth_info["git_author_email"])
        for commit_info in data["commits"]:
            repo_obj.create_head(commit_info["instance_id"], commit_info["base_commit"])

        print(f"\n🚀 Creating final private repo: '{auth_info['repo_owner']}/{repo_name}'")
        create_api_url = f"https://api.github.com/orgs/{org_name}/repos" if org_name else "https://api.github.com/user/repos"
        create_payload = {"name": repo_name, "private": True}
        create_res = requests.post(create_api_url, headers=auth_info["headers"], json=create_payload)
        if create_res.status_code not in [201, 422]:
            print(f"❌ Failed to create private repo: {create_res.text}"); results["skipped"].append(repo_fullname); continue
        
        private_remote_url = f"https://{auth_info['user_login']}:{auth_info['token']}@github.com/{auth_info['repo_owner']}/{repo_name}.git"
        
        remote_set = False
        for attempt in range(3):
            try:
                config_path = os.path.join(repo_obj.working_dir, ".git", "config")
                if os.path.exists(config_path): os.chmod(config_path, stat.S_IWRITE)
                if "origin" in repo_obj.remotes: repo_obj.delete_remote("origin")
                repo_obj.create_remote("origin", private_remote_url)
                remote_set = True; break
            except GitCommandError as e:
                print(f"   - ⚠️ Attempt {attempt + 1} to set remote failed: {e.stderr.strip()}. Retrying in 3s...")
                time.sleep(3)
        
        if not remote_set:
            print("❌ Failed to set remote. Skipping push."); results["skipped"].append(repo_fullname); continue

        repo_obj.git.push("origin", "--all", "--force")
        print(f"✅ Successfully pushed all branches to '{auth_info['repo_owner']}/{repo_name}'.")
        results["processed"].append(repo_fullname)

    print_header("🎉 Main Workflow Summary 🎉")
    print(f"✅ Successfully processed: {len(results['processed'])} repositories")
    for repo in results["processed"]: print(f"  - {repo}")
    if results["skipped"]:
        print(f"\n❌ Skipped or failed: {len(results['skipped'])} repositories")
        for repo in results["skipped"]: print(f"  - {repo}")

# === MAIN EXECUTION BLOCK ===
if __name__ == "__main__":
    # ... (This block remains the same, providing the menu) ...
    print_header("Main Menu")
    print("What would you like to do?")
    print("1. Run the full automation workflow to create repositories")
    print("2. Clean up (delete) all repositories created by this script")
    choice = input("Enter your choice (1 or 2): ").strip()

    if choice not in ['1', '2']:
        print("Invalid choice. Please enter 1 or 2."); sys.exit(1)
    
    print_header("Initializing & Validating GitHub Access")
    GITHUB_PAT = get_secure_token()
    HEADERS = {"Authorization": f"Bearer {GITHUB_PAT}", "Accept": "application/vnd.github.v3+json"}
    try:
        auth_response = requests.get("https://api.github.com/user", headers=HEADERS)
        auth_response.raise_for_status()
        user_info = auth_response.json()
        auth_info = {
            "token": GITHUB_PAT, "headers": HEADERS, "user_login": user_info['login'],
            "repo_owner": user_info['login'], "git_author_name": user_info.get('name') or user_info['login'],
            "git_author_email": user_info.get('email') or f"{user_info['id']}+{user_info['login']}@users.noreply.github.com",
        }
        print(f"✅ Authenticated as {auth_info['user_login']}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Authentication failed: {e}"); sys.exit(1)

    org = input(f"Enter the GitHub account or organization name to operate on (default: {auth_info['repo_owner']}): ").strip()
    if org: auth_info["repo_owner"] = org
    
    with open(REPOS_JSON_PATH, "r") as f: repo_data_main = json.load(f)["repositories"]

    if choice == '1':
        run_main_workflow(repo_data_main, auth_info)
    elif choice == '2':
        run_cleanup(repo_data_main, auth_info)