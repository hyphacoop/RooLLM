import requests

name = 'close_pull_request'
emoji = '🔒'
description = "Close a pull request without merging."

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'default': 'organizing-private'},
        'number': {'type': 'integer', 'description': 'The number of the pull request to close.'}
    },
    'required': ['number']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token")
    if not token:
        return "GitHub token is missing."
    
    org = arguments.get("org", "hyphacoop")
    repo = arguments.get("repo", "organizing-private")

    url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/pulls/{arguments['number']}"
    headers = {"Authorization": f"token {token}"}
    payload = {"state": "closed"}

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        return f"✅ Pull Request #{arguments['number']} closed successfully!"
    else:
        return f"GitHub API Error: {response.status_code} - {response.text}"
