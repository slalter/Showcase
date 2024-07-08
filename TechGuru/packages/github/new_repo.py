import requests
import os

def create_private_repo(org, repo_name):
    """
    Create a private GitHub repository within an organization.

    Args:
    org (str): The organization in which to create the repository.
    repo_name (str): The name of the repository to create.
    token (str): GitHub personal access token with necessary permissions.
    """
    url = f"https://api.github.com/orgs/{org}/repos"
    token = os.environ.get("GITHUB_TOKEN", None)
    if not token:
        raise ValueError("GitHub token not found. Please set the GITHUB_TOKEN environment variable.")
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "name": repo_name,
        "private": True
    }
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        print(f"Successfully created repository: {repo_name}")
        return response.json()  # Returns JSON data about the new repo
    else:
        print(f"Failed to create repository: {response.status_code}")
        print(response.text)
        return None

# Example Usage
if __name__ == "__main__":
    ORG_NAME = "your_organization_name"
    REPO_NAME = "new_private_repo"
    TOKEN = "your_github_token"
    
    create_private_repo(ORG_NAME, REPO_NAME, TOKEN)
