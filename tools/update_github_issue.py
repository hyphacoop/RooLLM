import requests
import os
name = 'update_github_issue'
emoji = '📋'
description = (
    "Update the title and/or body of an existing GitHub issue in a specified repository. "
    "For example: 'Update issue #10 in hyphacoop/organizing-private with a new title and description.'"
)

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'description': 'GitHub organization name.',  'default': os.getenv("DEFAULT_GITHUB_ORG", "hyphacoop")},
        'repo': {'type': 'string', 'description': 'Repository name.', 'default': os.getenv("DEFAULT_GITHUB_REPO", "organizing-private")},
        'number': {'type': 'integer', 'description': 'The number of the issue to update.'},
        'title': {'type': 'string', 'description': 'New title of the issue.', 'default': None},
        'body': {'type': 'string', 'description': 'New body description of the issue.', 'default': None}
    },
    'required': ['number']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token") if roo.config else None
    if not token:
        return "GitHub token is missing."

    org = arguments.get("org") or os.getenv("DEFAULT_GITHUB_ORG", "hyphacoop")
    repo = arguments.get("repo") or os.getenv("DEFAULT_GITHUB_REPO", "organizing-private")
    number = arguments["number"]
    title = arguments.get("title")
    body = arguments.get("body")

    if not title and not body:
        return "❌ Error: Provide at least a new title or body to update."

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{number}"
        headers = {"Authorization": f"token {token}"}
        payload = {}

        if title:
            payload["title"] = title
        if body:
            payload["body"] = body

        response = requests.patch(url, headers=headers, json=payload)

        print(response)

        if response.status_code == 200:
            issue = response.json()
            return f"✅ Issue updated successfully: [View Issue]({issue['html_url']})"
        else:
            return f"GitHub API Error: {response.status_code} - {response.text}"
    
    except Exception as e:
        return f"There was an error while updating the issue: {str(e)}"
