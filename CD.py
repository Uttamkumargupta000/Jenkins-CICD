import requests
import os
import re
import sys
import subprocess
import shutil

owner = "gripinvest"
repo = "release-test-1"

# Branch to send 
branch = "develop"

# new Released going 
new_tag = sys.argv[1]
# new_tag = "v2.5.9"

# target_services to change only 
target_repos = sys.argv[2]
# target_repos = "gi-common-service, gi-client-static, grip-client-web"

# github token for private repository
token = sys.argv[3]

# Check for the private repository
def isPrivateRepo(token, owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    print(url)

    headers = {"Accept": "application/vnd.github.v3+json"}

    if token:
        headers["Authorization"] = f"token {token}"
    
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json().get("private", False)
    else:
        print(f"Warning: Unable to determine reporsiotry is private ({response.status_code}). Assuming Public. ")
        return False
    
# function to handle clone repository, if doesn't exist it will pull latest changes
def clone_or_pull_repo(token, owner, repo, branch):
    repo_path = os.path.join(os.getcwd(), repo)

    # checking for public or private repo
    if isPrivateRepo(token, owner, repo) and token:
        repo_url = f"https://{token}@github.com/{owner}/{repo}.git"
    else:
        repo_url = f"https://github.com/{owner}/{repo}.git"

    if os.path.exists(repo_path) and os.path.isdir(os.path.join(repo_path, ".git")):
        try:
            subprocess.run(["git", "-C", repo_path, "checkout", branch], check=True)
            subprocess.run(["git", "-C", repo_path, "pull", "origin", branch], check=True)
            print(f"Successfully pulled latest changes for {repo}")
        except subprocess.CalledProcessError as e:
            print(f"Error pulling repository {repo}: {e}")
    else:
        # If folder exists but is not a git repo, remove it
        if os.path.exists(repo_path):
            print(f"Removing invalid repo folder: {repo_path}")
            shutil.rmtree(repo_path)

        try:
            subprocess.run(["git", "clone", "-b", branch, repo_url, repo_path], check=True)
            print(f"Successfully cloned {repo} on branch {branch}")
        except subprocess.CalledProcessError as e:
            print(f"Error cloning repository {repo}: {e}")

# function to update the value of tag in .yaml files
def update_tag(directory: str, new_tag: str, target_repos: str):
    if not os.path.isdir(directory):
        print(f"Error: The directory '{directory}' does not exist.")
        return False

    # Full repo names as provided
    allowed_repo_names = set([repo.strip() for repo in target_repos.split(",") if repo.strip()])

    # For gi-sirius-* we match on suffix after removing 'gi-'
    sirius_allowed_suffixes = set([
        repo.replace("gi-", "").strip()
        for repo in allowed_repo_names
        if repo.startswith("gi-")
    ])

    print(f"[INFO] Allowed generic repos: {allowed_repo_names}")
    print(f"[INFO] Allowed gi-sirius suffixes: {sirius_allowed_suffixes}")

    files_updated = 0

    for service in os.listdir(directory):
        service_path = os.path.join(directory, service)
        if not os.path.isdir(service_path):
            continue

        for file in os.listdir(service_path):
            if not file.endswith((".yaml", ".yml")):
                continue

            file_path = os.path.join(service_path, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue

            updated_content = content

            # --- gi-sirius-* handler ---
            def replace_sirius_tag(match):
                full_repo_path = match.group(2)
                repo_name = full_repo_path.split("/")[-1]  # gi-sirius-app-bridge
                suffix = repo_name.replace("gi-sirius-", "")
                print(f"[gi-sirius] Found: {repo_name}, Suffix: {suffix}")

                if suffix in sirius_allowed_suffixes:
                    print(f"[gi-sirius] Updating tag for {repo_name}")
                    return f"{match.group(1)}{new_tag}"
                else:
                    print(f"[gi-sirius] Skipping {repo_name}")
                    return match.group(0)

            sirius_pattern = re.compile(
                r"(repository:\s*ghcr\.io/([\w-]+/[\w-]+/gi-sirius-[\w-]+)\s*\n\s*tag:\s*)v[\d\.]+",
                re.MULTILINE
            )
            updated_content = sirius_pattern.sub(replace_sirius_tag, updated_content)

            # --- Generic repo handler ---
            def replace_generic_tag(match):
                full_repo_path = match.group(2)
                repo_name = full_repo_path.split("/")[-1]
                print(f"[generic] Found: {repo_name}")

                if repo_name in allowed_repo_names:
                    print(f"[generic] Updating tag for {repo_name}")
                    return f"{match.group(1)}{new_tag}"
                else:
                    print(f"[generic] Skipping {repo_name}")
                    return match.group(0)

            generic_pattern = re.compile(
                r"(repository:\s*ghcr\.io/([\w-]+/[\w-]+)\s*\n\s*tag:\s*)v[\d\.]+",
                re.MULTILINE
            )
            updated_content = generic_pattern.sub(replace_generic_tag, updated_content)

            if updated_content != content:
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(updated_content)
                    files_updated += 1
                    print(f"Tag updated in: {file_path}")
                except Exception as e:
                    print(f"Error writing to {file_path}: {e}")
            else:
                print(f"No update needed in: {file_path}")

    if files_updated == 0:
        print("No matching services found. No files updated.")
    else:
        print(f"Total Files Updated: {files_updated}")

    return files_updated > 0

# function to handle commit and push in github
def commitAndPushChanges(token, owner, repo, branch, commit_message):
    repo_path = os.path.join(os.getcwd(), repo)

    if not os.path.exists(repo_path):
        print(f"Error: The repository '{repo} does not exist locally. clone it first")
        return
    
    remote_url = f"https://{token}@github.com/{owner}/{repo}.git"

    try:
        os.chdir(repo_path)

        # Fetch the latest changes from remote to detect conflicts
        subprocess.run(["git", "fetch", "origin", branch], check=True)

        # check for merge conflicts before proceeding
        status_result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)

        if "UU" in status_result.stdout:
            print(f"Merge conflicts detect in {repo}. Resolve them before pushing")
            return
        
        # Add all the changes
        subprocess.run(["git", "add", "."], check=True)

        # commit changes with user provided message
        subprocess.run(["git", "commit", "-m", commit_message], check=True)

        # pull latest changes before pushing changes to the specified branch
        pull_result = subprocess.run(["git", "pull", "--rebase" "origin", branch], capture_output=True, text=True)

        if "CONFLICT" in pull_result.stdout:
            print(f"Merge conflict detected while pulling changes in {repo}. Resolve them before pushing")
            return 
        
        # push changes to the specified branch
        subprocess.run(["git", "push", remote_url, branch], check=True)

        print(f"Successfully committed and pushed changes to {branch} in {repo}.")
    
    except subprocess.CalledProcessError as e:
        print(f"Error while commmiting or push changes: {e}")

# Main function to take user input and update tag in YAML files inside each subfolder.
def main():
    # Pull changes from github account
    clone_or_pull_repo(token, owner, repo, branch)

    if not re.match(r"^v\d+\.\d+\.\d+$", new_tag):
        print("Invalid tag format. Use the format vX.Y.Z (e.g., v18.0.0).")
        return

    # Dynamically handlle the service folder and tag update 
    services_folder = os.path.join(os.getcwd(), repo, "services")

    # Check if services folder exists before proceeding
    if not os.path.isdir(services_folder):
        print(f"Warning: Skipping {repo} as 'services' directory does not exist.")
        return
        
    # Update the tag as new release going 
    tag_updated = update_tag(services_folder, new_tag, target_repos)
    
    # Push changes only if the tag was updated
    if tag_updated:
        commitAndPushChanges(token, owner, repo, branch, f"Updated tag to {new_tag}")

if __name__ == "__main__":
    main()
