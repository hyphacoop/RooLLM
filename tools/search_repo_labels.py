import requests

name = 'search_repo_labels'
emoji = '🏷️'
description = "Search and retrieve labels from a specified GitHub repository."

parameters = {
    'type': 'object',
    'properties': {
        'org': {'type': 'string', 'default': 'hyphacoop'},
        'repo': {'type': 'string', 'default': 'organizing-private'}
    },
    'required': ['org', 'repo']
}

GITHUB_API_BASE_URL = "https://api.github.com"

def get_repo_labels(org, repo, token):
    url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/labels"
    headers = {"Authorization": f"token {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return [label['name'] for label in response.json()]
    else:
        raise Exception(f"Unable to fetch labels: {response.status_code} - {response.text}")

async def tool(roo, arguments, user):
    token = roo.config.get("gh_token") if roo.config else None

    if not token:
        return "GitHub token is missing."

    org = arguments.get("org", "hyphacoop")
    repo = arguments.get("repo", "organizing-private")

    try:
        labels = get_repo_labels(org, repo, token)
        return f"Labels in '{org}/{repo}': {', '.join(labels)}"
    except Exception as e:
        return f"There was an error while fetching labels: {str(e)}"