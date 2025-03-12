import requests

name = 'update_pull_request'
emoji = '✏️'
description = "Update the title and/or body of an existing pull request."

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'default': 'organizing-private'},
        'number': {'type': 'integer', 'description': 'The number of the pull request to update.'},
        'title': {'type': 'string', 'description': 'New title of the pull request.', 'default': None},
        'body': {'type': 'string', 'description': 'New body/description of the pull request.', 'default': None}
    },
    'required': ['number']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token")
    if not token:
        return "GitHub token is missing."

    org = arguments.get("org") or "hyphacoop"
    repo = arguments.get("repo") or "organizing-private"

    if not arguments.get("title") and not arguments.get("body"):
        return "❌ Error: Provide at least a new title or body to update."

    url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/pulls/{arguments['number']}"
    headers = {"Authorization": f"token {token}"}
    payload = {}

    if arguments.get("title"):
        payload["title"] = arguments["title"]
    if arguments.get("body"):
        payload["body"] = arguments["body"]

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        pr = response.json()
        return f"✅ Pull Request updated successfully: [View PR]({pr['html_url']})"
    else:
        return f"GitHub API Error: {response.status_code} - {response.text}"
