import requests

name = 'add_label_to_pull_request'
emoji = '🏷️'
description = (
    "Add labels to a GitHub pull request in a specified repository. "
    "For example: 'Label PR #17 in hyphacoop/governance-experiment with Feedback required and enhancement.'"
)

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'description': 'GitHub organization name.', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'description': 'Repository name.', 'default': 'organizing-private'},
        'pr_number': {'type': 'integer', 'description': 'The number of the pull request to label.'},
        'labels': {
            'type': 'array',
            'items': {'type': 'string'},
            'description': 'List of labels to add to the pull request.'
        }
    },
    'required': ['pr_number', 'labels']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token") if roo.config else None
    if not token:
        return "GitHub token is missing."

    org = arguments.get("org", "hyphacoop")
    repo = arguments.get("repo", "organizing-private")
    pr_number = arguments["pr_number"]
    labels = arguments["labels"]

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{pr_number}/labels"
        headers = {"Authorization": f"token {token}"}
        payload = {"labels": labels}

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200 or response.status_code == 201:
            return f"🏷️ Labels {', '.join(labels)} added successfully to PR #{pr_number}."
        else:
            return f"GitHub API Error: {response.status_code} - {response.text}"

    except Exception as e:
        return f"There was an error while adding labels: {str(e)}"
