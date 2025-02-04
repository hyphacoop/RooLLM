import requests

name = 'reopen_pull_request'
emoji = '🔓'
description = "Reopen a previously closed pull request."

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'default': 'organizing-private'},
        'number': {'type': 'integer', 'description': 'The number of the pull request to reopen.'}
    },
    'required': ['number']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    print(arguments)
    token = roo.config.get("gh_token")
    if not token:
        return "GitHub token is missing."
    
    org = arguments.get("org", "hyphacoop")
    repo = arguments.get("repo", "organizing-private")

    url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/pulls/{arguments['number']}"
    headers = {"Authorization": f"token {token}"}
    payload = {"state": "open"}

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        return f"Pull Request #{arguments['number']} reopened successfully!"
    else:
        return f"GitHub API Error: {response.status_code} - {response.text}"
