import requests

name = 'assign_github_item'
emoji = '👤'
description = (
    "Assign a GitHub user to an issue or pull request in a specified repository. "
    "For example: 'Assign @username to issue #12 in hyphacoop/organizing-private.' "
    "or 'Assign @username to PR #25 in hyphacoop/code-repo.'"
)

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'description': 'GitHub organization name.', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'description': 'Repository name.', 'default': 'organizing-private'},
        'number': {'type': 'integer', 'description': 'The issue or pull request number to assign a user to.'},
        'assignee': {'type': 'string', 'description': 'GitHub username of the assignee.'}
    },
    'required': ['assignee']
}

GITHUB_API_BASE_URL = "https://api.github.com"

def get_github_item_details(org, repo, number, token):
    """Fetch issue or PR details (title, URL) from GitHub."""
    url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{number}"
    headers = {"Authorization": f"token {token}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        item = response.json()
        return item.get("title", "No title"), item.get("html_url", "No URL")
    else:
        return None, None 

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token") if roo.config else None
    if not token:
        return "GitHub token is missing."

    org = arguments.get("org", "hyphacoop")
    repo = arguments.get("repo", "organizing-private")

    number = arguments.get("number")
    if not number:
        return f"❌ Error: Missing issue or PR number. Received arguments: {arguments}"

    assignee = arguments["assignee"].lstrip("@")  # Remove @ if mistakenly added

    try:
        url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{number}/assignees"
        headers = {"Authorization": f"token {token}"}
        payload = {"assignees": [assignee]}

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code in [200, 201]:
              # Fetch additional info
            title, url = get_github_item_details(org, repo, number, token)

            return (
                f"✅ Assigned **{assignee}** to **#{number} - {title}**\n"
                f"🔗 **[View on GitHub]({url})**"
            )
        else:
            return f"GitHub API Error: {response.status_code} - {response.text}"
    
    except Exception as e:
        return f"There was an error while assigning the item: {str(e)}"
