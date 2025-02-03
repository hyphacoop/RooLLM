import requests

name = 'reopen_github_issue'
emoji = '🔄'
description = (
    "Reopen a closed GitHub issue in a specified repository. "
    "For example: 'Reopen issue #8 in hyphacoop/organizing-private.'"
)

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'description': 'GitHub organization name.', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'description': 'Repository name.', 'default': 'organizing-private'},
        'issue_number': {'type': 'integer', 'description': 'The number of the issue to reopen.'}
    },
    'required': ['issue_number']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token") if roo.config else None
    if not token:
        return "GitHub token is missing."

    org = arguments.get("org", "hyphacoop")
    repo = arguments.get("repo", "organizing-private")
    issue_number = arguments["issue_number"]

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{issue_number}"
        headers = {"Authorization": f"token {token}"}
        payload = {"state": "open"}

        response = requests.patch(url, headers=headers, json=payload)

        if response.status_code == 200:
            issue = response.json()
            return f"✅ Issue #{issue_number} reopened successfully: [View Issue]({issue['html_url']})"
        else:
            return f"GitHub API Error: {response.status_code} - {response.text}"

    except Exception as e:
        return f"There was an error while reopening the issue: {str(e)}"
