import requests

name = 'comment_pull_request'
emoji = '💬'
description = "Add a comment to a pull request."

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'default': 'organizing-private'},
        'pr_number': {'type': 'integer', 'description': 'The number of the pull request to comment on.'},
        'body': {'type': 'string', 'description': 'The content of the comment.', 'minLength': 1}
    },
    'required': ['pr_number', 'body']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token")
    if not token:
        return "GitHub token is missing."

    # Apply defaults if org or repo is missing
    org = arguments.get("org", "hyphacoop")  # Ensure default org
    repo = arguments.get("repo", "organizing-private")  # Ensure default repo
    pr_number = arguments["pr_number"]
    body = arguments.get("body", "").strip()

    # If body is missing, infer it from the input
    if not body:
        return "❌ Error: No comment body detected. Please provide the content of the comment."

    url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{pr_number}/comments"
    headers = {"Authorization": f"token {token}"}
    payload = {"body": body}

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 201:
        comment = response.json()
        return f"💬 Comment added successfully: [View Comment]({comment['html_url']})"
    else:
        return f"GitHub API Error: {response.status_code} - {response.text}"
