import requests

name = 'add_labels_to_github_item'
emoji = '🏷️'
description = (
    "Add labels to a GitHub item in a specified repository. "
    "For example: 'Label issue #15 in hyphacoop/organizing-private with bug and high-priority.' "
    "or 'Label PR #17 in hyphacoop/governance-experiment with enhancement.'"
)

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'description': 'GitHub organization name.', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'description': 'Repository name.', 'default': 'organizing-private'},
        'number': {'type': 'integer', 'description': 'The number of the issue or pull request to label.'},
        'labels': {
            'type': 'array',
            'items': {'type': 'string'},
            'description': 'List of labels to add to the issue or pull request.'
        }
    },
    'required': ['labels']
}

GITHUB_API_BASE_URL = "https://api.github.com"

def get_repo_labels(org, repo, token):
    """Fetch available labels for a repo to ensure valid labels are used."""
    url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/labels"
    headers = {"Authorization": f"token {token}"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return {label['name'].lower() for label in response.json()}  # Lowercase for case-insensitive match
    else:
        raise Exception(f"Unable to fetch labels: {response.status_code} - {response.text}")

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

    org = arguments.get("org", "hyphacoop")
    repo = arguments.get("repo", "organizing-private")
    
    # Handle both 'pr_number' and 'issue_number' by normalizing to 'number'
    number = arguments.get("number") or arguments.get("pr_number") or arguments.get("issue_number")
    if not number:
        return f"❌ Error: Missing issue or PR number. Received arguments: {arguments}"

    labels = arguments["labels"]

    try:
        # Fetch available labels to validate input
        available_labels = get_repo_labels(org, repo, token)
        
        # Filter out invalid labels
        valid_labels = [label for label in labels if label.lower() in available_labels]
        invalid_labels = [label for label in labels if label.lower() not in available_labels]

        if not valid_labels:
            return f"❌ No valid labels provided. Available labels: {', '.join(available_labels)}"

        url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues/{number}/labels"
        headers = {"Authorization": f"token {token}"}
        payload = {"labels": valid_labels}

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code in [200, 201]:
            # Fetch additional info
            title, item_url = get_github_item_details(org, repo, number, token)

            message = (
                f"Added labels {', '.join(valid_labels)} to **#{number} - {title}**\n"
                f"🔗 **[View on GitHub]({item_url})**"
            )

            if invalid_labels:
                message += f"\nThe following labels were ignored because they don't exist: {', '.join(invalid_labels)}."

            return message
        else:
            return f"GitHub API Error: {response.status_code} - {response.text}"

    except Exception as e:
        return f"There was an error while adding labels: {str(e)}"
