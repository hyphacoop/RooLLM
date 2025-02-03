import requests

name = 'assign_github_issue'
emoji = '🗂️'
description = (
    "Assign a GitHub user to an issue in a specified repository. "
    "For example: 'Assign @username to issue #12 in hyphacoop/organizing-private.'"
)

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'description': 'GitHub organization name.', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'description': 'Repository name.', 'default': 'organizing-private'},
        'issue_number': {'type': 'integer', 'description': 'The number of the issue to assign a user to.'},
        'assignee': {'type': 'string', 'description': 'GitHub username of the assignee.'}
    },
    'required': ['issue_number', 'assignee']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token") if roo.config else None
    if not token:
        return "GitHub token is missing."

    org = arguments.get("org", "hyphacoop")
    repo = arguments.get("repo", "organizing-private")
    issue_number = arguments["issue_number"]
    assignee = arguments["assignee"].lstrip("@")  # Remove @ if mistakenly added

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{issue_number}/assignees"
        headers = {"Authorization": f"token {token}"}
        payload = {"assignees": [assignee]}

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code in [200, 201]:
            return f"✅ Issue #{issue_number} assigned to {assignee} successfully."
        else:
            return f"GitHub API Error: {response.status_code} - {response.text}"
    
    except Exception as e:
        return f"There was an error while assigning the issue: {str(e)}"
