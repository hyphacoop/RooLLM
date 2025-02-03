import requests

name = 'comment_github_issue'
emoji = '💬'
description = (
    "Add a comment to a GitHub issue in a specified repository. "
    "For example: 'Comment on issue #10 in hyphacoop/organizing-private with the message: This is a test comment.'"
)

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'description': 'GitHub organization name.', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'description': 'Repository name.', 'default': 'organizing-private'},
        'issue_number': {'type': 'integer', 'description': 'The number of the issue to comment on.'},
        'body': {'type': 'string', 'description': 'The content of the comment.', 'minLength': 1}
    },
    'required': ['issue_number', 'body']
}

GITHUB_API_BASE_URL = "https://api.github.com"

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token") if roo.config else None
    if not token:
        return "GitHub token is missing."

    org = arguments.get("org", "hyphacoop")
    repo = arguments.get("repo", "organizing-private")
    issue_number = arguments["issue_number"]
    body = arguments["body"]

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{issue_number}/comments"
        headers = {"Authorization": f"token {token}"}
        payload = {"body": body}

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 201:
            comment = response.json()
            return f"💬 Comment added successfully: [View Comment]({comment['html_url']})"
        else:
            return f"GitHub API Error: {response.status_code} - {response.text}"
    
    except Exception as e:
        return f"There was an error while adding the comment: {str(e)}"
