import requests

name = 'assign_pull_request'
emoji = '👤'
description = "Assign a GitHub user to a pull request."

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'default': 'organizing-private'},
        'pr_number': {'type': 'integer', 'description': 'The number of the pull request to assign a user to.'},
        'assignee': {'type': 'string', 'description': 'GitHub username of the assignee.'}
    },
    'required': ['pr_number', 'assignee']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token")
    if not token:
        return "GitHub token is missing."
    
    org = arguments.get("org", "hyphacoop")
    repo = arguments.get("repo", "organizing-private")

    url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{arguments['pr_number']}/assignees"
    headers = {"Authorization": f"token {token}"}
    payload = {"assignees": [arguments["assignee"].lstrip("@")]}

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        return f"✅ Pull Request #{arguments['pr_number']} assigned to {arguments['assignee']} successfully."
    else:
        return f"GitHub API Error: {response.status_code} - {response.text}"
