import requests
import os

name = 'merge_pull_request'
emoji = '🔀'
description = "Merge an open pull request."

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'default': os.getenv("DEFAULT_GITHUB_ORG", "hyphacoop")},
        'repo': {'type': 'string', 'default': os.getenv("DEFAULT_GITHUB_REPO", "organizing-private")},
        'number': {'type': 'integer', 'description': 'The number of the pull request to merge.'}
    },
    'required': ['number']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token")
    if not token:
        return "GitHub token is missing."
    
    org = arguments.get("org") or os.getenv("DEFAULT_GITHUB_ORG", "hyphacoop")
    repo = arguments.get("repo") or os.getenv("DEFAULT_GITHUB_REPO", "organizing-private")
    number = arguments["number"]

    url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/pulls/{number}/merge"
    headers = {"Authorization": f"token {token}"}

    response = requests.put(url, headers=headers)

    pr_link = f"https://github.com/{org}/{repo}/pull/{number}"

    if response.status_code == 200:
        return f"✅ Pull Request [#{number}]({pr_link}) merged successfully!"
    elif response.status_code == 405:
        return f"⚠️ Pull Request #{number}({pr_link}) is not mergeable. Check for conflicts."
    elif response.status_code == 404:
        return f"❌ PR #{number} not found in '{org}/{repo}'."
    else:
        return f"GitHub API Error: {response.status_code} - {response.text}"
