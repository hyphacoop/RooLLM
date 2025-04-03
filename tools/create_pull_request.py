import requests
import os

name = 'create_pull_request'
emoji = '🌿'
description = "Create a pull request in a specified GitHub repository."

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'default': os.getenv("DEFAULT_GITHUB_ORG", "hyphacoop")},
        'repo': {'type': 'string', 'default': os.getenv("DEFAULT_GITHUB_REPO", "organizing-private")},
        'title': {'type': 'string', 'description': 'Title of the pull request.', 'minLength': 1},
        'body': {'type': 'string', 'description': 'PR description.', 'default': ''},
        'head': {'type': 'string', 'description': 'Branch name with changes.', 'minLength': 1},
        'base': {'type': 'string', 'description': 'Branch into which changes should be merged.', 'minLength': 1}
    },
    'required': ['title', 'head', 'base']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token")
    if not token:
        return "GitHub token is missing."
    
    org = arguments.get("org") or os.getenv("DEFAULT_GITHUB_ORG", "hyphacoop")
    repo = arguments.get("repo") or os.getenv("DEFAULT_GITHUB_REPO", "organizing-private")
    url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/pulls"
    headers = {"Authorization": f"token {token}"}
    payload = {
        "title": arguments["title"],
        "body": arguments["body"],
        "head": arguments["head"],
        "base": arguments["base"]
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 201:
        pr = response.json()
        return f"✅ Pull Request created: [View PR]({pr['html_url']})"
    else:
        return f"GitHub API Error: {response.status_code} - {response.text}"
