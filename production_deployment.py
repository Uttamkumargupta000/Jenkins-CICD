import requests
import os
import re
import sys
import subprocess

owner = "gripinvest"
repo = "argocd-prod"

# Branch to send 
branch = "main"

# new Released going 
new_tag = sys.argv[1]

# target_services to change only 
target_repos = sys.argv[2]

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
def clone_or_pull_repo(token,owner, repo, branch):
    
    repo_path = os.path.join(os.getcwd(), repo)

    # checking for public or private repo
    if isPrivateRepo(token, owner, repo) and token:
        repo_url = f"https://{token}@github.com/{owner}/{repo}.git"
    else:
        repo_url = f"https://github.com/{owner}/{repo}.git"

    if os.path.exists(repo_path):
        try:
            subprocess.run(["git","-C", repo_path, "checkout", branch], check= True)
            subprocess.run(["git","-C", repo_path, "pull", "origin", branch], check= True)
            print(f"Successfully pulled latest changes for {repo}")

        except subprocess.CalledProcessError as e:
            print(f"Error pulling repository {repo}: {e}")
        
    else:
        try:
            subprocess.run(["git", "clone", "-b", branch, repo_url, repo_path], check = True)
            print(f"Successfully cloned {repo} on branch {branch} ")
        except subprocess.CalledProcessError as e:
            print(f"Error cloning repository {repo}: {e}")

# function to update the value of tag in .yaml files
def update_tag(directory: str, new_tag: str, target_repos: str):
    if not os.path.isdir(directory):
        print(f"Error: The directory '{directory}' does not exist.")
        return False

    # Extract suffixes from full service names like 'gi-kyc-service' → 'kyc-service'
    allowed_suffixes = [
        repo.strip().replace("gi-", "") for repo in target_repos.split(",") if repo.strip()
    ]
    print(f"Allowed service suffixes: {allowed_suffixes}")

    files_updated = 0

    for service in os.listdir(directory):
        service_path = os.path.join(directory, service)

        if os.path.isdir(service_path):
            for file in os.listdir(service_path):
                if file.endswith((".yaml", ".yml")):
                    file_path = os.path.join(service_path, file)

                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
                        continue

                    updated_content = content

                    # Pattern to match lines like:
                    # repository: ghcr.io/gripinvest/<anything>/gi-sirius-<suffix>
                    # followed by tag: vX.Y.Z
                    pattern = re.compile(
                        r"(repository:\s*ghcr\.io/gripinvest/[-\w]+/(gi-sirius-([\w-]+))\s*)([\s\S]*?)(tag:\s*)v[\d.]+",
                        re.MULTILINE
                    )

                    matches = pattern.findall(content)
                    for repo_line, full_repo, suffix, middle_block, tag_line in matches:
                        if suffix in allowed_suffixes:
                            print(f"Updating: {full_repo} in {file_path}")
                            updated_content = re.sub(
                                rf"{re.escape(repo_line)}{re.escape(middle_block)}{tag_line}v[\d.]+",
                                f"{repo_line}{middle_block}{tag_line}{new_tag}",
                                updated_content
                            )
                        else:
                            print(f"Skipping: {full_repo} (suffix '{suffix}' not allowed)")

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
