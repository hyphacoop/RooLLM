import requests

name = 'comment_github_item'
emoji = '💬'
description = (
    "Add a comment to a GitHub issue or pull request in a specified repository. "
    "For example: 'Comment on issue #10 in hyphacoop/organizing-private with the message: This is a great proposal.' "
    "or 'Comment on PR #25 in hyphacoop/handbook with Looks good to me!'."
)

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'description': 'GitHub organization name.', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'description': 'Repository name.', 'default': 'organizing-private'},
        'number': {'type': 'integer', 'description': 'The issue or pull request number to comment on.'},
        'body': {'type': 'string', 'description': 'The content of the comment.', 'minLength': 1}
    },
    'required': ['body']
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
        return None, None  # Fallback if request fails

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token") if roo.config else None
    if not token:
        return "GitHub token is missing."

    org = arguments.get("org") or "hyphacoop"
    repo = arguments.get("repo") or "organizing-private"

    number = arguments.get("number")
    if not number:
        return f"❌ Error: Missing issue or PR number. Received arguments: {arguments}"

    body = arguments.get("body", "").strip()
    if not body:
        return "❌ Error: No comment body detected. Please provide the content of the comment."

    try:
        # Add a comment
        url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{number}/comments"
        headers = {"Authorization": f"token {token}"}
        payload = {"body": body}

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 201:
            comment = response.json()

            # Fetch additional info
            title, item_url = get_github_item_details(org, repo, number, token)

            return (
                f"Comment added to **[#{number}]({item_url}) - {title}**\n"
                f"🔗 **[View Comment]({comment['html_url']})**"
            )
        else:
            return f"GitHub API Error: {response.status_code} - {response.text}"

    except Exception as e:
        return f"❌ There was an error while adding the comment: {str(e)}"