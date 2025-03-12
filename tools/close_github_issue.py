import requests

name = 'close_github_issue'
emoji = '🔒'
description = (
    "Close an issue in a specified GitHub repository by issue number. "
    "For example: 'Close issue #42 in hyphacoop/organizing-private.'"
)

parameters = {
    'type': 'object',
    'properties': {
        'org': {
            'type': 'string',
            'description': 'GitHub organization name. Defaults to "hyphacoop".',
            'default': 'hyphacoop'
        },
        'repo': {
            'type': 'string',
            'description': 'Repository name. Defaults to "organizing-private".',
            'default': 'organizing-private'
        },
        'number': {
            'type': 'integer',
            'description': 'The number of the issue to close.'
        }
    },
    'required': ['number']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token") if roo.config else None

    if not token:
        return "GitHub token is missing."

    org = arguments.get("org") or "hyphacoop"
    repo = arguments.get("repo") or "organizing-private"
    number = arguments["number"]

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{number}"
        headers = {"Authorization": f"token {token}"}
        payload = {"state": "closed"}

        response = requests.patch(url, headers=headers, json=payload)

        if response.status_code == 200:
            issue = response.json()
            return f"Issue #{number} closed successfully: {issue['html_url']}"
        elif response.status_code == 404:
            return f"Issue #{number} not found in '{org}/{repo}'."
        else:
            return f"GitHub API Error: {response.status_code} - {response.text}"

    except Exception as e:
        return f"There was an error while closing the issue: {str(e)}"
