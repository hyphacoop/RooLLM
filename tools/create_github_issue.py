import requests

name = 'create_github_issue'
emoji = '📝'
description = (
    "Create a new issue in a specified GitHub repository. "
    "You can specify the title, description, labels, and an assignee. "
    "For example: 'Create an issue titled Bug Report in the repo hyphacoop/organizing-private, assigned to @username.'"
)

parameters = {
    'type': 'object',
    'properties': {
        'org': {
            'type': 'string',
            'description': 'GitHub organization name. Defaults to "hyphacoop".',
            'default': 'hyphacoop'
        },
        'repo': {
            'type': 'string',
            'description': 'Repository name. Defaults to "organizing-private".',
            'default': 'organizing-private'
        },
        'title': {
            'type': 'string',
            'description': 'Title of the issue.',
            'minLength': 1
        },
        'body': {
            'type': 'string',
            'description': 'Description or details of the issue.',
            'default': ''
        },
        'labels': {
            'type': 'array',
            'items': {'type': 'string'},
            'description': 'List of labels to apply to the issue.'
        },
        'assignee': {
            'type': 'string',
            'description': 'Assignee for the issue. Use "none" for no assignee.',
            'default': None
        }
    },
    'required': ['title']
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

    org = arguments.get("org") or "hyphacoop"
    repo = arguments.get("repo") or "organizing-private"
    title = arguments["title"]
    body = arguments.get("body", "")
    labels = arguments.get("labels", [])
    assignee = arguments.get("assignee")  # Optional

    try:
        # Fetch labels from the repo **only if labels were provided**
        if labels:
            repo_labels = get_repo_labels(org, repo, token)

            # Validate provided labels
            invalid_labels = [label for label in labels if label not in repo_labels]
            if invalid_labels:
                return f"Invalid labels provided: {', '.join(invalid_labels)}. Available labels are: {', '.join(repo_labels)}"

        # Preprocess the assignee to remove '@' if present
        if assignee and assignee.startswith("@"):
            assignee = assignee[1:]

        url = f"{GITHUB_API_BASE_URL}/repos/{org}/{repo}/issues"
        headers = {"Authorization": f"token {token}"}
        payload = {
            "title": title,
            "body": body,
            "labels": labels if labels else [],
            "assignee": assignee if assignee != "none" else None
        }

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 201:
            issue = response.json()
            return f"Issue created successfully: {issue['html_url']}"
        else:
            return f"GitHub API Error: {response.status_code} - {response.text}"

    except Exception as e:
        return f"There was an error while creating the issue: {str(e)}"
