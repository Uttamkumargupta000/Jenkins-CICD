import requests
import json
import sys
from packaging.version import parse

# 1. for Base branch (e.g., "develop" or "main")
base = sys.argv[1] 

# 2. Release Tag Name
tag = sys.argv[2]

# 3. for Repositories (comma-separated string)
repos = sys.argv[3]  
user_repo = [repo.strip() for repo in repos.split(",") if repo.strip()]

repositories = []
for entry in user_repo:
  if "/" in entry:
    owner, repo = entry.split("/", 1)
    repositories.append((owner, repo))
  else:
    print(f"Invalid format in the .env file '{entry} , SKipping.....")

# 4. GitHub token from Jenkins credentials 
token = sys.argv[4]

if not token:
  print("Error: Github token is missing. Please set it in the environment variable")
  exit(1)

test_url = "https://api.github.com/gripinvest"
headers = {"Authorization": f"token {token}"}
response = requests.get(test_url, headers=headers)
if response.status_code == 401:
    print(" Error: Invalid GitHub token. Check your token permissions and try again.")
    exit(1)

# fetching the latest release of current version
def fetch_latest_release(owner, repo, token):
    # Fetch the latest release
    release_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers['Authorization'] = f"token {token}"

    response = requests.get(release_url, headers=headers)

    tags = []
    if response.status_code == 200 and response.json():
        releases = response.json()
        tags = [release["tag_name"] for release in releases if "tag_name" in release]

    # Fetch tags if no releases exist
    if not tags:
        tag_url = f"https://api.github.com/repos/{owner}/{repo}/tags"
        response = requests.get(tag_url, headers=headers)
        if response.status_code == 200 and response.json():
            tags = [tag["name"] for tag in response.json()]

    # Sort tags properly (assuming semantic versioning)
    tags.sort(key=parse, reverse=True)

    # print(f"Sorted Tags: {tags}")

    # Assign latest and previous tags correctly
    latest_tag = tags[0] if tags else base

    # If only one tag, compare with base
    prev_tag = tags[1] if len(tags) > 1 else base 

    # print(f"Latest Tag: {latest_tag}, Previous Tag: {prev_tag}")
    return latest_tag, prev_tag

# Compare the branch to get 
def compare_branch(owner, repo, base, branch, token):
  # api call for check in github
  if not branch:
    print(f" Skipping {repo} - No valid feature branch found.")
    branch = base
  # For Checking in reverse Direction 
  url = f"https://api.github.com/repos/{owner}/{repo}/compare/{branch}...{base}"

  # authentication for private repository
  headers = {
    "Accept" : "application/vnd.github.v3+json"
  }

  if token:
    headers['Authorization'] = f"token {token}"

  # fetching the data 
  response = requests.get(url, headers=headers)
  data = response.json()

  if response.status_code == 200:
    # print(f"Repository : {repo}")
    print(f"Github Compare Link: {data['html_url']}")
    # print(f"Total Commit Ahead: {data['total_commits']}\n")

    # Extract commit message
    changelog = []
    for commit in data.get('commits', []):
      message = commit['commit']['message']
      author = commit['commit']['author']['name']
      changelog.append(f"- {message} (by {author})")

    # if changelog:
    #   print("\n What's Changed: ")
    #   print("\n".join(changelog))
    #   print("\n")

# Tracking the files changes
    total_additons = 0
    total_deletions = 0
    total_changes = 0

    for file in data.get('files',[]):
      additions = file.get('additions',0)
      deletions = file.get('deletions', 0)
      changes = file.get('changes', 0)

      total_additons += additions
      total_deletions += deletions
      total_changes += changes

    print(f"Total Changes: {total_changes}")

    return total_changes > 0, changelog, total_changes

  else:
    print(f"Error {response.status_code}: {response.json().get('message', 'Unknown error')}")
    return False, [], 0

# handle github releases 
def create_github_release(owner, repo, tag_name, title, description, token, latest_tag):
  release_url = f"https://api.github.com/repos/{owner}/{repo}/releases"

  headers = {
    "Accept": "application/vnd.github.v3+json"
  }
  if token: 
    headers['Authorization'] = f"token {token}"

    release_data = {
        "tag_name": tag_name,
        "name": title,
        "body": f" What's Changed\n {description}\n\n Full Changelog\n[View Compare](https://github.com/{owner}/{repo}/compare/{latest_tag}...{tag_name})",
        "draft": False,  
        "prerelease": False 
    }

    response = requests.post(release_url, json=release_data, headers=headers)

    if response.status_code == 201:
      print(f"Successfully created release '{title}' for {repo}!")
      print(f"Release URL : {response.json().get('html_url')}")
    else:
      print(f"Error Creating  release for repo {repo}: {response.json().get('message','Unknown')}")

# create a tag or release for the change that found
def create_tag(owner, repo, new_tag, base, token, changelog, prev_tag):
  tag_url = f"https://api.github.com/repos/{owner}/{repo}/git/refs"

  headers = {
    "Accept": "application/vnd.github.v3+json"
  }

  if token:
    headers['Authorization'] = f"token {token}"

  branch_url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{base}"
  branch_response = requests.get(branch_url, headers=headers)

  if branch_response.status_code != 200:
    print(f"Error fetching the lates commit for {repo}: {branch_response.json().get('message', 'unknown Error')}")
    return 
  
  latest_commit_sha = branch_response.json().get("object", {}).get("sha")

  if not latest_commit_sha:
    print(f"Unable to find the latest commit SHA for the {repo}")
    return
  
  tag_data = {
    "ref" : f"refs/tags/{new_tag}",
    "sha": latest_commit_sha
  }
  
  tag_response = requests.post(tag_url, json=tag_data, headers=headers)
  
  if tag_response.status_code == 201:
    print(f"Successfully created tag '{new_tag}' for {repo}.")
    
    # Automatically set the release title as per new tag name
    release_title = new_tag
    release_description = "\n".join(changelog)
    create_github_release(owner, repo, new_tag, release_title,release_description, token, prev_tag)

  else:
    print(f"Error creating tag '{new_tag}' for {repo}: {tag_response.json().get('message', 'unknown error')}")
      
# Main function to call 
def main():
    if 'repos_list' not in locals():
      repos_list = []
      
    repos_list.extend(user_repo)

    # check repo list is empty
    if not repos_list:
      print("No repo Provided")
      exit()

    repositories = []
    for entry in repos_list:
      if "/" in entry:
        owner, repo = entry.split("/", 1)
        repositories.append((owner, repo))
      else:
        print(f"Invalid format in the .env file '{entry} , SKipping.....")
  

    # List to store the repository with changes
    changed_repos = []

    for owner, repo in repositories:
        print(f"\n Checking repository: {owner}/{repo}")
        feature_branch, prev_tag = fetch_latest_release(owner, repo, token)
        print(f"Prev_Tag: {feature_branch}")

        changes_found, changelog, total_changes = compare_branch(owner, repo, base, feature_branch, token)
        # print(f"changes found : {changes_found}")

        # changes found to create the tag 
        if changes_found:
            new_tag = tag
            print(f"Latest_Tag: {new_tag}")
            if new_tag:
                create_tag(owner, repo, new_tag, base, token,changelog, feature_branch)

                 # Add repository to the list
                changed_repos.append(f"{owner}/{repo}") 
        else:
            print(f"No Changes found for {repo} so No Tag created")

        
    # Print the list of repositories with changes at the end
    if changed_repos:
      repos_json = json.dumps(changed_repos)
      print(repos_json)
      sys.exit(0)
    else :
      print("[]")
      sys.exit(0)

if __name__ == "__main__":
  main()
